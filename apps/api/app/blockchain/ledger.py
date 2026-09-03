from __future__ import annotations

import hashlib
import json
import os
import re
# Fabric peer CLI is an explicit provider boundary and is always invoked without a shell.
import subprocess  # nosec B404
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AuditEvent, OutboxEvent


class LedgerUnavailableError(RuntimeError):
    """Raised when the configured Fabric peer cannot commit a transaction."""


class ProvenanceLedger(Protocol):
    def register_case(self, db: Session, *, case_id: str, case_commitment: str, actor_id: str, **metadata: Any) -> str: ...
    def register_document(self, db: Session, *, document_version_id: str, case_id: str, hash_value: str, actor_id: str, **metadata: Any) -> str: ...
    def register_evidence(self, db: Session, *, evidence_id: str, case_id: str, hash_value: str, actor_id: str, **metadata: Any) -> str: ...
    def create_version(self, db: Session, *, document_version_id: str, case_id: str, hash_value: str, previous_hash: str, actor_id: str, **metadata: Any) -> str: ...
    def transfer_custody(self, db: Session, *, evidence_id: str, event_hash: str, actor_id: str, **metadata: Any) -> str: ...
    def grant_access(self, db: Session, *, grant_id: str, resource_id: str, actor_id: str, **metadata: Any) -> str: ...
    def revoke_access(self, db: Session, *, grant_id: str, resource_id: str, actor_id: str, **metadata: Any) -> str: ...
    def record_access(self, db: Session, *, event_id: str, resource_id: str, actor_id: str, **metadata: Any) -> str: ...
    def record_checkpoint(self, db: Session, *, batch_id: str, root: str, metadata_commitment: str, actor_id: str, **metadata: Any) -> str: ...
    def verify_artifact(self, *, artifact_id: str, hash_value: str) -> bool: ...


def _commitment(value: str | None) -> str:
    """Return a one-way commitment so identifiers do not leave the application DB."""
    return hashlib.sha256((value or "").encode()).hexdigest()


class DatabaseDevLedger:
    """Auditable fallback. UI/API must call this a development ledger, never Fabric."""

    ledger_name = "DATABASE_DEV"

    def _record(self, db: Session, *, action: str, resource_type: str, resource_id: str,
                actor_id: str | None, payload: dict[str, Any], case_id: str | None = None,
                synchronization_pending: bool = False) -> str:
        canonical = json.dumps({"action": action, **payload}, sort_keys=True, separators=(",", ":"))
        tx_id = "dev-ledger-" + hashlib.sha256(canonical.encode()).hexdigest()[:24]
        db.add(AuditEvent(actor_user_id=actor_id, action=action, resource_type=resource_type,
                          resource_id=resource_id, case_id=case_id, authorization_decision="ALLOWED",
                          metadata_json={"ledger": self.ledger_name, "transaction_id": tx_id,
                                         "synchronization_pending": synchronization_pending, **payload}))
        return tx_id

    def register_case(self, db: Session, *, case_id: str, case_commitment: str, actor_id: str, **metadata: Any) -> str:
        return self._record(db, action="REGISTER_CASE", resource_type="CASE", resource_id=case_id,
                            actor_id=actor_id, case_id=case_id, payload={"case_commitment": case_commitment, **metadata})

    def register_document(self, db: Session, *, document_version_id: str, case_id: str, hash_value: str,
                          actor_id: str, **metadata: Any) -> str:
        return self._record(db, action="REGISTER_DOCUMENT", resource_type="DOCUMENT_VERSION",
                            resource_id=document_version_id, actor_id=actor_id, case_id=case_id,
                            payload={"hash": hash_value, **metadata})

    def register_evidence(self, db: Session, *, evidence_id: str, case_id: str, hash_value: str,
                          actor_id: str, **metadata: Any) -> str:
        return self._record(db, action="REGISTER_EVIDENCE", resource_type="EVIDENCE", resource_id=evidence_id,
                            actor_id=actor_id, case_id=case_id, payload={"hash": hash_value, **metadata})

    def create_version(self, db: Session, *, document_version_id: str, case_id: str, hash_value: str,
                       previous_hash: str, actor_id: str, **metadata: Any) -> str:
        return self._record(db, action="CREATE_VERSION", resource_type="DOCUMENT_VERSION",
                            resource_id=document_version_id, actor_id=actor_id, case_id=case_id,
                            payload={"hash": hash_value, "previous_hash": previous_hash, **metadata})

    def transfer_custody(self, db: Session, *, evidence_id: str, event_hash: str, actor_id: str,
                         case_id: str | None = None, **metadata: Any) -> str:
        return self._record(db, action="TRANSFER_CUSTODY", resource_type="EVIDENCE", resource_id=evidence_id,
                            actor_id=actor_id, case_id=case_id, payload={"event_hash": event_hash, **metadata})

    def grant_access(self, db: Session, *, grant_id: str, resource_id: str, actor_id: str,
                     case_id: str | None = None, **metadata: Any) -> str:
        return self._record(db, action="GRANT_ACCESS", resource_type="ACCESS_GRANT", resource_id=grant_id,
                            actor_id=actor_id, case_id=case_id,
                            payload={"resource_commitment": _commitment(resource_id), **metadata})

    def revoke_access(self, db: Session, *, grant_id: str, resource_id: str, actor_id: str,
                      case_id: str | None = None, **metadata: Any) -> str:
        return self._record(db, action="REVOKE_ACCESS", resource_type="ACCESS_GRANT", resource_id=grant_id,
                            actor_id=actor_id, case_id=case_id,
                            payload={"resource_commitment": _commitment(resource_id), **metadata})

    def record_access(self, db: Session, *, event_id: str, resource_id: str, actor_id: str,
                      case_id: str | None = None, **metadata: Any) -> str:
        return self._record(db, action="RECORD_ACCESS", resource_type="AUDIT_EVENT", resource_id=event_id,
                            actor_id=actor_id, case_id=case_id,
                            payload={"resource_commitment": _commitment(resource_id), **metadata})

    def record_checkpoint(self, db: Session, *, batch_id: str, root: str, metadata_commitment: str,
                          actor_id: str, **metadata: Any) -> str:
        return self._record(db, action="RECORD_CHECKPOINT", resource_type="MERKLE_BATCH", resource_id=batch_id,
                            actor_id=actor_id, payload={"root": root, "metadata_commitment": metadata_commitment, **metadata})

    def verify_artifact(self, *, artifact_id: str, hash_value: str) -> bool:
        # DB callers compare the authoritative artifact row; this validates only the
        # development-ledger input shape and never claims public verification.
        return bool(artifact_id and re.fullmatch(r"[0-9a-fA-F]{64}", hash_value))


@dataclass(frozen=True)
class FabricPeerConfig:
    peer_binary: str
    channel: str
    chaincode: str
    orderer: str | None
    tls_root_cert: str | None
    peer_addresses: tuple[str, ...] = ()
    peer_tls_root_certs: tuple[str, ...] = ()

    @classmethod
    def from_environment(cls) -> "FabricPeerConfig":
        addresses = tuple(value.strip() for value in os.getenv("FABRIC_PEER_ADDRESSES", "").split(",") if value.strip())
        tls_roots = tuple(value.strip() for value in os.getenv("FABRIC_PEER_TLS_ROOT_CERTS", "").split(",") if value.strip())
        if tls_roots and len(addresses) != len(tls_roots):
            raise LedgerUnavailableError("FABRIC_PEER_ADDRESSES and FABRIC_PEER_TLS_ROOT_CERTS must have equal lengths")
        return cls(peer_binary=os.getenv("FABRIC_PEER_BINARY", "peer"),
                   channel=os.getenv("FABRIC_CHANNEL", "justicechannel"),
                   chaincode=os.getenv("FABRIC_CHAINCODE", "nyayagraph"),
                   orderer=os.getenv("FABRIC_ORDERER_ADDRESS"),
                   tls_root_cert=os.getenv("FABRIC_ORDERER_TLS_CA"),
                   peer_addresses=addresses, peer_tls_root_certs=tls_roots)


class FabricProvenanceLedger:
    """Fabric peer-CLI adapter using an externally mounted MSP identity.

    Only hashes, commitments, organization identifiers, and version numbers are
    submitted. CORE_PEER_* environment variables select the invoking identity.
    """

    def __init__(self, config: FabricPeerConfig | None = None) -> None:
        self.config = config or FabricPeerConfig.from_environment()

    def _invoke(self, operation: str, *args: str) -> str:
        invocation = json.dumps({"Args": [operation, *args]}, separators=(",", ":"))
        command = [self.config.peer_binary, "chaincode", "invoke", "-C", self.config.channel,
                   "-n", self.config.chaincode, "-c", invocation, "--waitForEvent"]
        if self.config.orderer:
            command.extend(["-o", self.config.orderer])
        if self.config.tls_root_cert:
            command.extend(["--tls", "--cafile", self.config.tls_root_cert])
        for index, address in enumerate(self.config.peer_addresses):
            command.extend(["--peerAddresses", address])
            if self.config.peer_tls_root_certs:
                command.extend(["--tlsRootCertFiles", self.config.peer_tls_root_certs[index]])
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)  # nosec B603
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LedgerUnavailableError(f"Fabric peer unavailable: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[-500:]
            raise LedgerUnavailableError(f"Fabric transaction failed: {detail}")
        match = re.search(r"txid \[([0-9a-fA-F]+)\]", result.stderr + result.stdout)
        if not match:
            raise LedgerUnavailableError("Fabric peer committed without returning a transaction ID")
        return match.group(1)

    def _query(self, operation: str, *args: str) -> str:
        invocation = json.dumps({"Args": [operation, *args]}, separators=(",", ":"))
        command = [self.config.peer_binary, "chaincode", "query", "-C", self.config.channel,
                   "-n", self.config.chaincode, "-c", invocation]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)  # nosec B603
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LedgerUnavailableError(f"Fabric peer unavailable: {exc}") from exc
        if result.returncode != 0:
            raise LedgerUnavailableError(f"Fabric query failed: {(result.stderr or result.stdout).strip()[-500:]}")
        return result.stdout.strip()

    @staticmethod
    def _actor(actor_id: str) -> str:
        return _commitment(actor_id)

    @staticmethod
    def _org(metadata: dict[str, Any]) -> str:
        return str(metadata.get("organization", metadata.get("organization_id",
                   os.getenv("FABRIC_MSP_ID", "PoliceMSP"))))

    def register_case(self, db: Session, *, case_id: str, case_commitment: str, actor_id: str, **metadata: Any) -> str:
        return self._invoke("RegisterCase", _commitment(case_id), case_commitment, self._org(metadata), self._actor(actor_id))

    def register_document(self, db: Session, *, document_version_id: str, case_id: str, hash_value: str,
                          actor_id: str, **metadata: Any) -> str:
        return self._invoke("RegisterDocument", document_version_id, _commitment(case_id), hash_value,
                            str(metadata.get("version", metadata.get("version_number", 1))), self._org(metadata), self._actor(actor_id),
                            str(metadata.get("previous_hash", "")))

    def register_evidence(self, db: Session, *, evidence_id: str, case_id: str, hash_value: str,
                          actor_id: str, **metadata: Any) -> str:
        return self._invoke("RegisterEvidence", evidence_id, _commitment(case_id), hash_value,
                            self._org(metadata), self._actor(actor_id))

    def create_version(self, db: Session, *, document_version_id: str, case_id: str, hash_value: str,
                       previous_hash: str, actor_id: str, **metadata: Any) -> str:
        return self._invoke("CreateVersion", document_version_id, _commitment(case_id), hash_value,
                            str(metadata.get("version", metadata.get("version_number", 1))), self._org(metadata), self._actor(actor_id), previous_hash)

    def transfer_custody(self, db: Session, *, evidence_id: str, event_hash: str, actor_id: str, **metadata: Any) -> str:
        return self._invoke("TransferCustody", evidence_id, event_hash,
                            str(metadata.get("previous_hash", metadata.get("previous_event_hash", ""))),
                            str(metadata.get("from_org", metadata.get("from_org_id", ""))),
                            str(metadata.get("to_org", metadata.get("to_org_id", ""))), self._actor(actor_id))

    def grant_access(self, db: Session, *, grant_id: str, resource_id: str, actor_id: str, **metadata: Any) -> str:
        subject_commitment = str(metadata.get("subject_commitment") or _commitment(str(metadata.get("subject_user_id", ""))))
        expires_commitment = str(metadata.get("expires_commitment") or _commitment(str(metadata.get("expires_at", ""))))
        return self._invoke("GrantAccess", grant_id, _commitment(resource_id),
                            subject_commitment, expires_commitment, self._actor(actor_id))

    def revoke_access(self, db: Session, *, grant_id: str, resource_id: str, actor_id: str, **metadata: Any) -> str:
        return self._invoke("RevokeAccess", grant_id, _commitment(resource_id), self._actor(actor_id))

    def record_access(self, db: Session, *, event_id: str, resource_id: str, actor_id: str, **metadata: Any) -> str:
        return self._invoke("RecordAccess", event_id, _commitment(resource_id),
                            str(metadata.get("decision", metadata.get("authorization_decision", "ALLOWED"))), self._actor(actor_id))

    def record_checkpoint(self, db: Session, *, batch_id: str, root: str, metadata_commitment: str,
                          actor_id: str, **metadata: Any) -> str:
        return self._invoke("RecordCheckpoint", batch_id, root, metadata_commitment, self._actor(actor_id))

    def verify_artifact(self, *, artifact_id: str, hash_value: str) -> bool:
        return self._query("VerifyArtifact", artifact_id, hash_value).lower() == "true"


class ResilientProvenanceLedger:
    """Attempts Fabric, then records an explicit pending-sync event in the dev ledger."""

    def __init__(self, primary: FabricProvenanceLedger, fallback: DatabaseDevLedger) -> None:
        self.primary = primary
        self.fallback = fallback

    def __getattr__(self, name: str):
        primary_method = getattr(self.primary, name)
        fallback_method = getattr(self.fallback, name)
        if name == "verify_artifact":
            def verify(**kwargs: Any) -> bool:
                try:
                    return primary_method(**kwargs)
                except LedgerUnavailableError:
                    return False
            return verify

        def invoke(db: Session, **kwargs: Any) -> str:
            if get_settings().app_env == "production":
                db.add(OutboxEvent(topic=f"fabric.{name}", payload_json=kwargs))
                return fallback_method(db, synchronization_pending=True, **kwargs)
            try:
                return primary_method(db, **kwargs)
            except LedgerUnavailableError:
                db.add(OutboxEvent(topic=f"fabric.{name}", payload_json=kwargs))
                # The transaction remains operationally recorded but the returned ID
                # is visibly a development-ledger ID, never a fabricated Fabric ID.
                # The outbox row commits atomically with the domain change and can be
                # retried after connectivity returns.
                return fallback_method(db, synchronization_pending=True, **kwargs)
        return invoke


def get_ledger() -> ProvenanceLedger:
    if get_settings().fabric_enabled:
        return ResilientProvenanceLedger(FabricProvenanceLedger(), DatabaseDevLedger())
    return DatabaseDevLedger()
