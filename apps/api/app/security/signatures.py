import base64
import hashlib
from pathlib import Path
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import get_settings
from ..models import DocumentVersion, Signature


class SignatureService:
    """Service attestation of the artifact hash and recorded submitting actor."""

    ALGORITHM = "ED25519_SERVER_ATTESTATION_V1"

    def _private_key(self) -> Ed25519PrivateKey:
        settings = get_settings()
        if settings.signing_private_key_path:
            key = serialization.load_pem_private_key(Path(settings.signing_private_key_path).read_bytes(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("Configured signing key must be Ed25519")
            return key
        if not settings.dev_mode:
            raise ValueError("SIGNING_PRIVATE_KEY_PATH is required outside development")
        seed = hashlib.sha256(settings.kek() + b"nyayagraph-ed25519-signing-v1").digest()
        return Ed25519PrivateKey.from_private_bytes(seed)

    def _public_key(self) -> Ed25519PublicKey:
        path = get_settings().signing_public_key_path
        key = serialization.load_pem_public_key(Path(path).read_bytes()) if path else self._private_key().public_key()
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("Configured signing key must be Ed25519")
        return key

    def sign_version(self, db: Session, version: DocumentVersion, signer_user_id: str) -> Signature:
        private_key = self._private_key()
        public_bytes = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        payload = self._payload(version, signer_user_id)
        signature_bytes = private_key.sign(payload)
        signature = Signature(artifact_type="DOCUMENT_VERSION", artifact_id=version.id, signer_user_id=signer_user_id,
                              algorithm=self.ALGORITHM, public_key_reference=base64.b64encode(public_bytes).decode(),
                              signature_value=base64.b64encode(signature_bytes).decode(), signed_hash=version.sha256_original)
        db.add(signature)
        return signature

    def verify_version(self, db: Session, version: DocumentVersion) -> bool:
        signature = db.scalar(select(Signature).where(Signature.artifact_type == "DOCUMENT_VERSION", Signature.artifact_id == version.id).order_by(Signature.created_at.desc()))
        if not signature or signature.signed_hash != version.sha256_original or signature.algorithm != self.ALGORITHM:
            return False
        try:
            key = self._public_key()
            trusted_public_bytes = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            if base64.b64decode(signature.public_key_reference) != trusted_public_bytes:
                return False
            key.verify(base64.b64decode(signature.signature_value), self._payload(version, signature.signer_user_id))
            return True
        except (InvalidSignature, ValueError, TypeError, OSError):
            return False

    @staticmethod
    def _payload(version: DocumentVersion, actor_id: str) -> bytes:
        return f"nyayagraph-server-attestation-v1:{version.id}:{actor_id}:{version.sha256_original}".encode()
