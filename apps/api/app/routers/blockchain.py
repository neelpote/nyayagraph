from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..security.auth import AuthenticatedUser, get_current_user
from ..services.merkle_service import MerkleCheckpointService

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


@router.post("/checkpoints")
def create_checkpoint(actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role not in {"ADMIN", "AUDITOR", "SUPERVISOR"}:
        raise HTTPException(status_code=403, detail="Role cannot create provenance checkpoints")
    return MerkleCheckpointService().create_checkpoint(db, actor.id)


@router.get("/merkle/{event_id}/proof")
def get_proof(event_id: str, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return MerkleCheckpointService().proof(db, actor, event_id)
