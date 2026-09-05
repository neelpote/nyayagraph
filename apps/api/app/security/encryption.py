from __future__ import annotations

import hashlib
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .kms import get_kms_provider


class EncryptionService:
    """AES-256-GCM envelope encryption backed by the configured KMS provider."""

    @staticmethod
    def sha256_bytes(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def generate_dek() -> bytes:
        return AESGCM.generate_key(bit_length=256)

    @staticmethod
    def wrap_dek(dek: bytes) -> str:
        provider = get_kms_provider()
        return json.dumps({"v": 1, "provider": provider.provider_name, "keyId": provider.key_id,
                           "wrapped": provider.wrap(dek)}, separators=(",", ":"))

    @staticmethod
    def unwrap_dek(wrapped: str) -> bytes:
        try:
            envelope = json.loads(wrapped)
        except json.JSONDecodeError:
            # Existing development records predate the versioned envelope.
            return get_kms_provider().unwrap(wrapped)
        if envelope.get("v") != 1 or not all(isinstance(envelope.get(field), str)
                                             for field in ("provider", "keyId", "wrapped")):
            raise ValueError("Invalid wrapped DEK envelope")
        return get_kms_provider(envelope["provider"], envelope["keyId"]).unwrap(envelope["wrapped"])

    def encrypt(self, plaintext: bytes) -> tuple[bytes, str]:
        dek = self.generate_dek()
        nonce = os.urandom(12)
        ciphertext = AESGCM(dek).encrypt(nonce, plaintext, b"nyayagraph-evidence-v1")
        return nonce + ciphertext, self.wrap_dek(dek)

    def decrypt(self, encrypted: bytes, wrapped_dek: str) -> bytes:
        dek = self.unwrap_dek(wrapped_dek)
        return AESGCM(dek).decrypt(encrypted[:12], encrypted[12:], b"nyayagraph-evidence-v1")
