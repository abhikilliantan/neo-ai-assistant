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

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    content_type: str
    byte_size: int
    status: str
    chunk_count: int
    created_at: datetime
