from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base
from ..utils.time import utc_now


def uid() -> str:
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    type: Mapped[str] = mapped_column(String(80))
    fabric_msp_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    external_identity_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(80), index=True)
    clearance_level: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    demo_password: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    organization: Mapped[Organization] = relationship()


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_number: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    case_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(80))
    jurisdiction: Mapped[str] = mapped_column(String(160))
    classification_level: Mapped[int] = mapped_column(Integer, default=2)
    fir_number: Mapped[str] = mapped_column(String(120))
    police_station: Mapped[str] = mapped_column(String(160))
    investigating_officer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    incident_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    incident_location: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    next_hearing_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class CaseAssignment(Base):
    __tablename__ = "case_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_role: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    evidence_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    evidence_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    classification_level: Mapped[int] = mapped_column(Integer, default=2)
    capture_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    capture_location: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    current_custodian_org_id: Mapped[Optional[str]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(60), default="REGISTERED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    evidence_id: Mapped[Optional[str]] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    classification_level: Mapped[int] = mapped_column(Integer, default=2)
    storage_policy: Mapped[str] = mapped_column(String(80), default="PRIVATE_VAULT")
    current_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_document_version_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    sha256_original: Mapped[str] = mapped_column(String(64), index=True)
    sha256_encrypted: Mapped[str] = mapped_column(String(64))
    previous_version_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    storage_reference: Mapped[str] = mapped_column(String(500))
    wrapped_dek: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    ocr_status: Mapped[str] = mapped_column(String(30), default="NOT_REQUIRED")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    change_reason: Mapped[str] = mapped_column(String(500), default="Initial ingestion")
    fabric_tx_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class EvidenceCustodyEvent(Base):
    __tablename__ = "evidence_custody_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80))
    from_org_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    to_org_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(500))
    location: Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    event_time: Mapped[datetime] = mapped_column(DateTime)
    previous_event_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64))
    fabric_tx_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class AccessGrant(Base):
    __tablename__ = "access_grants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    subject_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    subject_org_id: Mapped[Optional[str]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    permissions: Mapped[str] = mapped_column(String(120), default="READ")
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    granted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    requested_scope: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_break_glass: Mapped[bool] = mapped_column(Boolean, default=False)
    supervisor_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    fabric_tx_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(36))
    case_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    authorization_decision: Mapped[str] = mapped_column(String(30))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    topic: Mapped[str] = mapped_column(String(120), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MerkleBatch(Base):
    __tablename__ = "merkle_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    merkle_root: Mapped[str] = mapped_column(String(64))
    event_count: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(20), default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    public_tx_hash: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    public_chain_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    anchor_status: Mapped[str] = mapped_column(String(40), default="PENDING")


class MerkleLeaf(Base):
    __tablename__ = "merkle_leaves"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("merkle_batches.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    leaf_hash: Mapped[str] = mapped_column(String(64))
    leaf_index: Mapped[int] = mapped_column(Integer)


class BlockchainAnchor(Base):
    __tablename__ = "blockchain_anchors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("merkle_batches.id"), unique=True)
    chain_type: Mapped[str] = mapped_column(String(60))
    chain_id: Mapped[str] = mapped_column(String(80))
    contract_address: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    transaction_hash: Mapped[str] = mapped_column(String(200))
    block_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    anchor_timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Signature(Base):
    __tablename__ = "signatures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    artifact_type: Mapped[str] = mapped_column(String(80))
    artifact_id: Mapped[str] = mapped_column(String(36), index=True)
    signer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    algorithm: Mapped[str] = mapped_column(String(60), default="ED25519")
    public_key_reference: Mapped[str] = mapped_column(String(300))
    signature_value: Mapped[str] = mapped_column(Text)
    signed_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(1000))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    hash_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    version_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    anchor_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
