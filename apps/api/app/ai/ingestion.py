from __future__ import annotations

from dataclasses import dataclass

import fitz


@dataclass(frozen=True)
class ExtractedChunk:
    page_number: int
    chunk_index: int
    text: str


class TextExtractionService:
    """Extract selectable text first; OCR providers can extend this boundary later."""

    def extract(self, content: bytes, mime_type: str) -> list[ExtractedChunk]:
        pages: list[tuple[int, str]] = []
        if mime_type == "text/plain":
            pages = [(1, content.decode("utf-8"))]
        elif mime_type == "application/pdf":
            with fitz.open(stream=content, filetype="pdf") as document:
                pages = [(index + 1, page.get_text("text")) for index, page in enumerate(document)]
        chunks: list[ExtractedChunk] = []
        for page_number, page_text in pages:
            normalized = " ".join(page_text.split())
            start = 0
            page_index = 0
            while start < len(normalized):
                end = min(start + 1200, len(normalized))
                chunks.append(ExtractedChunk(page_number, page_index, normalized[start:end]))
                if end == len(normalized):
                    break
                start = max(start + 1, end - 150)
                page_index += 1
        return [chunk for chunk in chunks if chunk.text]
