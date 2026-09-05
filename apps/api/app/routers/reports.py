from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..security.auth import AuthenticatedUser, get_current_user
from ..services.report_service import VerificationReportService

router = APIRouter(tags=["verification reports"])


@router.get("/cases/{case_number}/verification-report", response_class=HTMLResponse)
def verification_report(case_number: str, actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return VerificationReportService().generate(db, actor, case_number)


@router.get("/public/verify/{token}")
def public_verify(token: str, db: Session = Depends(get_db)):
    return VerificationReportService().public_verify(db, token)
