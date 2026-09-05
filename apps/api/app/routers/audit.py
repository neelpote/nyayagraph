from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AuditEvent, Case, CaseAssignment, User
from ..security.auth import AuthenticatedUser, get_current_user
from ..security.policy import policy_engine

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_events(case_id: Optional[str] = None, case_number: Optional[str] = None,
                      action: Optional[str] = None, limit: int = Query(100, ge=1, le=500),
                      actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role not in {"AUDITOR", "ADMIN", "SUPERVISOR", "INVESTIGATING_OFFICER", "COURT_USER", "PROSECUTOR"}:
        raise HTTPException(status_code=403, detail="Role cannot query audit events")
    if case_number:
        case = db.scalar(select(Case).where(Case.case_number == case_number))
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        if not policy_engine.can_view_case(db, actor, case):
            raise HTTPException(status_code=403, detail="Case access denied")
        case_id = case.id
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if case_id:
        query = query.where(AuditEvent.case_id == case_id)
    if action:
        query = query.where(AuditEvent.action == action)
    if actor.role in {"AUDITOR", "SUPERVISOR"}:
        organization_cases = select(Case.id).join(
            User, User.id == Case.investigating_officer_id
        ).where(User.organization_id == actor.organization_id)
        query = query.where(AuditEvent.case_id.in_(organization_cases))
    elif actor.role != "ADMIN":
        assigned_cases = select(CaseAssignment.case_id).where(CaseAssignment.user_id == actor.id, CaseAssignment.status == "ACTIVE")
        if actor.role == "INVESTIGATING_OFFICER":
            assigned_cases = select(Case.id).where((Case.investigating_officer_id == actor.id) | (Case.id.in_(assigned_cases)))
        query = query.where(AuditEvent.case_id.in_(assigned_cases))
    events = list(db.scalars(query))
    return [{"id": item.id, "actorUserId": item.actor_user_id, "organizationId": item.organization_id,
             "action": item.action, "resourceType": item.resource_type, "resourceId": item.resource_id,
             "caseId": item.case_id, "authorizationDecision": item.authorization_decision,
             "createdAt": item.created_at, "metadata": item.metadata_json} for item in events]
