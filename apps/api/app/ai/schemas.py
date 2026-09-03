from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


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
    status: Literal["SUPPORTED", "INSUFFICIENT_EVIDENCE"]
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
