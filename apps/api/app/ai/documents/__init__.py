"""Document parser + chunker builders — config-driven selection.

Mirrors `build_chat_provider` / `build_workflow_client`:
  - `build_document_parser(settings)` selects the parser from
    `settings.document_parser`. "mock" is the CI/test default; a real parser
    name RAISES NotImplementedError this slice — 8f ships real PDF/DOCX parsing
    with its own dependency review. We do NOT stub a fake parse.
  - `build_chunker(settings)` returns the single fixed-size chunker configured
    from settings. No mock/real split — chunking is deterministic pure logic
    with no external dependency; the `Chunker` Protocol keeps a future
    sentence/structure-aware strategy additive, so no selector is added yet.

Nothing consumes either yet — 8a is the contracts/mock slice; 8c wires ingest.
"""

from __future__ import annotations

from app.ai.documents.block_aware import BlockAwareChunker
from app.ai.documents.chunker import FixedSizeChunker
from app.ai.documents.dispatch import ContentTypeDocumentParser
from app.ai.documents.ingest import (
    DocumentIngestService,
    validate_chunk_size_within_token_cap,
)
from app.ai.documents.mock import MockDocumentParser
from app.ai.documents.text import TextDocumentParser
from app.application.ports.documents import Chunker, DocumentParser
from app.application.ports.embeddings import EmbeddingProvider
from app.infrastructure.config import Settings


def build_document_parser(settings: Settings) -> DocumentParser:
    """Wire the parser: a content-type dispatcher that routes text/plain and
    text/markdown to the real TextDocumentParser (8f-1) and everything else to
    the `document_parser`-selected fallback.

    The fallback is still the mock (the CI/test default) — PDF/DOCX real parsing
    lands in a later 8f slice, so DOCUMENT_PARSER=unstructured still fails fast.
    """
    text_parser = TextDocumentParser(max_bytes=settings.document_max_bytes)
    if settings.document_parser == "mock":
        fallback: DocumentParser = MockDocumentParser(max_bytes=settings.document_max_bytes)
    elif settings.document_parser == "unstructured":
        raise NotImplementedError(
            "DOCUMENT_PARSER=unstructured (real PDF/DOCX) is not implemented until a "
            "later 8f slice; use 'mock' for now"
        )
    else:
        raise RuntimeError(f"Unknown DOCUMENT_PARSER: {settings.document_parser!r}")
    return ContentTypeDocumentParser(text_parser=text_parser, fallback=fallback)


def build_chunker(settings: Settings) -> Chunker:
    """Select the chunker from settings.document_chunker (ADR 0001 Decision 7).
    "fixed" (default) and "block_aware" share chunk_size/overlap; both validate
    size/overlap at construction. Fail-fast on the unknown branch.
    """
    if settings.document_chunker == "fixed":
        return FixedSizeChunker(
            chunk_size=settings.document_chunk_size,
            overlap=settings.document_chunk_overlap,
        )
    if settings.document_chunker == "block_aware":
        return BlockAwareChunker(
            chunk_size=settings.document_chunk_size,
            overlap=settings.document_chunk_overlap,
        )
    raise RuntimeError(f"Unknown DOCUMENT_CHUNKER: {settings.document_chunker!r}")


def build_document_ingest_service(
    settings: Settings,
    *,
    parser: DocumentParser,
    chunker: Chunker,
    embedding_provider: EmbeddingProvider,
) -> DocumentIngestService:
    """Wire the ingest service. The constructor runs the token-cap guard, so a
    chunk_size that could be silently truncated at embed fails fast at startup.
    """
    return DocumentIngestService(
        parser=parser,
        chunker=chunker,
        embedding_provider=embedding_provider,
        chunk_size=settings.document_chunk_size,
        embedding_model=settings.embedding_model,
    )


__all__ = [
    "BlockAwareChunker",
    "ContentTypeDocumentParser",
    "DocumentIngestService",
    "FixedSizeChunker",
    "MockDocumentParser",
    "TextDocumentParser",
    "build_chunker",
    "build_document_ingest_service",
    "build_document_parser",
    "validate_chunk_size_within_token_cap",
]
