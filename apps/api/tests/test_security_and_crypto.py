import base64
import json
import os
import pytest
os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
os.environ["MASTER_KEK_BASE64"] = base64.b64encode(b"a" * 32).decode()
from app.security.encryption import EncryptionService
from app.security.kms import LocalKekProvider
from app.config import Settings
from app.storage.transactional import track_storage_write
from app.security.malware import MalwareScanner
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def test_encryption_roundtrip():
    service = EncryptionService()
    encrypted, wrapped = service.encrypt(b"confidential evidence")
    assert encrypted != b"confidential evidence"
    assert service.decrypt(encrypted, wrapped) == b"confidential evidence"


def test_modified_bytes_have_different_hash():
    assert EncryptionService.sha256_bytes(b"original") != EncryptionService.sha256_bytes(b"modified")


def test_local_kek_is_rejected_outside_development(monkeypatch):
    monkeypatch.setattr("app.security.kms.get_settings", lambda: Settings(
        _env_file=None, dev_mode=False, master_kek_base64=base64.b64encode(b"a" * 32).decode()
    ))
    try:
        LocalKekProvider().wrap(b"d" * 32)
        assert False, "production must not use a process-local KEK"
    except RuntimeError as error:
        assert "disabled outside development" in str(error)


def test_wrapped_dek_envelope_retains_original_kms_key_id(monkeypatch):
    selected = []

    class Provider:
        provider_name = "http"

        def __init__(self, key_id):
            self.key_id = key_id

        def wrap(self, dek):
            return base64.b64encode(self.key_id.encode() + b":" + dek).decode()

        def unwrap(self, wrapped):
            value = base64.b64decode(wrapped)
            prefix = self.key_id.encode() + b":"
            assert value.startswith(prefix)
            return value[len(prefix):]

    current_key = ["evidence-key-v1"]

    def provider(provider_name=None, key_id=None):
        selected.append((provider_name, key_id))
        return Provider(key_id or current_key[0])

    monkeypatch.setattr("app.security.encryption.get_kms_provider", provider)
    wrapped = EncryptionService.wrap_dek(b"d" * 32)
    assert json.loads(wrapped)["keyId"] == "evidence-key-v1"
    current_key[0] = "evidence-key-v2"
    assert EncryptionService.unwrap_dek(wrapped) == b"d" * 32
    assert selected[-1] == ("http", "evidence-key-v1")


def test_rolled_back_ingestion_removes_new_storage_object(monkeypatch):
    deleted = []

    class Provider:
        def delete(self, reference):
            deleted.append(reference)

    monkeypatch.setattr("app.storage.transactional.storage_provider_for_reference", lambda _: Provider())
    with Session(create_engine("sqlite://")) as db:
        db.execute(text("SELECT 1"))
        track_storage_write(db, "minio://documents/case/document/v1.bin")
        db.rollback()
    assert deleted == ["minio://documents/case/document/v1.bin"]


def test_production_upload_fails_closed_without_malware_scanner(monkeypatch):
    monkeypatch.setattr("app.security.malware.get_settings", lambda: Settings(
        _env_file=None, app_env="production", dev_mode=False, malware_scan_enabled=False,
    ))
    with pytest.raises(HTTPException) as error:
        MalwareScanner().scan(b"untrusted upload")
    assert error.value.status_code == 503
