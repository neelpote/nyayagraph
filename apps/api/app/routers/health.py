import socket
import subprocess  # nosec B404
import urllib.request
from urllib.parse import urlparse
from fastapi import APIRouter
from sqlalchemy import text
from ..database import engine
from ..config import get_settings

router = APIRouter(tags=["operations"])


@router.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"
    settings = get_settings()
    def reachable(host: str, port: int) -> str:
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return "ok"
        except OSError:
            return "unavailable"
    redis = urlparse(settings.redis_url)
    minio_host, minio_port = settings.minio_endpoint.rsplit(":", 1)
    ipfs = "disabled"
    if settings.ipfs_enabled:
        try:
            request = urllib.request.Request(f"{settings.ipfs_api_url.rstrip('/')}/api/v0/id", data=b"", method="POST")
            with urllib.request.urlopen(request, timeout=1):  # nosec B310
                ipfs = "ok"
        except OSError:
            ipfs = "unavailable"
    fabric = "disabled"
    if settings.fabric_enabled:
        try:
            result = subprocess.run(["peer", "version"], capture_output=True, timeout=2, check=False)  # nosec B603 B607
            fabric = "ok" if result.returncode == 0 else "unavailable"
        except (OSError, subprocess.TimeoutExpired):
            fabric = "unavailable"
    return {"api": "ok", "database": database,
            "postgres": database if engine.dialect.name == "postgresql" else "disabled",
            "redis": reachable(redis.hostname or "localhost", redis.port or 6379),
            "minio": "disabled" if settings.storage_backend == "local" else reachable(minio_host, int(minio_port)),
            "ipfs": ipfs,
            "neo4j": "disabled" if not settings.enable_neo4j else "configured",
            "fabric": fabric,
            "publicChain": settings.public_chain_mode}
