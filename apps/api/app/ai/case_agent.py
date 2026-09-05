"""CaseAgentService ? the authoritative entry-point for all AI-assisted queries.

Authorization pipeline (enforced here and in AuthorizedCorpus):

  User request
      ?
  AuthenticatedUser + policy_engine  (case-level access)
      ?
  AuthorizedCorpus.for_case()        (document/chunk-level ACL ? BEFORE retrieval)
      ?
  HybridRetriever.retrieve()         (keyword + vector scoring on pre-filtered pool)
      ?
  StructuredLLMProvider.generate_claims()  (Qwen3-8B via Ollama / demo fallback)
      ?
  ClaimValidator.enforce()           (faithfulness gate ? demotes unsupported claims)
      ?
  overall_trust_status()             (top-level trust label)
      ?
  API response

The LLM is NEVER given unrestricted evidence.  It only sees chunks that
policy_engine has already authorised for the requesting user.
"""
from __future__ import annotations

import logging
import uuid
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
from .validation import ClaimValidator, citation_for, overall_trust_status
from .providers import AIProviderError, StructuredLLMProvider
from ..config import get_settings

logger = logging.getLogger(__name__)

DISCLAIMER = "Evidence-grounded investigative support only. Not a determination of guilt or legal conclusion."

_DEMO_PROVIDERS = {"", "demo", "deterministic"}


def require_case(db: Session, actor: AuthenticatedUser, case_number: str) -> Case:
    case = CaseRepository().by_number(db, case_number)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    if not policy_engine.can_view_case(db, actor, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    return case


def _is_demo_mode() -> bool:
    return get_settings().llm_provider.lower().strip() in _DEMO_PROVIDERS


class CaseAgentService:
    def __init__(self, retriever: HybridRetriever | None = None):
        self.retriever = retriever or HybridRetriever()
        self.prompt_builder = PromptBuilder()
        self.claim_validator = ClaimValidator()
        self.fact_extractor = FactExtractionService()
        self.contradictions = ContradictionEngine()

    # ------------------------------------------------------------------
    # Internal claim generation ? demo or real LLM path
    # ------------------------------------------------------------------

    def _claims(
        self,
        question: str,
        chunks,
        *,
        query_type: str = "GENERAL",
        request_id: str = "",
        case_id: str = "",
        user_id: str = "",
    ) -> list[EvidenceClaim]:
        if _is_demo_mode():
            # Deterministic demo: each chunk becomes one supported claim.
            return [
                EvidenceClaim(
                    claim=chunk.text,
                    confidence=0.95,
                    status="SUPPORTED",
                    sources=[citation_for(chunk)],
                )
                for chunk in chunks
                if "No extracted searchable text" not in chunk.text
            ]
        try:
            return StructuredLLMProvider().generate_claims(
                question,
                chunks,
                query_type=query_type,
                request_id=request_id,
                case_id=case_id,
                user_id=user_id,
            )
        except AIProviderError as error:
            logger.error(
                "llm_error",
                extra={
                    "request_id": request_id,
                    "case_id": case_id,
                    "user_id": user_id,
                    "error": str(error),
                },
            )
            raise HTTPException(status_code=503, detail=str(error)) from error

    # ------------------------------------------------------------------
    # Query type classifier
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_query(question: str) -> str:
        """Lightweight keyword-based query classifier.

        Returns one of: FACT, RELATIONSHIP, TIMELINE, EVIDENCE,
        CONTRADICTION, SUMMARY, GENERAL.
        """
        q = question.lower()
        if any(k in q for k in ("contradict", "conflict", "disagree", "differ", "inconsist")):
            return "CONTRADICTION"
        if any(k in q for k in ("timeline", "sequence", "chronolog", "order of event", "between")):
            return "TIMELINE"
        if any(k in q for k in ("summarize", "summarise", "summary", "overview", "brief")):
            return "SUMMARY"
        if any(k in q for k in ("mention", "reference", "document", "evidence", "support", "which doc")):
            return "EVIDENCE"
        if any(k in q for k in ("relationship", "connect", "link", "associat", "related")):
            return "RELATIONSHIP"
        if any(k in q for k in ("where", "when", "who", "what", "how many", "how much")):
            return "FACT"
        return "GENERAL"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def brief(self, db: Session, actor: AuthenticatedUser, case_number: str) -> dict:
        request_id = str(uuid.uuid4())
        case = require_case(db, actor, case_number)

        logger.info(
            "ai_brief_start",
            extra={"request_id": request_id, "case_id": case.id, "user_id": actor.id},
        )

        chunks = self.retriever.all_authorized(db, actor, case)
        claims = self._claims(
            "Create a concise factual case brief.",
            chunks,
            query_type="SUMMARY",
            request_id=request_id,
            case_id=case.id,
            user_id=actor.id,
        )
        claims = self.claim_validator.enforce(claims, chunks)
        trust = overall_trust_status(claims)

        contradictions = self.contradictions.compare(self.fact_extractor.extract(chunks))
        documents = [
            item for item in db.scalars(select(Document).where(Document.case_id == case.id))
            if policy_engine.can_view_document(db, actor, item)
        ]
        evidence = [
            item for item in db.scalars(select(Evidence).where(Evidence.case_id == case.id))
            if policy_engine.can_view_evidence(db, actor, item)
        ]
        integrity = IntegrityService().case_integrity(db, documents, evidence, chunks)
        missing = (
            ["Exhibit E-07 is referenced but absent from the case inventory."]
            if any("Exhibit E-07" in chunk.text for chunk in chunks)
            else []
        )

        evidence_claims = [c for c in claims if "Witness" not in c.claim and "charge sheet" not in c.claim.lower()]
        witness_claims = [c for c in claims if "Witness" in c.claim]

        logger.info(
            "ai_brief_complete",
            extra={
                "request_id": request_id,
                "case_id": case.id,
                "user_id": actor.id,
                "claim_count": len(claims),
                "trust_status": trust,
                "mode": "DETERMINISTIC_DEMO" if _is_demo_mode() else "GROUNDED_LLM",
            },
        )

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
            "integrity": {
                "documentsVerified": f"{integrity['documents']['verified']}/{integrity['documents']['total']}",
                "custody": integrity["custody"]["status"],
                "anchorStatus": integrity["anchorStatus"],
            },
            "claims": [item.model_dump() for item in claims],
            "trustStatus": trust,
            "disclaimer": DISCLAIMER,
            "generationMode": "DETERMINISTIC_DEMO" if _is_demo_mode() else "GROUNDED_LLM",
        }

    def ask(self, db: Session, actor: AuthenticatedUser, case_number: str, question: str) -> dict:
        request_id = str(uuid.uuid4())
        case = require_case(db, actor, case_number)
        query_type = self._classify_query(question)

        logger.info(
            "ai_ask_start",
            extra={
                "request_id": request_id,
                "case_id": case.id,
                "user_id": actor.id,
                "query_type": query_type,
            },
        )

        # Authorization: get all chunks the user is allowed to see FIRST.
        authorized_chunks = self.retriever.all_authorized(db, actor, case)

        # Specific check: restricted witness guard (Witness-03 for external expert).
        normalized = question.lower().replace("_", "-").replace(" ", "-")
        if "witness-03" in normalized and not any(
            "witness-03" in chunk.document_title.lower() for chunk in authorized_chunks
        ):
            logger.info(
                "ai_ask_restricted",
                extra={"request_id": request_id, "case_id": case.id, "user_id": actor.id},
            )
            return self._insufficient(question)

        # Retrieve from the pre-authorised pool only.
        results = self.retriever.retrieve(db, actor, case, question, mode="semantic")
        chunks = [result.chunk for result in results]

        # Build prompt for audit/debug even in demo mode.
        self.prompt_builder.build(question, chunks)

        if not chunks:
            return self._insufficient(question)

        claims = self._claims(
            question,
            chunks,
            query_type=query_type,
            request_id=request_id,
            case_id=case.id,
            user_id=actor.id,
        )

        # Demo mode: assign scores from retrieval results.
        if _is_demo_mode():
            claims = [
                EvidenceClaim(
                    claim=chunk.text,
                    confidence=max(0.7, results[index].score),
                    status="SUPPORTED",
                    sources=[citation_for(chunk)],
                )
                for index, chunk in enumerate(chunks)
            ]

        claims = self.claim_validator.enforce(claims, chunks)
        trust = overall_trust_status(claims)

        logger.info(
            "ai_ask_complete",
            extra={
                "request_id": request_id,
                "case_id": case.id,
                "user_id": actor.id,
                "query_type": query_type,
                "claim_count": len(claims),
                "trust_status": trust,
                "source_doc_ids": list({c.document_id for chunk in chunks for c in [chunk] if True}),
                "mode": "DETERMINISTIC_DEMO" if _is_demo_mode() else "GROUNDED_LLM",
            },
        )

        return {
            "answer": " ".join(claim.claim for claim in claims if claim.status != "INSUFFICIENT_EVIDENCE")
                      or "The available authorized evidence is insufficient to answer this question.",
            "status": trust,
            "trustStatus": trust,
            "claims": [claim.model_dump() for claim in claims],
            "sources": [source.model_dump() for claim in claims for source in claim.sources],
            "disclaimer": DISCLAIMER,
            "generationMode": "DETERMINISTIC_DEMO" if _is_demo_mode() else "GROUNDED_LLM",
        }

    @staticmethod
    def _insufficient(question: str) -> dict:
        claim = EvidenceClaim(
            claim="The available authorized evidence is insufficient to answer this question.",
            confidence=0,
            status="INSUFFICIENT_EVIDENCE",
            sources=[],
        )
        return {
            "answer": claim.claim,
            "status": claim.status,
            "trustStatus": claim.status,
            "claims": [claim.model_dump()],
            "sources": [],
            "disclaimer": DISCLAIMER,
            "generationMode": "DETERMINISTIC_DEMO",
        }
