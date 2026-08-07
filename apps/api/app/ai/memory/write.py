"""Shared memory-WRITE logic — one dedupe path for every writer.

The save_memory tool, `POST /api/v1/memories`, and the post-chat extraction
path all call `save_memory_deduped`, so a preference like "call me Boss" is
never stored twice regardless of which path recorded it. The dedupe is: embed
the content (input_type="document"), nearest-neighbour search the caller's own
memories, and skip the insert when the top cosine similarity is at or above the
threshold — returning the existing row instead.

The caller supplies a session-bound `MemoryRepositoryPort` and owns the
transaction (mirrors the rest of the repo layer — helpers never commit).
"""

from __future__ import annotations

from uuid import UUID

from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.repositories import MemoryRepositoryPort
from app.infrastructure.db.models.memory import MEMORY_KINDS
from app.infrastructure.db.models.memory import Memory as MemoryModel

_DEFAULT_KIND = "fact"
_FALLBACK_KIND = "other"


def clamp_kind(kind: str | None) -> str:
    """Map an arbitrary kind onto the allowed set (the DB CHECK would 500 on an
    unknown value). None → the default; unknown → 'other'."""
    if kind is None:
        return _DEFAULT_KIND
    normalized = kind.strip().lower()
    return normalized if normalized in MEMORY_KINDS else _FALLBACK_KIND


async def save_memory_deduped(
    *,
    repo: MemoryRepositoryPort,
    embedding_provider: EmbeddingProvider,
    organization_id: UUID,
    user_id: UUID,
    content: str,
    dedupe_threshold: float,
    kind: str | None = None,
    source: str | None = None,
) -> tuple[MemoryModel, bool]:
    """Embed `content`, skip if a near-duplicate already exists, else insert.

    Returns `(memory, created)` — `created=False` means an existing near-dupe
    row was returned untouched. `kind` is clamped to the allowed set.
    """
    resolved_kind = clamp_kind(kind)
    result = await embedding_provider.embed(texts=[content], input_type="document")
    vector = result.vectors[0]

    # Only rows embedded by the SAME model are comparable (cosine across vector
    # spaces is meaningless) — the search filters on it.
    existing = await repo.search_similar(
        organization_id=organization_id,
        user_id=user_id,
        query_embedding=vector,
        limit=1,
        embedding_model=result.model,
    )
    if existing and existing[0][1] >= dedupe_threshold:
        return existing[0][0], False

    memory = await repo.add(
        organization_id=organization_id,
        user_id=user_id,
        content=content,
        embedding=vector,
        embedding_model=result.model,
        kind=resolved_kind,
        source=source,
    )
    return memory, True
