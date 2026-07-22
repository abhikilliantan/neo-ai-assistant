"""Parent-side PDF parser adapter (ADR 0003 slice 2, PDF).

A `DocumentParser` that runs the real PDF extraction INSIDE the isolation harness
(`parse_in_subprocess`), so every PDF parse inherits the wall-clock timeout +
RLIMIT_AS. It threads the scanned-detection floor to the child via env and lets
the harness compute char offsets parent-side from the returned blocks.
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
    ) -> None:
        self._min_chars_per_page = min_chars_per_page
        self._max_memory_bytes = max_memory_bytes
        self._timeout_seconds = timeout_seconds

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument:
        return await parse_in_subprocess(
            parser="pdf",
            data=data,
            content_type=content_type,
            max_memory_bytes=self._max_memory_bytes,
            timeout_seconds=self._timeout_seconds,
            child_env={"NEO_PDF_MIN_CHARS_PER_PAGE": str(self._min_chars_per_page)},
        )
