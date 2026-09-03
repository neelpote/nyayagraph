from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import AccessGrant, AuditEvent, Case, Document, Notification, User
from ..repositories.core import UserRepository
from ..security.auth import AuthenticatedUser
from ..blockchain.ledger import get_ledger
from ..security.policy import policy_engine
from ..utils.time import utc_now


class AccessService:
    GRANT_ROLES = {"INVESTIGATING_OFFICER", "SUPERVISOR", "ADMIN"}

    def _document_and_case(self, db: Session, document_id: str) -> tuple[Document, Case]:
        document = db.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        case = db.get(Case, document.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return document, case

    def create_grant(self, db: Session, actor: AuthenticatedUser, *, document_id: str, subject_email: str,
                     expires_at: datetime, reason: str, permissions: str = "READ") -> AccessGrant:
        if actor.role not in self.GRANT_ROLES:
            raise HTTPException(status_code=403, detail="Role cannot grant access")
        if permissions != "READ":
            raise HTTPException(status_code=422, detail="Only READ grants are supported")
        document, case = self._document_and_case(db, document_id)
        if actor.role != "ADMIN" and not policy_engine.can_view_case(db, actor, case):
            raise HTTPException(status_code=403, detail="Actor cannot manage access for this case")
        if actor.role == "INVESTIGATING_OFFICER" and case.investigating_officer_id != actor.id:
            raise HTTPException(status_code=403, detail="Only the assigned investigating officer can grant access")
        subject = UserRepository().by_email(db, subject_email)
        if not subject or subject.status != "ACTIVE":
            raise HTTPException(status_code=404, detail="Target user not found")
        now = utc_now()
        if expires_at <= now or expires_at > now + timedelta(days=30):
            raise HTTPException(status_code=422, detail="Grant expiry must be within the next 30 days")
        if subject.clearance_level < document.classification_level:
            raise HTTPException(status_code=403, detail="Target clearance is below document classification")
        grant = AccessGrant(resource_type="DOCUMENT", resource_id=document.id, subject_user_id=subject.id,
                            subject_org_id=subject.organization_id, permissions=permissions, valid_from=now,
                            expires_at=expires_at, granted_by=actor.id, reason=reason, requested_scope=document.title)
        db.add(grant); db.flush()
        grant.fabric_tx_id = get_ledger().grant_access(db, grant_id=grant.id, resource_id=document.id, actor_id=actor.id,
                                                       case_id=case.id,
                                                       subject_commitment=hashlib.sha256(subject.id.encode()).hexdigest(),
                                                       expires_commitment=hashlib.sha256(expires_at.isoformat().encode()).hexdigest())
        db.add(AuditEvent(actor_user_id=actor.id, organization_id=actor.organization_id, action="GRANT_ACCESS",
                          resource_type="ACCESS_GRANT", resource_id=grant.id, case_id=case.id,
                          authorization_decision="ALLOWED", metadata_json={"subject_user_id": subject.id, "expires_at": expires_at.isoformat()}))
        db.add(Notification(user_id=subject.id, case_id=case.id, type="ACCESS_GRANTED", title="Temporary case access granted",
                            message=f"Access to {document.title} expires {expires_at.isoformat()}."))
        db.commit(); db.refresh(grant)
        return grant

    def break_glass(self, db: Session, actor: AuthenticatedUser, *, document_id: str, justification: str,
                    requested_scope: str, minutes: int) -> AccessGrant:
        if actor.role not in {"INVESTIGATING_OFFICER", "FSL_OFFICER", "PROSECUTOR", "COURT_USER", "SUPERVISOR", "ADMIN"}:
            raise HTTPException(status_code=403, detail="Role cannot request emergency evidence access")
        if len(justification.strip()) < 20:
            raise HTTPException(status_code=422, detail="Emergency-access justification must be at least 20 characters")
        if minutes < 5 or minutes > 60:
            raise HTTPException(status_code=422, detail="Emergency access must expire within 5–60 minutes")
        document, case = self._document_and_case(db, document_id)
        if not policy_engine.can_view_case(db, actor, case):
            raise HTTPException(status_code=403, detail="Actor is not assigned to this case")
        if actor.clearance_level < document.classification_level:
            raise HTTPException(status_code=403, detail="Clearance is insufficient even for emergency access")
        now = utc_now()
        grant = AccessGrant(resource_type="DOCUMENT", resource_id=document.id, subject_user_id=actor.id,
                            subject_org_id=actor.organization_id, permissions="READ", valid_from=now,
                            expires_at=now + timedelta(minutes=minutes), granted_by=actor.id, reason=justification,
                            requested_scope=requested_scope, is_break_glass=True, supervisor_review_required=True)
        db.add(grant); db.flush()
        grant.fabric_tx_id = get_ledger().grant_access(db, grant_id=grant.id, resource_id=document.id, actor_id=actor.id,
                                                       case_id=case.id, break_glass=True,
                                                       subject_commitment=hashlib.sha256(actor.id.encode()).hexdigest(),
                                                       expires_commitment=hashlib.sha256(grant.expires_at.isoformat().encode()).hexdigest())
        db.add(AuditEvent(actor_user_id=actor.id, organization_id=actor.organization_id, action="BREAK_GLASS_ACCESS",
                          resource_type="ACCESS_GRANT", resource_id=grant.id, case_id=case.id,
                          authorization_decision="ALLOWED", metadata_json={"scope": requested_scope, "expires_at": grant.expires_at.isoformat(), "supervisor_review_required": True}))
        db.commit(); db.refresh(grant)
        return grant

    def revoke(self, db: Session, actor: AuthenticatedUser, grant_id: str, reason: str) -> AccessGrant:
        if actor.role not in self.GRANT_ROLES:
            raise HTTPException(status_code=403, detail="Role cannot revoke access")
        grant = db.get(AccessGrant, grant_id)
        if not grant:
            raise HTTPException(status_code=404, detail="Access grant not found")
        _, case = self._document_and_case(db, grant.resource_id)
        if actor.role != "ADMIN" and not policy_engine.can_view_case(db, actor, case):
            raise HTTPException(status_code=403, detail="Grant belongs to another case")
        if actor.role == "INVESTIGATING_OFFICER" and case.investigating_officer_id != actor.id:
            raise HTTPException(status_code=403, detail="Grant belongs to another case")
        grant.status = "REVOKED"
        grant.fabric_tx_id = get_ledger().revoke_access(db, grant_id=grant.id, resource_id=grant.resource_id, actor_id=actor.id,
                                                        case_id=case.id, reason=reason)
        db.add(AuditEvent(actor_user_id=actor.id, organization_id=actor.organization_id, action="REVOKE_ACCESS",
                          resource_type="ACCESS_GRANT", resource_id=grant.id, case_id=case.id,
                          authorization_decision="ALLOWED",
                          metadata_json={"reason": reason}))
        db.commit(); db.refresh(grant)
        return grant

    def list_grants(self, db: Session, actor: AuthenticatedUser, case_id: str | None = None) -> list[AccessGrant]:
        query = select(AccessGrant).order_by(AccessGrant.expires_at.desc())
        if case_id:
            document_ids = select(Document.id).where(Document.case_id == case_id)
            query = query.where(AccessGrant.resource_id.in_(document_ids))
        if actor.role == "INVESTIGATING_OFFICER":
            case_ids = select(Case.id).where(Case.investigating_officer_id == actor.id)
            document_ids = select(Document.id).where(Document.case_id.in_(case_ids))
            query = query.where(AccessGrant.resource_id.in_(document_ids))
        elif actor.role in {"SUPERVISOR", "AUDITOR"}:
            organization_cases = select(Case.id).join(
                User, User.id == Case.investigating_officer_id
            ).where(User.organization_id == actor.organization_id)
            document_ids = select(Document.id).where(Document.case_id.in_(organization_cases))
            query = query.where(AccessGrant.resource_id.in_(document_ids))
        elif actor.role != "ADMIN":
            query = query.where(AccessGrant.subject_user_id == actor.id)
        return list(db.scalars(query))
