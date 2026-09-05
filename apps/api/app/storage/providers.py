from pathlib import Path
from typing import Protocol
import re
import httpx
from minio import Minio
from ..config import get_settings


class EvidenceStorageProvider(Protocol):
    def store(self, object_key: str, content: bytes, content_type: str) -> str: ...
    def retrieve(self, reference: str) -> bytes: ...
    def delete(self, reference: str) -> None: ...


class MinIOStorageProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.client = Minio(settings.minio_endpoint, access_key=settings.minio_access_key,
                            secret_key=settings.minio_secret_key, secure=settings.minio_secure)

    def store(self, object_key: str, content: bytes, content_type: str) -> str:
        from io import BytesIO
        if not self.client.bucket_exists(self.settings.minio_bucket_evidence):
            self.client.make_bucket(self.settings.minio_bucket_evidence)
        self.client.put_object(self.settings.minio_bucket_evidence, object_key, BytesIO(content), len(content), content_type)
        return f"minio://{self.settings.minio_bucket_evidence}/{object_key}"

    def retrieve(self, reference: str) -> bytes:
        _, rest = reference.split("://", 1)
        bucket, object_key = rest.split("/", 1)
        response = self.client.get_object(bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, reference: str) -> None:
        _, rest = reference.split("://", 1)
        bucket, object_key = rest.split("/", 1)
        self.client.remove_object(bucket, object_key)


class IPFSStorageProvider:
    """Stores only already-encrypted bytes in a configured private IPFS node."""

    def __init__(self, base_url: str | None = None, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        if not settings.ipfs_enabled:
            raise RuntimeError("IPFS storage is disabled")
        self.base_url = (base_url or settings.ipfs_api_url).rstrip("/")
        self.client = client or httpx.Client(timeout=15.0)

    @staticmethod
    def _cid(reference: str) -> str:
        cid = reference.removeprefix("ipfs://")
        if not re.fullmatch(r"[A-Za-z0-9]{32,120}", cid):
            raise ValueError("Invalid IPFS content identifier")
        return cid

    def store(self, object_key: str, content: bytes, content_type: str) -> str:
        response = self.client.post(
            f"{self.base_url}/api/v0/add",
            params={"pin": "true", "cid-version": "1"},
            files={"file": (object_key.rsplit("/", 1)[-1], content, content_type)},
        )
        response.raise_for_status()
        cid = response.json().get("Hash", "")
        self._cid(f"ipfs://{cid}")
        return f"ipfs://{cid}"

    def retrieve(self, reference: str) -> bytes:
        response = self.client.post(f"{self.base_url}/api/v0/cat", params={"arg": self._cid(reference)})
        response.raise_for_status()
        return response.content

    def delete(self, reference: str) -> None:
        response = self.client.post(f"{self.base_url}/api/v0/pin/rm", params={"arg": self._cid(reference)})
        response.raise_for_status()


class LocalEncryptedVault:
    """Explicit dev fallback for tests or an unavailable MinIO service."""
    root = Path("data/evidence")

    def store(self, object_key: str, content: bytes, content_type: str) -> str:
        path = self.root / object_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return f"local://{path}"

    def retrieve(self, reference: str) -> bytes:
        return Path(reference.removeprefix("local://")).read_bytes()

    def delete(self, reference: str) -> None:
        Path(reference.removeprefix("local://")).unlink(missing_ok=True)


def get_storage_provider() -> EvidenceStorageProvider:
    backend = get_settings().storage_backend.lower()
    if backend == "local":
        return LocalEncryptedVault()
    if backend == "ipfs":
        return IPFSStorageProvider()
    if backend == "minio":
        return MinIOStorageProvider()
    raise ValueError(f"Unsupported STORAGE_BACKEND: {backend}")


def storage_provider_for_reference(reference: str) -> EvidenceStorageProvider:
    if reference.startswith("local://"):
        return LocalEncryptedVault()
    if reference.startswith("minio://"):
        return MinIOStorageProvider()
    if reference.startswith("ipfs://"):
        return IPFSStorageProvider()
    raise ValueError("Unsupported evidence storage reference")
