from __future__ import annotations

import re
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Case, Document, DocumentChunk, DocumentVersion
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine


@dataclass(frozen=True)
class AuthorizedChunk:
    document_id: str
    document_version_id: str
    document_title: str
    document_type: str
    case_id: str
    page_number: int
    chunk_id: str
    text: str
    source_hash: str
    classification_level: int
    embedding: list[float] | None = None


def _metadata_text(document: Document) -> str:
    return (
        f"Document titled {document.title}. Document type {document.document_type}. "
        "No extracted searchable text is available for this document."
    )


class AuthorizedCorpus:
    """Resolves searchable chunks only after deterministic document authorization."""

    def for_case(self, db: Session, actor: AuthenticatedUser, case: Case) -> list[AuthorizedChunk]:
        documents = list(db.scalars(select(Document).where(Document.case_id == case.id)))
        chunks: list[AuthorizedChunk] = []
        for document in documents:
            if not policy_engine.can_view_document(db, actor, document):
                continue
            version = db.get(DocumentVersion, document.current_version_id) if document.current_version_id else None
            if version is None:
                continue
            indexed = list(db.scalars(select(DocumentChunk).where(
                DocumentChunk.document_version_id == version.id,
                DocumentChunk.classification_level <= actor.clearance_level,
            ).order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)))
            if indexed:
                chunks.extend(AuthorizedChunk(
                    document_id=document.id, document_version_id=version.id,
                    document_title=document.title, document_type=document.document_type,
                    case_id=case.id, page_number=item.page_number, chunk_id=item.id,
                    text=item.text, source_hash=item.source_hash,
                    classification_level=item.classification_level,
                    embedding=item.embedding,
                ) for item in indexed)
                continue
            text = _metadata_text(document)
            chunks.append(AuthorizedChunk(
                document_id=document.id,
                document_version_id=version.id,
                document_title=document.title,
                document_type=document.document_type,
                case_id=case.id,
                page_number=1,
                chunk_id=f"{version.id}:p1:c0",
                text=text,
                source_hash=version.sha256_original,
                classification_level=document.classification_level,
                embedding=None,
            ))
        return chunks


def tokens(value: str) -> set[str]:
    stop_words = {"a", "an", "and", "are", "did", "do", "for", "in", "is", "of", "the", "to", "what", "which", "with"}
    return set(re.findall(r"[a-z0-9-]+", value.lower())) - stop_words
