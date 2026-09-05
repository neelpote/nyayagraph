"""Citation validation and faithfulness gate.

Pipeline:
  Qwen answer ? EvidenceClaim list
      ?
  CitationValidator  ? every citation must point to an authorised chunk
      ?
  ClaimValidator (faithfulness gate)
      ? SUPPORTED with no valid citations ? UNSUPPORTED
      ? UNSUPPORTED claims ? surface as UNSUPPORTED (not hidden)
      ? INSUFFICIENT_EVIDENCE ? pass through unchanged
"""
from __future__ import annotations

from .corpus import AuthorizedChunk
from .schemas import ClaimStatus, EvidenceClaim, SourceCitation


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
            (source.chunkId, source.sourceHash, source.documentId) in allowed
            for source in claim.sources
        )


class ClaimValidator:
    """Faithfulness gate: enforces that every SUPPORTED claim has verified citations.

    Rules:
    - SUPPORTED with no sources or invalid sources ? UNSUPPORTED.
    - PARTIALLY_SUPPORTED / CONFLICTING ? keep as-is (sources may be partial).
    - UNSUPPORTED ? pass through; the frontend surfaces these as review flags.
    - INSUFFICIENT_EVIDENCE ? pass through with sources cleared.
    """

    def __init__(self) -> None:
        self.citations = CitationValidator()

    def enforce(
        self, claims: list[EvidenceClaim], authorized_chunks: list[AuthorizedChunk]
    ) -> list[EvidenceClaim]:
        result: list[EvidenceClaim] = []
        for claim in claims:
            if claim.status == "INSUFFICIENT_EVIDENCE":
                result.append(claim.model_copy(update={"sources": []}))

            elif claim.status == "SUPPORTED":
                if not self.citations.validate(claim, authorized_chunks):
                    # Claim asserts support but citations don't check out ?
                    # demote rather than expose a fabricated fact.
                    result.append(EvidenceClaim(
                        claim=claim.claim,
                        confidence=0.0,
                        status="UNSUPPORTED",
                        sources=[],
                    ))
                else:
                    result.append(claim)

            elif claim.status in {"PARTIALLY_SUPPORTED", "CONFLICTING"}:
                # Keep with whatever valid citations exist; strip invalid ones.
                if authorized_chunks:
                    allowed = {(c.chunk_id, c.source_hash, c.document_id) for c in authorized_chunks}
                    valid_sources = [
                        s for s in claim.sources
                        if (s.chunkId, s.sourceHash, s.documentId) in allowed
                    ]
                    result.append(claim.model_copy(update={"sources": valid_sources}))
                else:
                    result.append(claim.model_copy(update={"sources": []}))

            else:
                # UNSUPPORTED ? surface as-is (no citations expected).
                result.append(claim.model_copy(update={"sources": []}))

        return result


def overall_trust_status(claims: list[EvidenceClaim]) -> ClaimStatus:
    """Derive a single trust status from a list of validated claims.

    Used to populate the top-level ``trust_status`` field in API responses.
    """
    if not claims:
        return "INSUFFICIENT_EVIDENCE"
    statuses = {c.status for c in claims}
    if statuses == {"SUPPORTED"}:
        return "SUPPORTED"
    if "INSUFFICIENT_EVIDENCE" in statuses and len(statuses) == 1:
        return "INSUFFICIENT_EVIDENCE"
    if "CONFLICTING" in statuses:
        return "CONFLICTING"
    if "UNSUPPORTED" in statuses:
        return "PARTIALLY_SUPPORTED"
    return "PARTIALLY_SUPPORTED"
