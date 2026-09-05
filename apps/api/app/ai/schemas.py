from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

# Claim support statuses ? ordered from strongest to weakest evidence backing.
ClaimStatus = Literal[
    "SUPPORTED",             # Every factual assertion is directly backed by a retrieved source.
    "PARTIALLY_SUPPORTED",   # Some assertions are backed; others lack direct evidence.
    "CONFLICTING",           # Sources provide materially contradictory information.
    "UNSUPPORTED",           # No retrieved source backs the assertion.
    "INSUFFICIENT_EVIDENCE", # Authorised evidence pool is empty or does not address the question.
]


class SourceCitation(BaseModel):
    documentId: str
    documentVersionId: str
    documentTitle: str
    page: int = 1
    chunkId: str
    sourceHash: str


class EvidenceClaim(BaseModel):
    claim: str
    confidence: float = Field(ge=0, le=1)
    status: ClaimStatus
    sources: list[SourceCitation] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class CaseSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    caseNumber: Optional[str] = None


class ContradictionDTO(BaseModel):
    type: str
    subject: str
    values: list[dict]
    explanation: str
    sources: list[SourceCitation]
