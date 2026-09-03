from __future__ import annotations

import base64
import json
import os
from urllib.parse import quote
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings


class LocalKekProvider:
    """Development-only envelope-key provider."""

    provider_name = "local"
    key_id = "dev-local-kek-v1"

    def wrap(self, dek: bytes) -> str:
        settings = get_settings()
        if not settings.dev_mode:
            raise RuntimeError("Local KEK provider is disabled outside development")
        nonce = os.urandom(12)
        encrypted = AESGCM(settings.kek()).encrypt(nonce, dek, b"nyayagraph-dek-v1")
        return base64.b64encode(nonce + encrypted).decode()

    def unwrap(self, wrapped: str) -> bytes:
        settings = get_settings()
        if not settings.dev_mode:
            raise RuntimeError("Local KEK provider is disabled outside development")
        raw = base64.b64decode(wrapped, validate=True)
        return AESGCM(settings.kek()).decrypt(raw[:12], raw[12:], b"nyayagraph-dek-v1")


class HttpKmsProvider:
    """Adapter for an approved KMS/HSM gateway; plaintext DEKs never enter the database."""

    provider_name = "http"

    def __init__(self, key_id: str | None = None) -> None:
        settings = get_settings()
        if not settings.kms_url or not settings.kms_key_id:
            raise RuntimeError("KMS_URL and KMS_KEY_ID are required")
        if not settings.dev_mode and not settings.kms_url.startswith("https://"):
            raise RuntimeError("Production KMS_URL must use HTTPS")
        self.base_url = settings.kms_url.rstrip("/")
        self.key_id = key_id or settings.kms_key_id
        self.token = settings.kms_bearer_token

    def _call(self, operation: str, value: str) -> str:
        body = json.dumps({"value": value, "context": "nyayagraph-evidence-v1"}).encode()
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(
            f"{self.base_url}/v1/keys/{quote(self.key_id, safe='')}/{operation}",
            data=body,
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=10) as response:  # nosec B310 - operator-controlled KMS endpoint
            result = json.load(response)
        if not isinstance(result.get("value"), str):
            raise RuntimeError("KMS returned an invalid response")
        return result["value"]

    def wrap(self, dek: bytes) -> str:
        return self._call("wrap", base64.b64encode(dek).decode())

    def unwrap(self, wrapped: str) -> bytes:
        return base64.b64decode(self._call("unwrap", wrapped), validate=True)


def get_kms_provider(provider_name: str | None = None, key_id: str | None = None):
    provider = (provider_name or get_settings().kms_provider).lower()
    if provider in {"http", "nic_kms", "hsm_gateway"}:
        return HttpKmsProvider(key_id=key_id)
    if provider == "local":
        if key_id and key_id != LocalKekProvider.key_id:
            raise RuntimeError(f"Unknown local KEK identifier: {key_id}")
        return LocalKekProvider()
    raise RuntimeError(f"Unsupported KMS provider: {provider}")
