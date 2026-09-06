import socket
import subprocess  # nosec B404
import urllib.request
from urllib.parse import urlparse
from fastapi import APIRouter
from sqlalchemy import text
from ..database import engine
from ..config import get_settings

router = APIRouter(tags=["operations"])


@router.get("/health/llm")
def llm_health():
    """Check whether the configured LLM provider is reachable and ready.

    Returns provider name, model, and status without exposing secrets or
    configuration values.  Does not require authentication ? it reveals
    only connectivity state, not case data.
    """
    settings = get_settings()
    provider_name = (settings.llm_provider or "demo").lower().strip()

    if provider_name in {"demo", "deterministic", ""}:
        return {
            "provider": "demo",
            "model": "deterministic",
            "status": "healthy",
            "detail": "Running in deterministic demo mode. No external model required.",
        }

    try:
        from ..ai.llm.factory import get_llm_provider
        provider = get_llm_provider()
        return provider.health()
    except Exception as exc:
        # Never expose stack traces ? return a safe summary.
        return {
            "provider": provider_name,
            "model": settings.llm_model or "unknown",
            "status": "unhealthy",
            "detail": "LLM provider could not be initialised. Check OLLAMA_BASE_URL and LLM_MODEL.",
        }


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
