"""HTTP schemas for /api/v1/documents.

Deliberate omission: `DocumentOut` does NOT include `full_text`. The extracted
text can be enormous and has no place in a metadata response — same whitelist
discipline as MemoryOut omitting the embedding (5e-1) and AgentOut omitting the
system_prompt (6h). Whitelisting via an explicit model makes the exclusion
structural, not a stylistic choice, so full_text can never leak by accident.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    content_type: str
    byte_size: int
    status: str
    chunk_count: int
    created_at: datetime


# --- 8e-1 search --------------------------------------------------------------


class DocumentSearchRequest(BaseModel):
    # POST (not GET): the query is user text that may be long and shouldn't land
    # in URLs or access logs. `limit` is clamped server-side (see the router).
    query: str = Field(min_length=1)
    limit: int = 5


class DocumentPositionOut(BaseModel):
    """The STRUCTURED provenance, for the UI to link/highlight with. The UI must
    NOT re-derive the human citation from these — it renders `citation` (below),
    computed once server-side, so two renderers can't drift."""

    char_start: int
    char_end: int
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None


class DocumentSearchResult(BaseModel):
    """One chunk hit. Whitelist discipline (5e-1): the chunk `text` only — never
    the document's `full_text`, never the embedding vector."""

    document_id: UUID
    filename: str
    text: str
    similarity: float
    position: DocumentPositionOut
    # Canonical citation string from DocumentPosition.render() — the single
    # source of truth for "p. 3 / pp. 2-3 / section X". The UI displays THIS.
    citation: str
