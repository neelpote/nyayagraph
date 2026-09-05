import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..blockchain.ledger import get_ledger
from ..models import AuditEvent, Case, Evidence, EvidenceCustodyEvent, Notification, Organization, User
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine
from ..utils.time import utc_now


class CustodyService:
    ALLOWED_ROLES = {"INVESTIGATING_OFFICER", "FSL_OFFICER", "SUPERVISOR", "ADMIN"}

    def transfer(self, db: Session, actor: AuthenticatedUser, evidence_id: str, *, to_org_id: str,
                 purpose: str, location: str) -> EvidenceCustodyEvent:
        evidence = db.scalar(select(Evidence).where((Evidence.id == evidence_id) | (Evidence.evidence_code == evidence_id)))
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")
        if actor.role not in self.ALLOWED_ROLES:
            raise HTTPException(status_code=403, detail="Role cannot transfer custody")
        case = db.get(Case, evidence.case_id)
        if not case or not policy_engine.can_view_case(db, actor, case):
            raise HTTPException(status_code=403, detail="Actor is not assigned to this case")
        if actor.role not in {"SUPERVISOR", "ADMIN"} and evidence.current_custodian_org_id != actor.organization_id:
            raise HTTPException(status_code=403, detail="Actor organization is not the current custodian")
        target = db.get(Organization, to_org_id)
        if not target or target.status != "ACTIVE":
            raise HTTPException(status_code=404, detail="Target organization not found")
        previous = db.scalar(select(EvidenceCustodyEvent).where(EvidenceCustodyEvent.evidence_id == evidence.id).order_by(EvidenceCustodyEvent.event_time.desc()))
        now = utc_now()
        canonical = json.dumps({"actor": actor.id, "evidence": evidence.id, "event": "TRANSFERRED", "from": evidence.current_custodian_org_id,
                                "location": location, "purpose": purpose, "timestamp": now.isoformat(timespec="microseconds"), "to": to_org_id},
                               sort_keys=True, separators=(",", ":"))
        event_hash = hashlib.sha256(((previous.event_hash if previous else "") + canonical).encode()).hexdigest()
        event = EvidenceCustodyEvent(evidence_id=evidence.id, event_type="TRANSFERRED", from_org_id=evidence.current_custodian_org_id,
                                     to_org_id=to_org_id, actor_user_id=actor.id, purpose=purpose, location=location,
                                     event_time=now, previous_event_hash=previous.event_hash if previous else None, event_hash=event_hash)
        db.add(event); db.flush()
        ledger = get_ledger()
        if hasattr(ledger, "transfer_custody"):
            event.fabric_tx_id = ledger.transfer_custody(db, evidence_id=evidence.id, event_id=event.id,
                                                         event_hash=event_hash, actor_id=actor.id, case_id=evidence.case_id,
                                                         previous_hash=event.previous_event_hash or "",
                                                         from_org=event.from_org_id or "", to_org=to_org_id)
        evidence.current_custodian_org_id = to_org_id
        db.add(AuditEvent(actor_user_id=actor.id, organization_id=actor.organization_id, action="TRANSFER_CUSTODY",
                          resource_type="EVIDENCE", resource_id=evidence.id, case_id=evidence.case_id,
                          authorization_decision="ALLOWED", metadata_json={"event_id": event.id, "to_org_id": to_org_id, "event_hash": event_hash}))
        target_users = list(db.scalars(select(User).where(User.organization_id == to_org_id, User.status == "ACTIVE")))
        for user in target_users:
            db.add(Notification(user_id=user.id, case_id=evidence.case_id, type="CUSTODY_TRANSFER", title=f"Evidence {evidence.evidence_code} transferred",
                                message=f"Custody transferred for {purpose}."))
        db.commit(); db.refresh(event)
        return event
