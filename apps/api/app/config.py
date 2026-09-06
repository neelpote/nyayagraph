import base64
import os
import secrets
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    dev_mode: bool = True
    auth_mode: str = "dev_jwt"
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "nyayagraph"
    keycloak_client_id: str = "nyayagraph-web"
    keycloak_client_secret: str = ""
    oidc_issuer: str = "http://localhost:8080/realms/nyayagraph"
    oidc_jwks_url: str = "http://localhost:8080/realms/nyayagraph/protocol/openid-connect/certs"
    demo_password: str = ""
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./data/nyayagraph.db"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "nyayaadmin"
    minio_secret_key: str = "change_me"
    minio_bucket_evidence: str = "evidence"
    minio_secure: bool = False
    storage_backend: str = "minio"
    ipfs_enabled: bool = False
    ipfs_api_url: str = "http://localhost:5001"
    jwt_secret: str = ""
    master_kek_base64: str = ""
    kms_provider: str = "local"
    kms_url: str = ""
    kms_key_id: str = ""
    kms_bearer_token: str = ""
    signing_private_key_path: str = ""
    signing_public_key_path: str = ""
    fabric_enabled: bool = False
    enable_neo4j: bool = False
    public_chain_mode: str = "local"
    llm_provider: str = "demo"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    # Ollama-specific ? takes precedence over llm_base_url when provider=ollama.
    ollama_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    embedding_provider: str = "demo"
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "all-minilm"
    max_upload_bytes: int = 20 * 1024 * 1024
    malware_scan_enabled: bool = False
    malware_scan_host: str = ""
    malware_scan_port: int = 3310

    def kek(self) -> bytes:
        if self.master_kek_base64:
            key = base64.b64decode(self.master_kek_base64)
            if len(key) != 32:
                raise ValueError("MASTER_KEK_BASE64 must decode to exactly 32 bytes")
            return key
        if not self.dev_mode:
            raise ValueError("MASTER_KEK_BASE64 is required outside development")
        key_path = Path("data/keys/dev-kek.bin")
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(os.urandom(32))
        key = key_path.read_bytes()
        if len(key) != 32:
            raise ValueError("Development KEK file is invalid")
        return key

    def jwt_signing_key(self) -> str:
        known_defaults = {"development-only-change-me", "change_me", "replace_with_openssl_rand_hex_32"}
        if self.jwt_secret and self.jwt_secret not in known_defaults and len(self.jwt_secret) >= 32:
            return self.jwt_secret
        if not self.dev_mode:
            raise ValueError("A strong JWT_SECRET is required outside development")
        key_path = Path("data/keys/dev-jwt-secret.txt")
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            try:
                descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(secrets.token_urlsafe(48))
            except FileExistsError:
                pass
        key = key_path.read_text(encoding="utf-8").strip()
        if len(key) < 32:
            raise ValueError("Development JWT key file is invalid")
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()
