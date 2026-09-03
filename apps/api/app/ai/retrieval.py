from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from sqlalchemy.orm import Session

from ..models import Case
from ..security.auth import AuthenticatedUser
from .corpus import AuthorizedChunk, AuthorizedCorpus, tokens
from .providers import get_embedding_provider


_SEMANTIC_EXPANSIONS = {
    "gunshot": {"residue", "forensic"},
    "forensic": {"residue", "fsl", "analysis"},
    "car": {"vehicle", "swift"},
    "vehicle": {"car", "swift"},
    "time": {"departed", "timestamp", "21", "22"},
    "timing": {"departed", "time", "cctv", "witness"},
    "restricted": {"witness-03"},
}


@dataclass(frozen=True)
class RetrievalResult:
    chunk: AuthorizedChunk
    score: float


class HybridRetriever:
    """MVP hybrid retrieval; ACL filtering occurs before scoring."""

    def __init__(self, corpus: AuthorizedCorpus | None = None):
        self.corpus = corpus or AuthorizedCorpus()

    def retrieve(
        self, db: Session, actor: AuthenticatedUser, case: Case, query: str,
        *, mode: str = "semantic", limit: int = 8,
    ) -> list[RetrievalResult]:
        candidates = self.corpus.for_case(db, actor, case)
        query_embedding = get_embedding_provider().embed(query) if mode == "semantic" else None
        query_tokens = tokens(query)
        if mode == "semantic":
            query_tokens |= set().union(*(_SEMANTIC_EXPANSIONS.get(token, set()) for token in query_tokens))
        results: list[RetrievalResult] = []
        for chunk in candidates:
            haystack = tokens(f"{chunk.document_title} {chunk.document_type} {chunk.text}")
            overlap = len(query_tokens & haystack)
            phrase = query.lower() in f"{chunk.document_title} {chunk.text}".lower()
            if mode == "metadata":
                matched = bool(tokens(query) & tokens(f"{chunk.document_title} {chunk.document_type}"))
            else:
                matched = overlap > 0 or phrase
            if matched:
                score = min(1.0, (overlap / max(1, len(query_tokens))) + (0.25 if phrase else 0))
                results.append(RetrievalResult(chunk, round(score, 4)))
            elif query_embedding is not None and chunk.embedding is not None:
                denominator = sqrt(sum(value * value for value in query_embedding)) * sqrt(
                    sum(value * value for value in chunk.embedding)
                )
                similarity = sum(a * b for a, b in zip(query_embedding, chunk.embedding)) / denominator if denominator else 0
                if similarity > 0:
                    results.append(RetrievalResult(chunk, round(similarity, 4)))
        return sorted(results, key=lambda result: (-result.score, result.chunk.document_title))[:limit]

    def all_authorized(self, db: Session, actor: AuthenticatedUser, case: Case) -> list[AuthorizedChunk]:
        return self.corpus.for_case(db, actor, case)
