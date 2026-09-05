from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..ai.case_agent import CaseAgentService
from ..ai.schemas import AskRequest
from ..database import get_db
from ..security.auth import AuthenticatedUser, get_current_user
from ..services.audit_service import AuditService
from ..repositories.core import CaseRepository

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/case/{case_number}/brief")
def case_brief(
    case_number: str,
    actor: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = CaseAgentService().brief(db, actor, case_number)
    case = CaseRepository().by_number(db, case_number)
    AuditService().record(db, actor, action="AI_CASE_BRIEF", resource_type="CASE",
                          resource_id=case.id, case_id=case.id,
                          metadata={"claim_count": len(result.get("claims", []))})
    return result


@router.post("/case/{case_number}/ask")
def ask_case(
    case_number: str,
    request: AskRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = CaseAgentService().ask(db, actor, case_number, request.question)
    case = CaseRepository().by_number(db, case_number)
    AuditService().record(db, actor, action="AI_QUERY", resource_type="CASE", resource_id=case.id,
                          case_id=case.id,
                          metadata={"status": result.get("status"), "source_count": len(result.get("sources", []))})
    return result
