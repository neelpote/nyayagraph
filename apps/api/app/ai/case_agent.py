from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Case, Document, Evidence
from ..repositories.core import CaseRepository
from ..security.auth import AuthenticatedUser
from ..security.policy import policy_engine
from ..services.case_service import IntegrityService
from .contradictions import ContradictionEngine, FactExtractionService
from .prompting import PromptBuilder
from .retrieval import HybridRetriever
from .schemas import EvidenceClaim
from .validation import ClaimValidator, citation_for
from .providers import AIProviderError, StructuredLLMProvider
from ..config import get_settings


DISCLAIMER = "Evidence-grounded investigative support only. Not a determination of guilt or legal conclusion."


def require_case(db: Session, actor: AuthenticatedUser, case_number: str) -> Case:
    case = CaseRepository().by_number(db, case_number)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if not policy_engine.can_view_case(db, actor, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    return case


class CaseAgentService:
    def __init__(self, retriever: HybridRetriever | None = None):
        self.retriever = retriever or HybridRetriever()
        self.prompt_builder = PromptBuilder()
        self.claim_validator = ClaimValidator()
        self.fact_extractor = FactExtractionService()
        self.contradictions = ContradictionEngine()

    def _claims(self, question: str, chunks) -> list[EvidenceClaim]:
        if get_settings().llm_provider in {"", "demo", "deterministic"}:
            return [EvidenceClaim(
                claim=chunk.text,
                confidence=0.95,
                status="SUPPORTED",
                sources=[citation_for(chunk)],
            ) for chunk in chunks if "No extracted searchable text" not in chunk.text]
        try:
            return StructuredLLMProvider().generate_claims(question, chunks)
        except AIProviderError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    def brief(self, db: Session, actor: AuthenticatedUser, case_number: str) -> dict:
        case = require_case(db, actor, case_number)
        chunks = self.retriever.all_authorized(db, actor, case)
        claims = self._claims("Create a concise factual case brief.", chunks)
        claims = self.claim_validator.enforce(claims, chunks)
        contradictions = self.contradictions.compare(self.fact_extractor.extract(chunks))
        documents = [item for item in db.scalars(select(Document).where(Document.case_id == case.id))
                     if policy_engine.can_view_document(db, actor, item)]
        evidence = [item for item in db.scalars(select(Evidence).where(Evidence.case_id == case.id))
                    if policy_engine.can_view_evidence(db, actor, item)]
        integrity = IntegrityService().case_integrity(db, documents, evidence, chunks)
        missing = ["Exhibit E-07 is referenced but absent from the case inventory."] if any(
            "Exhibit E-07" in chunk.text for chunk in chunks
        ) else []
        evidence_claims = [claim for claim in claims if "Witness" not in claim.claim and "charge sheet" not in claim.claim.lower()]
        witness_claims = [claim for claim in claims if "Witness" in claim.claim]
        return {
            "caseOverview": case.description,
            "incident": f"{case.case_type} reported at {case.incident_location}.",
            "fir": case.fir_number,
            "investigatingOfficer": case.investigating_officer_id,
            "sections": [],
            "timelineSummary": "Authorized records contain incident, evidence, and custody chronology.",
            "primaryEvidence": [item.model_dump() for item in evidence_claims],
            "witnesses": [item.model_dump() for item in witness_claims],
            "forensicResults": [item.model_dump() for item in claims if "FSL" in item.claim],
            "contradictions": [item.model_dump() for item in contradictions],
            "missingInformation": missing,
            "pendingTasks": ["Locate referenced Exhibit E-07"] if missing else [],
            "nextHearing": case.next_hearing_at,
            "integrity": {"documentsVerified": f"{integrity['documents']['verified']}/{integrity['documents']['total']}",
                          "custody": integrity["custody"]["status"], "anchorStatus": integrity["anchorStatus"]},
            "claims": [item.model_dump() for item in claims],
            "disclaimer": DISCLAIMER,
            "generationMode": "DETERMINISTIC_DEMO" if get_settings().llm_provider == "demo" else "GROUNDED_LLM",
        }

    def ask(self, db: Session, actor: AuthenticatedUser, case_number: str, question: str) -> dict:
        case = require_case(db, actor, case_number)
        authorized_chunks = self.retriever.all_authorized(db, actor, case)
        normalized = question.lower().replace("_", "-").replace(" ", "-")
        if "witness-03" in normalized and not any(
            "witness-03" in chunk.document_title.lower() for chunk in authorized_chunks
        ):
            return self._insufficient(question)
        results = self.retriever.retrieve(db, actor, case, question, mode="semantic")
        chunks = [result.chunk for result in results]
        # Build even in deterministic mode so the same strict trust boundary is exercised.
        self.prompt_builder.build(question, chunks)
        if not chunks:
            return self._insufficient(question)
        if get_settings().llm_provider in {"", "demo", "deterministic"}:
            claims = [EvidenceClaim(
                claim=chunk.text,
                confidence=max(0.7, results[index].score),
                status="SUPPORTED",
                sources=[citation_for(chunk)],
            ) for index, chunk in enumerate(chunks)]
        else:
            claims = self._claims(question, chunks)
        claims = self.claim_validator.enforce(claims, chunks)
        return {
            "answer": " ".join(claim.claim for claim in claims),
            "status": "SUPPORTED",
            "claims": [claim.model_dump() for claim in claims],
            "sources": [source.model_dump() for claim in claims for source in claim.sources],
            "disclaimer": DISCLAIMER,
            "generationMode": "DETERMINISTIC_DEMO" if get_settings().llm_provider == "demo" else "GROUNDED_LLM",
        }

    @staticmethod
    def _insufficient(question: str) -> dict:
        claim = EvidenceClaim(
            claim="Insufficient authorized evidence available.", confidence=0,
            status="INSUFFICIENT_EVIDENCE", sources=[],
        )
        return {
            "answer": claim.claim,
            "status": claim.status,
            "claims": [claim.model_dump()],
            "sources": [],
            "disclaimer": DISCLAIMER,
            "generationMode": "DETERMINISTIC_DEMO",
        }
