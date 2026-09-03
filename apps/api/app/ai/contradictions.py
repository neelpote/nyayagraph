from __future__ import annotations

import re
from dataclasses import dataclass
from .corpus import AuthorizedChunk
from .schemas import ContradictionDTO
from .validation import citation_for


@dataclass(frozen=True)
class NormalizedFact:
    fact_type: str
    subject: str
    value: str
    minutes: int
    source: AuthorizedChunk
    confidence: float


class FactExtractionService:
    """Deterministic extraction for the MVP's structured timing facts."""

    _TIME = re.compile(r"\b([01]\d|2[0-3]):([0-5]\d)\b")

    def extract(self, chunks: list[AuthorizedChunk]) -> list[NormalizedFact]:
        facts: list[NormalizedFact] = []
        for chunk in chunks:
            if "depart" not in chunk.text.lower():
                continue
            match = self._TIME.search(chunk.text)
            if match:
                hour, minute = int(match.group(1)), int(match.group(2))
                facts.append(NormalizedFact(
                    fact_type="INCIDENT_TIME",
                    subject="Vehicle departure",
                    value=match.group(0),
                    minutes=hour * 60 + minute,
                    source=chunk,
                    confidence=0.95 if "CCTV" in chunk.document_title else 0.9,
                ))
        return facts


class ContradictionEngine:
    """Flags materially different assertions without deciding which is truthful."""

    TIME_THRESHOLD_MINUTES = 15

    def compare(self, facts: list[NormalizedFact]) -> list[ContradictionDTO]:
        timing = [fact for fact in facts if fact.fact_type == "INCIDENT_TIME"]
        if len(timing) < 2 or max(f.minutes for f in timing) - min(f.minutes for f in timing) < self.TIME_THRESHOLD_MINUTES:
            return []
        return [ContradictionDTO(
            type="TIME_DISCREPANCY",
            subject="Vehicle departure",
            values=[{
                "value": fact.value,
                "source": fact.source.document_title,
                "confidence": fact.confidence,
            } for fact in sorted(timing, key=lambda item: item.minutes)],
            explanation=(
                "Authorized sources report materially different vehicle-departure times. "
                "NyayaGraph does not determine which source is truthful."
            ),
            sources=[citation_for(fact.source) for fact in timing],
        )]
