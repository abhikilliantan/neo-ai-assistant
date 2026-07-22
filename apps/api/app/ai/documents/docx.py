"""Parent-side DOCX parser adapter (ADR 0003 slice 1, DOCX).

A `DocumentParser` that runs the real DOCX extraction INSIDE the isolation
harness (`parse_in_subprocess`), so every DOCX parse inherits the wall-clock
timeout + RLIMIT_AS. It threads the decompressed-size cap to the child via env
and lets the harness compute char offsets parent-side from the returned blocks.
"""

from __future__ import annotations

from app.ai.parsing.harness import parse_in_subprocess
from app.application.ports.documents import ParsedDocument

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class SubprocessDocxParser:
    def __init__(
        self,
        *,
        max_decompressed_bytes: int,
        max_memory_bytes: int,
        timeout_seconds: float,
    ) -> None:
        self._max_decompressed_bytes = max_decompressed_bytes
        self._max_memory_bytes = max_memory_bytes
        self._timeout_seconds = timeout_seconds

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument:
        return await parse_in_subprocess(
            parser="docx",
            data=data,
            content_type=content_type,
            max_memory_bytes=self._max_memory_bytes,
            timeout_seconds=self._timeout_seconds,
            child_env={"NEO_DOCX_MAX_DECOMPRESSED": str(self._max_decompressed_bytes)},
        )
