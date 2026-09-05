from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError
import fitz
from ..ai.ingestion import TextExtractionService
from ..ai.providers import get_embedding_provider
from ..models import CaseTimelineEvent, Document, DocumentChunk, DocumentVersion
from ..security.auth import AuthenticatedUser
from ..security.encryption import EncryptionService
from ..security.signatures import SignatureService
from ..security.malware import MalwareScanner
from ..storage.providers import LocalEncryptedVault, get_storage_provider
from ..storage.transactional import track_storage_write
from ..blockchain.ledger import get_ledger


ALLOWED_MIME = {"application/pdf", "text/plain", "image/jpeg", "image/png"}
ALLOWED_SUFFIX = {".pdf", ".txt", ".jpg", ".jpeg", ".png"}
MIME_BY_SUFFIX = {".pdf": "application/pdf", ".txt": "text/plain", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
MAX_PDF_PAGES = 500
MAX_IMAGE_PIXELS = 40_000_000


async def read_upload_limited(file: UploadFile, max_size: int) -> bytes:
    content = await file.read(max_size + 1)
    if not content or len(content) > max_size:
        raise HTTPException(status_code=422, detail="File is empty or exceeds upload limit")
    return content


@dataclass
class IngestionResult:
    document: Document
    version: DocumentVersion
    ledger_tx_id: str
    duplicate: bool = False


class FileValidator:
    def validate(self, file: UploadFile, content: bytes, max_size: int) -> None:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIX or file.content_type not in ALLOWED_MIME or MIME_BY_SUFFIX.get(suffix) != file.content_type:
            raise HTTPException(status_code=422, detail="Only PDF, TXT, JPG and PNG uploads are allowed")
        if not content or len(content) > max_size:
            raise HTTPException(status_code=422, detail="File is empty or exceeds upload limit")
        if content.startswith(b"PK\x03\x04"):
            raise HTTPException(status_code=422, detail="Archive uploads are not supported")
        if suffix == ".pdf" and (not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]):
            raise HTTPException(status_code=422, detail="Malformed PDF structure")
        if suffix == ".pdf":
            try:
                with fitz.open(stream=content, filetype="pdf") as document:
                    if document.page_count < 1 or document.page_count > MAX_PDF_PAGES:
                        raise HTTPException(status_code=422, detail=f"PDF must contain 1?{MAX_PDF_PAGES} pages")
                    for page in document:
                        page.get_text("text")
            except (fitz.FileDataError, RuntimeError, ValueError) as error:
                raise HTTPException(status_code=422, detail="Malformed PDF structure") from error
        if suffix == ".txt":
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise HTTPException(status_code=422, detail="Text files must be valid UTF-8") from error
            if b"\x00" in content:
                raise HTTPException(status_code=422, detail="Text file contains binary data")
        if suffix in {".jpg", ".jpeg", ".png"}:
            try:
                with Image.open(BytesIO(content)) as image:
                    if image.format not in ({"JPEG"} if suffix in {".jpg", ".jpeg"} else {"PNG"}):
                        raise HTTPException(status_code=422, detail="Image signature does not match its extension")
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise HTTPException(status_code=422, detail="Image dimensions exceed the safe processing limit")
                    image.verify()
            except (UnidentifiedImageError, OSError) as error:
                raise HTTPException(status_code=422, detail="Malformed image file") from error


class DocumentService:
    def __init__(self) -> None:
        self.validator = FileValidator()
        self.crypto = EncryptionService()

    async def ingest_document(self, db: Session, *, file: UploadFile, case_id: str, actor: AuthenticatedUser,
                              title: str, document_type: str, classification_level: int, evidence_id: str | None = None,
                              change_reason: str = "Initial ingestion") -> IngestionResult:
        from ..config import get_settings
        content = await read_upload_limited(file, get_settings().max_upload_bytes)
        self.validator.validate(file, content, get_settings().max_upload_bytes)
        MalwareScanner().scan(content)
        original_hash = self.crypto.sha256_bytes(content)
        duplicate = db.scalar(select(DocumentVersion).join(Document).where(
            Document.case_id == case_id, DocumentVersion.sha256_original == original_hash
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail={"message": "Exact duplicate detected", "document_version_id": duplicate.id})
        encrypted, wrapped_dek = self.crypto.encrypt(content)
        encrypted_hash = self.crypto.sha256_bytes(encrypted)
        document = Document(case_id=case_id, evidence_id=evidence_id, title=title or file.filename or "Untitled evidence",
                            document_type=document_type, classification_level=classification_level,
                            created_by=actor.id, storage_policy="PRIVATE_VAULT")
        db.add(document)
        db.flush()
        object_key = f"{case_id}/{document.id}/v1.bin"
        provider = get_storage_provider()
        try:
            reference = provider.store(object_key, encrypted, "application/octet-stream")
        except Exception:
            if not get_settings().dev_mode:
                raise HTTPException(status_code=503, detail="Evidence vault is unavailable")
            reference = LocalEncryptedVault().store(object_key, encrypted, "application/octet-stream")
        track_storage_write(db, reference)
        version = DocumentVersion(document_id=document.id, version_number=1, sha256_original=original_hash,
                                  sha256_encrypted=encrypted_hash, storage_reference=reference, wrapped_dek=wrapped_dek,
                                  mime_type=file.content_type or "application/octet-stream", size_bytes=len(content),
                                  created_by=actor.id, change_reason=change_reason)
        db.add(version)
        db.flush()
        self._index_text(db, version, case_id, content, file.content_type or "application/octet-stream", classification_level)
        SignatureService().sign_version(db, version, actor.id)
        document.current_version_id = version.id
        tx_id = get_ledger().register_document(db, document_version_id=version.id, case_id=case_id,
                                                hash_value=original_hash, actor_id=actor.id,
                                                version=version.version_number, organization_id=actor.organization_id)
        version.fabric_tx_id = tx_id
        db.commit()
        db.refresh(document)
        db.refresh(version)
        return IngestionResult(document=document, version=version, ledger_tx_id=tx_id)

    async def create_version(self, db: Session, *, document: Document, file: UploadFile, actor: AuthenticatedUser,
                             change_reason: str) -> IngestionResult:
        from ..config import get_settings
        document = db.scalar(select(Document).where(Document.id == document.id).with_for_update())
        current = db.get(DocumentVersion, document.current_version_id) if document and document.current_version_id else None
        if not current:
            raise HTTPException(status_code=409, detail="Document has no current version")
        content = await read_upload_limited(file, get_settings().max_upload_bytes)
        self.validator.validate(file, content, get_settings().max_upload_bytes)
        MalwareScanner().scan(content)
        original_hash = self.crypto.sha256_bytes(content)
        if original_hash == current.sha256_original:
            raise HTTPException(status_code=409, detail={"message": "New version is identical to the current version", "document_version_id": current.id})
        encrypted, wrapped_dek = self.crypto.encrypt(content)
        encrypted_hash = self.crypto.sha256_bytes(encrypted)
        version_number = current.version_number + 1
        object_key = f"{document.case_id}/{document.id}/v{version_number}.bin"
        try:
            reference = get_storage_provider().store(object_key, encrypted, "application/octet-stream")
        except Exception:
            if not get_settings().dev_mode:
                raise HTTPException(status_code=503, detail="Evidence vault is unavailable")
            reference = LocalEncryptedVault().store(object_key, encrypted, "application/octet-stream")
        track_storage_write(db, reference)
        version = DocumentVersion(document_id=document.id, version_number=version_number, sha256_original=original_hash,
                                  sha256_encrypted=encrypted_hash, previous_version_hash=current.sha256_original,
                                  storage_reference=reference, wrapped_dek=wrapped_dek,
                                  mime_type=file.content_type or "application/octet-stream", size_bytes=len(content),
                                  created_by=actor.id, change_reason=change_reason)
        db.add(version); db.flush()
        self._index_text(db, version, document.case_id, content, file.content_type or "application/octet-stream", document.classification_level)
        SignatureService().sign_version(db, version, actor.id)
        document.current_version_id = version.id
        tx_id = get_ledger().create_version(db, document_version_id=version.id, case_id=document.case_id,
                                            hash_value=original_hash, previous_hash=current.sha256_original, actor_id=actor.id,
                                            version=version.version_number, organization_id=actor.organization_id)
        version.fabric_tx_id = tx_id
        db.commit(); db.refresh(version); db.refresh(document)
        return IngestionResult(document=document, version=version, ledger_tx_id=tx_id)

    @staticmethod
    def _index_text(db: Session, version: DocumentVersion, case_id: str, content: bytes,
                    mime_type: str, classification_level: int) -> None:
        extracted = TextExtractionService().extract(content, mime_type)
        for item in extracted:
            db.add(DocumentChunk(document_version_id=version.id, case_id=case_id,
                                 page_number=item.page_number, chunk_index=item.chunk_index,
                                 text=item.text, embedding=get_embedding_provider().embed(item.text),
                                 classification_level=classification_level,
                                 allowed_roles=[], source_hash=version.sha256_original))
        db.add(CaseTimelineEvent(case_id=case_id, event_type="DOCUMENT_INGESTED",
                                 title="Document version registered",
                                 description=f"Version {version.version_number} was encrypted, hashed and stored.",
                                 event_time=version.created_at, source_document_version_id=version.id,
                                 confidence=1.0))
