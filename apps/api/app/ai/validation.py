from __future__ import annotations

from .corpus import AuthorizedChunk
from .schemas import EvidenceClaim, SourceCitation


def citation_for(chunk: AuthorizedChunk) -> SourceCitation:
    return SourceCitation(
        documentId=chunk.document_id,
        documentVersionId=chunk.document_version_id,
        documentTitle=chunk.document_title,
        page=chunk.page_number,
        chunkId=chunk.chunk_id,
        sourceHash=chunk.source_hash,
    )


class CitationValidator:
    def validate(self, claim: EvidenceClaim, authorized_chunks: list[AuthorizedChunk]) -> bool:
        allowed = {(item.chunk_id, item.source_hash, item.document_id) for item in authorized_chunks}
        return bool(claim.sources) and all(
            (source.chunkId, source.sourceHash, source.documentId) in allowed for source in claim.sources
        )


class ClaimValidator:
    """Rejects factual claims that do not carry valid authorized citations."""

    def __init__(self):
        self.citations = CitationValidator()

    def enforce(self, claims: list[EvidenceClaim], authorized_chunks: list[AuthorizedChunk]) -> list[EvidenceClaim]:
        result: list[EvidenceClaim] = []
        for claim in claims:
            if claim.status == "SUPPORTED" and not self.citations.validate(claim, authorized_chunks):
                result.append(EvidenceClaim(
                    claim="Insufficient authorized evidence available.",
                    confidence=0,
                    status="INSUFFICIENT_EVIDENCE",
                    sources=[],
                ))
            elif claim.status == "INSUFFICIENT_EVIDENCE":
                result.append(claim.model_copy(update={"sources": []}))
            else:
                result.append(claim)
        return result
