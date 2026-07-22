"""Content-type dispatch for document parsing (8f-1; reject fallthrough 8-cleanup).

`parse()` routes by content type: text/plain and text/markdown go to the real
TextDocumentParser. Every other type (application/pdf, DOCX, …) goes to the
`fallback` — which is the mock ONLY when explicitly wired for tests/CI
(settings.document_parser == "mock"), and otherwise `None`, meaning REJECT with
415. Rejecting a format we cannot really parse beats falling through to the mock
and fabricating searchable content that has nothing to do with the file — silent
fabrication is worse than failure. The content type is normalized (drop params,
lowercase) so "text/plain; charset=..." still routes correctly.

(No magic-number sniffing here — that is the 8f-2 security slice. We trust the
declared type; a misdeclared file, e.g. a PDF renamed .txt, still fails honestly
via the UTF-8 decode error → 422.)
"""

from __future__ import annotations

from app.application.ports.documents import DocumentParser, ParsedDocument
from app.shared.exceptions.documents import UnsupportedContentTypeError

_TEXT_CONTENT_TYPES = frozenset({"text/plain", "text/markdown"})


class ContentTypeDocumentParser:
    def __init__(
        self,
        *,
        text_parser: DocumentParser,
        fallback: DocumentParser | None,
        native: dict[str, DocumentParser] | None = None,
    ) -> None:
        self._text_parser = text_parser
        # `native` maps content-type → a real per-format parser (e.g. DOCX), enabled
        # per-format (ADR 0003). A type with no native parser falls to `fallback`.
        self._native = native or {}
        self._fallback = fallback

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument:
        base = content_type.split(";")[0].strip().lower()
        if base in _TEXT_CONTENT_TYPES:
            return await self._text_parser.parse(data=data, content_type=content_type)
        native = self._native.get(base)
        if native is not None:
            return await native.parse(data=data, content_type=content_type)
        if self._fallback is None:
            raise UnsupportedContentTypeError(
                f"cannot process {base!r} yet — only plain text (text/plain) and "
                "Markdown (text/markdown) are supported. PDF and Word support is coming."
            )
        return await self._fallback.parse(data=data, content_type=content_type)
