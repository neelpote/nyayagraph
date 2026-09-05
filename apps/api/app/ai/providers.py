"""AI provider layer.

``StructuredLLMProvider`` is the single entry-point for all LLM-backed claim
generation.  It:

  1. Chooses the right LLMProvider via the factory (Ollama/Qwen, OpenAI-compat ?).
  2. Builds a structured evidence-context prompt.
  3. Sends the request to the model.
  4. Parses + validates the structured JSON output with a safe fallback.
  5. Validates every citation against the authorised chunk pool.
  6. Applies the faithfulness gate ? unsupported claims are demoted.

The rest of the application (case_agent.py) calls only ``generate_claims()``.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from urllib.request import Request, urlopen

from ..config import get_settings
from .corpus import AuthorizedChunk
from .llm.base import LLMProviderError, LLMRequest
from .prompting import NYAYAGRAPH_SYSTEM_PROMPT, PromptBuilder
from .schemas import EvidenceClaim, ClaimStatus
from .validation import citation_for

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy low-level HTTP client ? kept for EmbeddingProvider and the
# openai_compat LLM adapter.  NOT used directly for Qwen/Ollama.
# ---------------------------------------------------------------------------

class AIProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAICompatibleClient:
    base_url: str
    api_key: str

    def post(self, path: str, payload: dict) -> dict:
        if not self.base_url:
            raise AIProviderError("AI provider URL is not configured")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=45) as response:  # nosec B310 - configured AI endpoint
                return json.load(response)
        except Exception as error:
            raise AIProviderError("Configured AI provider is unavailable") from error


# ---------------------------------------------------------------------------
# Structured output parser
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[str, ClaimStatus] = {
    "SUPPORTED": "SUPPORTED",
    "PARTIALLY_SUPPORTED": "PARTIALLY_SUPPORTED",
    "CONFLICTING": "CONFLICTING",
    "UNSUPPORTED": "UNSUPPORTED",
    "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
}


def _parse_llm_output(raw: str, allowed_chunks: dict[str, AuthorizedChunk]) -> list[EvidenceClaim]:
    """Parse Qwen's JSON output into EvidenceClaim objects.

    Handles three failure modes gracefully:
      - Malformed JSON ? attempts to extract the JSON substring.
      - Missing/wrong fields ? skips individual bad claims.
      - Hallucinated document IDs ? citations stripped; claim demoted.
    """
    # Strip markdown code fences if present.
    content = raw.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-z]*\n?", "", content)
        content = re.sub(r"```$", "", content).strip()

    # Attempt to extract a JSON object if there's surrounding text.
    if not content.startswith("{"):
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group(0)

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        logger.warning("LLM returned unparseable JSON; treating as insufficient evidence")
        return []

    overall_raw = str(data.get("overall_status", "UNSUPPORTED")).upper()
    overall_status: ClaimStatus = _STATUS_MAP.get(overall_raw, "UNSUPPORTED")

    # If the model returned INSUFFICIENT_EVIDENCE as the top-level status,
    # return a single insufficient claim ? no fabricated citations possible.
    if overall_status == "INSUFFICIENT_EVIDENCE":
        return [EvidenceClaim(
            claim="The available authorized evidence is insufficient to answer this question.",
            confidence=0.0,
            status="INSUFFICIENT_EVIDENCE",
            sources=[],
        )]

    claims: list[EvidenceClaim] = []
    raw_claims = data.get("claims") or []

    # Build an index keyed by document_id for fast citation lookup.
    chunks_by_doc: dict[str, list[AuthorizedChunk]] = {}
    for chunk in allowed_chunks.values():
        chunks_by_doc.setdefault(chunk.document_id, []).append(chunk)

    for raw_claim in raw_claims:
        if not isinstance(raw_claim, dict):
            continue
        claim_text = str(raw_claim.get("claim", "")).strip()[:4000]
        if not claim_text:
            continue
        raw_status = str(raw_claim.get("support_status", "UNSUPPORTED")).upper()
        claim_status: ClaimStatus = _STATUS_MAP.get(raw_status, "UNSUPPORTED")

        # Resolve citations ? only accept document IDs that exist in the
        # authorised chunk pool.  Hallucinated IDs are silently dropped.
        sources = []
        for src in raw_claim.get("supporting_sources") or []:
            if not isinstance(src, dict):
                continue
            doc_id = str(src.get("document_id", ""))
            page = int(src.get("page", 1))
            matching_chunks = chunks_by_doc.get(doc_id, [])
            if not matching_chunks:
                # Hallucinated document ID ? drop citation, demote claim.
                claim_status = "UNSUPPORTED"
                continue
            # Pick the chunk closest to the cited page.
            best = min(matching_chunks, key=lambda c: abs(c.page_number - page))
            sources.append(citation_for(best))

        # Faithfulness gate: a SUPPORTED claim with no valid citations is demoted.
        if claim_status == "SUPPORTED" and not sources:
            claim_status = "UNSUPPORTED"

        confidence = 1.0 if claim_status == "SUPPORTED" else (
            0.6 if claim_status == "PARTIALLY_SUPPORTED" else (
                0.3 if claim_status == "CONFLICTING" else 0.0
            )
        )
        claims.append(EvidenceClaim(
            claim=claim_text,
            confidence=confidence,
            status=claim_status,
            sources=sources,
        ))

    return claims if claims else []


# ---------------------------------------------------------------------------
# Main structured LLM provider
# ---------------------------------------------------------------------------

class StructuredLLMProvider:
    """Orchestrates prompt construction ? LLM call ? output parsing ? citation
    validation for every LLM-backed query in NyayaGraph.

    This class is provider-agnostic: it delegates the actual HTTP call to
    whichever LLMProvider the factory returns.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._provider_name = (settings.llm_provider or "demo").lower()
        self._prompt_builder = PromptBuilder()

    def _get_provider(self):
        """Lazily resolve the LLM provider (not cached here; factory caches it)."""
        from .llm.factory import get_llm_provider
        return get_llm_provider()

    def generate_claims(
        self,
        question: str,
        chunks: list[AuthorizedChunk],
        *,
        query_type: str = "GENERAL",
        request_id: str = "",
        case_id: str = "",
        user_id: str = "",
    ) -> list[EvidenceClaim]:
        """Full pipeline: context ? prompt ? LLM ? parse ? validate ? gate."""
        if not chunks:
            return []

        allowed = {chunk.chunk_id: chunk for chunk in chunks}

        # Build structured context and user prompt.
        context = self._prompt_builder.build_structured_context(chunks)
        user_prompt = self._prompt_builder.build_user_prompt(question, query_type)

        provider = self._get_provider()
        settings = get_settings()

        llm_request = LLMRequest(
            system_prompt=NYAYAGRAPH_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            context=context,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        t0 = time.monotonic()
        try:
            response = provider.generate(llm_request)
        except LLMProviderError as exc:
            raise AIProviderError(str(exc)) from exc
        latency_ms = (time.monotonic() - t0) * 1000

        # Operational log ? no evidence text, no PII.
        logger.info(
            "llm_request",
            extra={
                "request_id": request_id,
                "case_id": case_id,
                "user_id": user_id,
                "query_type": query_type,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "retrieved_docs": list({c.document_id for c in chunks}),
                "retrieved_chunks": len(chunks),
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "latency_ms": round(latency_ms, 1),
            },
        )

        claims = _parse_llm_output(response.content, allowed)

        if not claims:
            raise AIProviderError("AI provider returned no grounded claims")

        return claims


# ---------------------------------------------------------------------------
# Embedding provider ? unchanged from original.
# ---------------------------------------------------------------------------

class EmbeddingProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.embedding_provider not in {"", "demo", "disabled"}
        self.model = settings.embedding_model
        self.client = OpenAICompatibleClient(
            settings.embedding_base_url or settings.llm_base_url,
            settings.embedding_api_key or settings.llm_api_key,
        )

    def embed(self, text: str) -> list[float] | None:
        if not self.enabled:
            return None
        response = self.client.post("embeddings", {"model": self.model, "input": text})
        try:
            vector = [float(value) for value in response["data"][0]["embedding"]]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise AIProviderError("Embedding provider returned invalid output") from error
        if len(vector) != 384:
            raise AIProviderError("Embedding provider must return 384 dimensions")
        return vector


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return EmbeddingProvider()
