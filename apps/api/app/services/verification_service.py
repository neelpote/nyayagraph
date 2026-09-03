from fastapi import HTTPException
from sqlalchemy.orm import Session
from ..repositories.core import DocumentRepository
from ..security.auth import AuthenticatedUser
from ..security.encryption import EncryptionService
from ..security.policy import policy_engine
from ..security.signatures import SignatureService
from ..storage.providers import storage_provider_for_reference


class VerificationService:
    def verify_registered_version(self, db: Session, version) -> dict:
        try:
            encrypted = storage_provider_for_reference(version.storage_reference).retrieve(version.storage_reference)
            encrypted_hash_valid = EncryptionService.sha256_bytes(encrypted) == version.sha256_encrypted
            plaintext = EncryptionService().decrypt(encrypted, version.wrapped_dek) if encrypted_hash_valid else b""
            original_hash_valid = encrypted_hash_valid and EncryptionService.sha256_bytes(plaintext) == version.sha256_original
            signature_valid = SignatureService().verify_version(db, version)
            return {"hashVerified": original_hash_valid, "encryptedHashVerified": encrypted_hash_valid,
                    "signatureVerified": signature_valid, "verified": original_hash_valid and signature_valid}
        except Exception:
            return {"hashVerified": False, "encryptedHashVerified": False, "signatureVerified": False, "verified": False}

    def verify_document(self, db: Session, actor: AuthenticatedUser, document_version_id: str, content: bytes) -> dict:
        version = DocumentRepository().version(db, document_version_id)
        if not version:
            raise HTTPException(status_code=404, detail="Document version not found")
        document = DocumentRepository().by_id(db, version.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        policy_engine.require_document_read(db, actor, document)
        actual = EncryptionService.sha256_bytes(content)
        if actual == version.sha256_original:
            return {"status": "VERIFIED", "documentVersionId": version.id, "hashVerified": True}
        return {"status": "HASH_MISMATCH", "documentVersionId": version.id, "hashVerified": False,
                "expected": version.sha256_original, "actual": actual}
