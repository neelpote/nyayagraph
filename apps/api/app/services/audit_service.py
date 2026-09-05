from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import AuditEvent
from ..security.auth import AuthenticatedUser


class AuditService:
    def record(self, db: Session, actor: AuthenticatedUser, *, action: str,
               resource_type: str, resource_id: str, case_id: str | None = None,
               decision: str = "ALLOWED", metadata: dict | None = None) -> AuditEvent:
        event = AuditEvent(actor_user_id=actor.id, organization_id=actor.organization_id,
                           action=action, resource_type=resource_type, resource_id=resource_id,
                           case_id=case_id, authorization_decision=decision,
                           metadata_json=metadata or {})
        db.add(event)
        db.commit()
        return event
