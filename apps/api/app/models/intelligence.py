from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base
from ..utils.time import utc_now
from .core import uid


class CaseParticipant(Base):
    __tablename__ = "case_participants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    participant_type: Mapped[str] = mapped_column(String(80))
    is_confidential: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384).with_variant(JSON(), "sqlite"), nullable=True)
    classification_level: Mapped[int] = mapped_column(Integer, default=2)
    allowed_roles: Mapped[list] = mapped_column(JSON, default=list)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    analysis_type: Mapped[str] = mapped_column(String(80))
    model_name: Mapped[str] = mapped_column(String(160))
    model_version: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    status: Mapped[str] = mapped_column(String(40), default="COMPLETED")


class AIClaim(Base):
    __tablename__ = "ai_claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("ai_analyses.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(80))
    claim_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AIClaimSource(Base):
    __tablename__ = "ai_claim_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    claim_id: Mapped[str] = mapped_column(ForeignKey("ai_claims.id"), index=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("document_versions.id"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("document_chunks.id"))
    quote_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retrieval_score: Mapped[float] = mapped_column(Float)


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    canonical_name: Mapped[str] = mapped_column(String(250))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    classification_level: Mapped[int] = mapped_column(Integer, default=2)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(100))
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    source_document_version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    event_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class CaseTimelineEvent(Base):
    __tablename__ = "case_timeline_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    source_document_version_id: Mapped[str | None] = mapped_column(ForeignKey("document_versions.id"), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class ComplianceRequirement(Base):
    __tablename__ = "compliance_requirements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text)
    case_type: Mapped[str] = mapped_column(String(100))
    required_document_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(30))
