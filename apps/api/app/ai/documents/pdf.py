"""Parent-side PDF parser adapter (ADR 0003 slice 2, PDF; ADR 0004 slice 1, OCR).

A `DocumentParser` that runs the real PDF extraction INSIDE the isolation harness
(`parse_in_subprocess`), so every PDF parse inherits the wall-clock timeout +
RLIMIT_AS. It threads the scanned-detection floor and (ADR 0004) the OCR config
to the child via env, and lets the harness compute char offsets parent-side.

When OCR is enabled the subprocess gets the LARGER OCR wall-clock budget
(`ocr_timeout_seconds`) rather than the 30s text budget, because a scanned PDF
legitimately needs longer; a native-text PDF still finishes in well under it. The
harness kill is authoritative regardless.
"""

from __future__ import annotations

from app.ai.parsing.harness import parse_in_subprocess
from app.application.ports.documents import ParsedDocument

PDF_CONTENT_TYPE = "application/pdf"


class SubprocessPdfParser:
    def __init__(
        self,
        *,
        min_chars_per_page: int,
        max_memory_bytes: int,
        timeout_seconds: float,
        ocr_enabled: bool = False,
        ocr_max_pages: int = 15,
        ocr_timeout_seconds: float = 90.0,
        ocr_min_confidence: float = 60.0,
    ) -> None:
        self._min_chars_per_page = min_chars_per_page
        self._max_memory_bytes = max_memory_bytes
        self._timeout_seconds = timeout_seconds
        self._ocr_enabled = ocr_enabled
        self._ocr_max_pages = ocr_max_pages
        self._ocr_timeout_seconds = ocr_timeout_seconds
        self._ocr_min_confidence = ocr_min_confidence

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument:
        child_env = {"NEO_PDF_MIN_CHARS_PER_PAGE": str(self._min_chars_per_page)}
        # OCR path gets the larger wall-clock budget; the text path never needs it.
        timeout = self._timeout_seconds
        if self._ocr_enabled:
            child_env.update(
                {
                    "NEO_OCR_ENABLED": "1",
                    "NEO_OCR_MAX_PAGES": str(self._ocr_max_pages),
                    "NEO_OCR_MIN_CONFIDENCE": str(self._ocr_min_confidence),
                }
            )
            timeout = max(self._timeout_seconds, self._ocr_timeout_seconds)
        return await parse_in_subprocess(
            parser="pdf",
            data=data,
            content_type=content_type,
            max_memory_bytes=self._max_memory_bytes,
            timeout_seconds=timeout,
            child_env=child_env,
        )
