"""Document ingest pipeline (Phase 8b) — a SERVICE, not an endpoint.

bytes + content-type + filename + tenant + user
  → parse (8a parser)
  → chunk (8a chunker)
  → embed (Phase 5 provider, input_type="document")
  → persist document + all chunks in ONE transaction.

⚠️ NOT best-effort. Unlike the 5c memory write (fire-and-forget, swallows
failures so a memory bug can't break chat), a document ingest that fails must
NOT silently swallow: the user uploaded a file and expects it searchable, and a
half-ingested document (rows for some chunks, not others) is worse than none.
So this raises on any failure and persists document + chunks in a single unit of
work — Postgres commits every chunk INSERT or none, so partial state is
structurally impossible. The caller owns the transaction (matching the repo
convention); any exception here propagates and rolls the whole thing back.

⚠️ TOKEN-CAP GUARD (build time, fail-loud). `chunk_size` is in CHARACTERS;
embedding models cap TOKENS. The ≈4-chars/token heuristic breaks on non-English
text and code, so we do NOT use it to reassure ourselves — we use the only bound
that CANNOT be exceeded: byte-level BPE worst case. A UTF-8 char is ≤4 bytes and
each byte is ≤1 token, so a character yields ≤4 tokens. Guard: a full chunk can
reach `chunk_size * 4` tokens, which must not exceed the model's input cap. If it
could, we raise at construction (→ at lifespan startup) rather than let the
provider silently truncate a chunk at embed time and corrupt retrieval invisibly.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.documents import Chunker, DocumentParser
from app.application.ports.embeddings import EmbeddingProvider
from app.infrastructure.db.models import Document
from app.infrastructure.db.repositories import DocumentRepository
from app.shared.exceptions.documents import DocumentConfigError

# Worst-case tokens per character: 4-byte UTF-8 + byte-level BPE. This is the
# only ratio that holds for ANY script (CJK, emoji, code) — the ≈4 chars/token
# English heuristic is optimistic and unsafe as a guard.
_MAX_TOKENS_PER_CHAR = 4

# Max input tokens per embedding model. Add a model here when it ships.
_MODEL_MAX_INPUT_TOKENS: dict[str, int] = {
    "voyage-3.5": 32_000,
    "voyage-3-large": 32_000,
    "mock-embed-1": 32_000,  # mirrors voyage so the guard is exercised in tests
}
# Conservative floor for an unknown model — better to reject a large chunk_size
# than to assume a generous cap we can't prove.
_DEFAULT_MAX_INPUT_TOKENS = 8_192


def validate_chunk_size_within_token_cap(*, chunk_size: int, embedding_model: str) -> None:
    """Fail loudly if `chunk_size` chars could exceed the model's token cap."""
    cap = _MODEL_MAX_INPUT_TOKENS.get(embedding_model, _DEFAULT_MAX_INPUT_TOKENS)
    worst_case_tokens = chunk_size * _MAX_TOKENS_PER_CHAR
    if worst_case_tokens > cap:
        raise DocumentConfigError(
            f"DOCUMENT_CHUNK_SIZE={chunk_size} chars can reach {worst_case_tokens} "
            f"tokens (worst-case {_MAX_TOKENS_PER_CHAR} tokens/char), exceeding "
            f"{embedding_model!r} input cap of {cap}. Reduce chunk_size to "
            f"<= {cap // _MAX_TOKENS_PER_CHAR}."
        )


class DocumentIngestService:
    def __init__(
        self,
        *,
        parser: DocumentParser,
        chunker: Chunker,
        embedding_provider: EmbeddingProvider,
        chunk_size: int,
        embedding_model: str,
    ) -> None:
        # Build-time guard: refuse to start with a chunk_size that could be
        # silently truncated at embed time.
        validate_chunk_size_within_token_cap(chunk_size=chunk_size, embedding_model=embedding_model)
        self._parser = parser
        self._chunker = chunker
        self._embedding_provider = embedding_provider

    async def ingest(
        self,
        session: AsyncSession,  # tenant-scoped by the caller; caller owns the txn
        *,
        organization_id: UUID,
        uploaded_by_user_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
        storage_key: str | None = None,
        storage_backend: str | None = None,
        content_sha256: str | None = None,
    ) -> Document:
        """Parse → chunk → embed → persist, all-or-nothing. Raises on any
        failure; the caller's transaction rolls back → no partial rows.

        ADR 0002: the original bytes are stored BEFORE this runs, at the route
        boundary; the resulting pointer/provenance (`storage_key` etc.) is threaded
        through to the row here. This service does not touch the store — a failure
        here rolls back the row, and the caller fires the compensating delete.
        """
        parsed = await self._parser.parse(data=data, content_type=content_type)

        repo = DocumentRepository(session)
        document = await repo.create(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            content_type=content_type,
            byte_size=len(data),
            full_text=parsed.full_text,
            extraction_method=parsed.extraction_method,  # ADR 0004: "text" | "ocr"
            storage_key=storage_key,
            storage_backend=storage_backend,
            content_sha256=content_sha256,
        )

        chunks = self._chunker.chunk(document_id=str(document.id), document=parsed)
        if chunks:
            result = await self._embedding_provider.embed(
                texts=[c.text for c in chunks], input_type="document"
            )
            await repo.add_chunks(
                document_id=document.id,
                organization_id=organization_id,
                chunks=chunks,
                vectors=result.vectors,
                embedding_model=result.model,
                chunker=self._chunker.chunker_id,
            )
        return document
