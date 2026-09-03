from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Document, Evidence
from ..repositories.core import CaseRepository
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine
from .retrieval import HybridRetriever
from .validation import citation_for


class SearchService:
    MODES = {"metadata", "fulltext", "semantic"}

    def __init__(self):
        self.retriever = HybridRetriever()

    def search(self, db: Session, actor: AuthenticatedUser, query: str, mode: str) -> list[dict]:
        if mode not in self.MODES:
            raise ValueError(f"Unsupported mode: {mode}")
        hits: list[dict] = []
        for case in CaseRepository().list(db):
            if not policy_engine.can_view_case(db, actor, case):
                continue
            if mode == "metadata":
                normalized = query.strip().lower()
                evidence_items = list(db.scalars(select(Evidence).where(Evidence.case_id == case.id)))
                authorized_chunks = self.retriever.all_authorized(db, actor, case)
                chunks_by_evidence = {}
                for chunk in authorized_chunks:
                    # Resolve through the real document record; the corpus itself carries no
                    # evidence identifier so it cannot widen authorization.
                    document = db.get(Document, chunk.document_id)
                    if document and document.evidence_id:
                        chunks_by_evidence.setdefault(document.evidence_id, chunk)
                for evidence in evidence_items:
                    if normalized not in {evidence.evidence_code.lower(), evidence.id.lower()}:
                        continue
                    source_chunk = chunks_by_evidence.get(evidence.id)
                    if source_chunk is None:
                        continue
                    hits.append({
                        "caseNumber": case.case_number,
                        "resourceType": "EVIDENCE",
                        "resourceId": evidence.id,
                        "evidenceCode": evidence.evidence_code,
                        "score": 1.0,
                        "excerpt": evidence.description,
                        "source": citation_for(source_chunk).model_dump(),
                    })
            for result in self.retriever.retrieve(db, actor, case, query, mode=mode, limit=20):
                hits.append({
                    "caseNumber": case.case_number,
                    "score": result.score,
                    "excerpt": result.chunk.text,
                    "source": citation_for(result.chunk).model_dump(),
                })
        return sorted(hits, key=lambda hit: (-hit["score"], hit["source"]["documentTitle"]))[:50]

    def natural_case_search(
        self, db: Session, actor: AuthenticatedUser, query: str, case_number: str | None,
    ) -> dict:
        hits = self.search(db, actor, query, "semantic")
        if case_number:
            hits = [hit for hit in hits if hit["caseNumber"] == case_number]
        return {
            "query": query,
            "status": "SUPPORTED" if hits else "INSUFFICIENT_AUTHORIZED_EVIDENCE",
            "results": hits,
        }
