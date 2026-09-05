from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from ..database import get_db
from ..security.auth import AuthenticatedUser, get_current_user
from ..services.verification_service import VerificationService
from ..services.audit_service import AuditService
from ..models import Document, DocumentVersion
from ..config import get_settings
from ..services.document_service import read_upload_limited

router = APIRouter(prefix="/verification", tags=["verification"])


@router.post("/document")
async def verify_document(document_version_id: str = Form(...), file: UploadFile = File(...),
                          actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)):
    content = await read_upload_limited(file, get_settings().max_upload_bytes)
    result = VerificationService().verify_document(db, actor, document_version_id, content)
    version = db.get(DocumentVersion, document_version_id)
    document = db.get(Document, version.document_id) if version else None
    AuditService().record(db, actor, action="VERIFY_DOCUMENT", resource_type="DOCUMENT_VERSION",
                          resource_id=document_version_id, case_id=document.case_id if document else None,
                          metadata={"status": result["status"]})
    return result
