from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..database import get_db
from ..security.auth import AuthenticatedUser, get_current_user
from ..security.policy import policy_engine
from ..services.document_service import DocumentService
from ..repositories.core import DocumentRepository
from ..models import AuditEvent, Case, DocumentVersion, Evidence
from ..security.signatures import SignatureService
from ..security.encryption import EncryptionService
from ..storage.providers import storage_provider_for_reference

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/versions")
def list_document_versions(
    document_id: str,
    actor: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = DocumentRepository().by_id(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    policy_engine.require_document_read(db, actor, document)
    versions = list(db.scalars(select(DocumentVersion).where(
        DocumentVersion.document_id == document.id
    ).order_by(DocumentVersion.version_number)))
    signatures = SignatureService()
    return [{
        "id": version.id,
        "versionNumber": version.version_number,
        "sha256Original": version.sha256_original,
        "sha256Encrypted": version.sha256_encrypted,
        "previousVersionHash": version.previous_version_hash,
        "mimeType": version.mime_type,
        "sizeBytes": version.size_bytes,
        "createdBy": version.created_by,
        "createdAt": version.created_at,
        "changeReason": version.change_reason,
        "signatureVerified": signatures.verify_version(db, version),
    } for version in versions]


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    version_id: Optional[str] = Query(None),
    actor: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = DocumentRepository().by_id(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    policy_engine.require_document_read(db, actor, document)
    selected_id = version_id or document.current_version_id
    version = db.get(DocumentVersion, selected_id) if selected_id else None
    if not version or version.document_id != document.id:
        raise HTTPException(status_code=404, detail="Document version not found")
    try:
        encrypted = storage_provider_for_reference(version.storage_reference).retrieve(version.storage_reference)
        plaintext = EncryptionService().decrypt(encrypted, version.wrapped_dek)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Stored evidence failed authenticated decryption") from exc
    if EncryptionService.sha256_bytes(plaintext) != version.sha256_original:
        raise HTTPException(status_code=409, detail="Stored evidence hash verification failed")
    audit = AuditEvent(actor_user_id=actor.id, organization_id=actor.organization_id,
                       action="DOCUMENT_DOWNLOAD", resource_type="DOCUMENT_VERSION", resource_id=version.id,
                       case_id=document.case_id, authorization_decision="ALLOWED")
    db.add(audit)
    db.commit()
    safe_name = "".join(character for character in document.title if character.isalnum() or character in " ._-").strip() or "document"
    return Response(content=plaintext, media_type=version.mime_type,
                    headers={"Content-Disposition": f'attachment; filename="{safe_name[:120]}"',
                             "X-Content-Type-Options": "nosniff"})


@router.post("")
async def upload_document(
    case_id: str = Form(...), title: str = Form(""), document_type: str = Form("OTHER"),
    classification_level: int = Form(2), evidence_id: Optional[str] = Form(None), file: UploadFile = File(...),
    actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    policy_engine.require_upload(actor)
    case = db.get(Case, case_id)
    if not case or not policy_engine.can_view_case(db, actor, case):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Actor is not assigned to the target case")
    if classification_level < 1 or classification_level > 4:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Classification level must be between 1 and 4")
    if evidence_id:
        evidence = db.get(Evidence, evidence_id)
        if not evidence or evidence.case_id != case.id:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Evidence does not belong to the target case")
    result = await DocumentService().ingest_document(db, file=file, case_id=case_id, actor=actor, title=title,
        document_type=document_type, classification_level=classification_level, evidence_id=evidence_id)
    return {"documentId": result.document.id, "documentVersionId": result.version.id, "sha256Original": result.version.sha256_original,
            "sha256Encrypted": result.version.sha256_encrypted, "storagePolicy": result.document.storage_policy,
            "storageBackend": result.version.storage_reference.split("://", 1)[0].upper(),
            "provenance": {"mode": "DATABASE_DEV" if result.ledger_tx_id.startswith("dev-ledger-") else "FABRIC",
                           "transaction": result.ledger_tx_id}}


@router.post("/{document_id}/versions")
async def create_document_version(
    document_id: str, change_reason: str = Form(...), file: UploadFile = File(...),
    actor: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    policy_engine.require_upload(actor)
    document = DocumentRepository().by_id(db, document_id)
    if not document:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")
    policy_engine.require_document_read(db, actor, document)
    result = await DocumentService().create_version(db, document=document, file=file, actor=actor, change_reason=change_reason)
    return {"documentId": document.id, "documentVersionId": result.version.id, "versionNumber": result.version.version_number,
            "sha256Original": result.version.sha256_original, "sha256Encrypted": result.version.sha256_encrypted,
            "previousVersionHash": result.version.previous_version_hash,
            "storageBackend": result.version.storage_reference.split("://", 1)[0].upper(),
            "provenance": {"mode": "DATABASE_DEV" if result.ledger_tx_id.startswith("dev-ledger-") else "FABRIC",
                           "transaction": result.ledger_tx_id}}
