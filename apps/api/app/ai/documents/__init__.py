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

from app.ai.documents.chunker import FixedSizeChunker
from app.ai.documents.ingest import (
    DocumentIngestService,
    validate_chunk_size_within_token_cap,
)
from app.ai.documents.mock import MockDocumentParser
from app.application.ports.documents import Chunker, DocumentParser
from app.application.ports.embeddings import EmbeddingProvider
from app.infrastructure.config import Settings


def build_document_parser(settings: Settings) -> DocumentParser:
    """Wire the concrete parser from settings.document_parser. Fail-fast on the
    unknown branch, same posture as build_chat_provider.
    """
    if settings.document_parser == "mock":
        return MockDocumentParser(max_bytes=settings.document_max_bytes)
    if settings.document_parser == "unstructured":
        raise NotImplementedError(
            "DOCUMENT_PARSER=unstructured is not implemented until 8f; use 'mock' for now"
        )
    raise RuntimeError(f"Unknown DOCUMENT_PARSER: {settings.document_parser!r}")


def build_chunker(settings: Settings) -> Chunker:
    """The fixed-size chunker, configured from settings. Bad size/overlap fail
    at construction (FixedSizeChunker validates).
    """
    return FixedSizeChunker(
        chunk_size=settings.document_chunk_size,
        overlap=settings.document_chunk_overlap,
    )


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
    "DocumentIngestService",
    "FixedSizeChunker",
    "MockDocumentParser",
    "build_chunker",
    "build_document_ingest_service",
    "build_document_parser",
    "validate_chunk_size_within_token_cap",
]
