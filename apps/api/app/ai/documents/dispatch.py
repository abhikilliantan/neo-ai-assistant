"""Content-type dispatch for document parsing (8f-1).

`parse()` routes by content type: text/plain and text/markdown go to the real
TextDocumentParser; every other type (application/pdf, DOCX, …) goes to the
`fallback` parser — the mock this slice, real PDF/DOCX in a later 8f slice. The
content type is normalized (drop params, lowercase) so "text/plain; charset=..."
still routes to the text parser even though the ingest layer already normalizes.
"""

from __future__ import annotations

from app.application.ports.documents import DocumentParser, ParsedDocument

_TEXT_CONTENT_TYPES = frozenset({"text/plain", "text/markdown"})


class ContentTypeDocumentParser:
    def __init__(self, *, text_parser: DocumentParser, fallback: DocumentParser) -> None:
        self._text_parser = text_parser
        self._fallback = fallback

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument:
        base = content_type.split(";")[0].strip().lower()
        parser = self._text_parser if base in _TEXT_CONTENT_TYPES else self._fallback
        return await parser.parse(data=data, content_type=content_type)
