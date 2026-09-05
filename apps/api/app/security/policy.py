from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import AccessGrant, Case, CaseAssignment, Document, Evidence, User
from .auth import AuthenticatedUser
from ..utils.time import utc_now


class PolicyEngine:
    """Deterministic authorization: role, clearance, assignment/grant, then expiry."""

    def can_view_case(self, db: Session, actor: AuthenticatedUser, case: Case) -> bool:
        if actor.clearance_level < case.classification_level:
            return False
        if actor.role == "ADMIN":
            return True
        if actor.role in {"AUDITOR", "SUPERVISOR"}:
            lead_organization = db.scalar(select(User.organization_id).where(
                User.id == case.investigating_officer_id
            ))
            if lead_organization == actor.organization_id:
                return True
        if actor.role == "INVESTIGATING_OFFICER" and case.investigating_officer_id == actor.id:
            return True
        return db.scalar(select(CaseAssignment.id).where(CaseAssignment.case_id == case.id,
                         CaseAssignment.user_id == actor.id, CaseAssignment.status == "ACTIVE")) is not None

    def can_view_document(self, db: Session, actor: AuthenticatedUser, document: Document) -> bool:
        if actor.clearance_level < document.classification_level:
            return False
        case = db.get(Case, document.case_id)
        if not case or not self.can_view_case(db, actor, case):
            return False
        if actor.role in {"ADMIN", "SUPERVISOR"}:
            return True
        if actor.role == "INVESTIGATING_OFFICER" and case.investigating_officer_id == actor.id:
            return True
        if actor.role in {"PROSECUTOR", "COURT_USER"}:
            return True
        grant = db.scalar(select(AccessGrant).where(
            AccessGrant.resource_type == "DOCUMENT",
            AccessGrant.resource_id == document.id,
            AccessGrant.subject_user_id == actor.id,
            AccessGrant.permissions == "READ",
            AccessGrant.status == "ACTIVE",
            AccessGrant.valid_from <= utc_now(),
            AccessGrant.expires_at > utc_now(),
        ))
        return grant is not None

    def can_view_evidence(self, db: Session, actor: AuthenticatedUser, evidence: Evidence) -> bool:
        if actor.clearance_level < evidence.classification_level:
            return False
        case = db.get(Case, evidence.case_id)
        if not case or not self.can_view_case(db, actor, case):
            return False
        linked_documents = list(db.scalars(select(Document).where(Document.evidence_id == evidence.id)))
        return not linked_documents or any(self.can_view_document(db, actor, document) for document in linked_documents)

    def require_document_read(self, db: Session, actor: AuthenticatedUser, document: Document) -> None:
        if not self.can_view_document(db, actor, document):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied by role, clearance, or grant policy")

    def can_upload(self, actor: AuthenticatedUser) -> bool:
        return actor.role in {"INVESTIGATING_OFFICER", "FSL_OFFICER", "SUPERVISOR", "ADMIN"}

    def require_upload(self, actor: AuthenticatedUser) -> None:
        if not self.can_upload(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role cannot ingest evidence")


policy_engine = PolicyEngine()
