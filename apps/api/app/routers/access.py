from __future__ import annotations

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Case
from ..security.auth import AuthenticatedUser, get_current_user
from ..security.policy import policy_engine
from ..services.access_service import AccessService

router = APIRouter(prefix="/access", tags=["access"])


class GrantRequest(BaseModel):
    document_id: str
    subject_email: str
    expires_at: datetime
    reason: str = Field(min_length=10, max_length=500)
    permissions: str = "READ"


class BreakGlassRequest(BaseModel):
    document_id: str
    justification: str
    requested_scope: str
    minutes: int = 30


class RevokeRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


def dto(grant):
    return {"id": grant.id, "resourceType": grant.resource_type, "resourceId": grant.resource_id,
            "subjectUserId": grant.subject_user_id, "permissions": grant.permissions, "validFrom": grant.valid_from,
            "expiresAt": grant.expires_at, "reason": grant.reason, "status": grant.status,
            "isBreakGlass": grant.is_break_glass, "supervisorReviewRequired": grant.supervisor_review_required,
            "fabricTransaction": grant.fabric_tx_id}


@router.get("/grants")
def list_grants(case_number: Optional[str] = None, actor: AuthenticatedUser = Depends(get_current_user),
                db: Session = Depends(get_db)):
    case_id = None
    if case_number:
        case = db.scalar(select(Case).where(Case.case_number == case_number))
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        if not policy_engine.can_view_case(db, actor, case):
            raise HTTPException(status_code=403, detail="Case access denied")
        case_id = case.id
    return [dto(item) for item in AccessService().list_grants(db, actor, case_id=case_id)]


@router.post("/grants")
def create_grant(payload: GrantRequest, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return dto(AccessService().create_grant(db, actor, **payload.model_dump()))


@router.post("/break-glass")
def break_glass(payload: BreakGlassRequest, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return dto(AccessService().break_glass(db, actor, **payload.model_dump()))


@router.post("/grants/{grant_id}/revoke")
def revoke_grant(grant_id: str, payload: RevokeRequest, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return dto(AccessService().revoke(db, actor, grant_id, payload.reason))
