"""Deterministic mock document parser. Zero external calls, NO real file
libraries — the CI/test default, same posture as MockProvider /
MockWorkflowClient.

It produces output with REALISTIC STRUCTURE — several pages (paginated content
types) or several sections (everything else) — so 8b-8e can test citation for
real. A mock that returned one flat blob would let a provenance bug hide until
real parsing lands.

It does NOT interpret the input bytes (that is real parsing, 8f). It DOES
enforce `max_bytes` up front, so the resource-limit path in the contract is
exercised now.
"""

from __future__ import annotations

from app.application.ports.documents import ParsedBlock, ParsedDocument
from app.shared.exceptions.documents import DocumentTooLargeError

# Content types the mock treats as paginated (blocks get real page numbers).
# Everything else is treated as section-structured (page=None, section set).
_PAGINATED = frozenset({"application/pdf"})

# Deterministic, distinctly-sized block bodies so tests can force chunks to
# span a page/section boundary without depending on the input bytes.
_BLOCK_BODIES = (
    "Introduction. " + ("alpha " * 20),
    "Methods and materials. " + ("beta " * 24),
    "Results and discussion. " + ("gamma " * 18),
)


class MockDocumentParser:
    def __init__(self, *, max_bytes: int) -> None:
        self._max_bytes = max_bytes

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument:
        if len(data) > self._max_bytes:
            # Reject cheaply, before any "parsing". No byte content in the
            # message — an oversized upload is untrusted.
            raise DocumentTooLargeError(
                f"document exceeds max_bytes ({len(data)} > {self._max_bytes})"
            )
        if not data:
            # Empty input → an empty document (no blocks). full_text == "".
            return ParsedDocument(content_type=content_type, blocks=[])

        paginated = content_type in _PAGINATED
        blocks = [
            ParsedBlock(
                text=body,
                page=(i + 1) if paginated else None,
                section=None if paginated else f"Section {i + 1}",
            )
            for i, body in enumerate(_BLOCK_BODIES)
        ]
        return ParsedDocument(content_type=content_type, blocks=blocks)
