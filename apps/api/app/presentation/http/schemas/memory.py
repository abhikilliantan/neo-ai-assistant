"""HTTP schemas for /api/v1/memories + /api/v1/preferences.

Deliberate omissions:
  - `MemoryOut` does NOT include `embedding` — it's a 1024-float pgvector
    blob (~4 KB/row) with no client use. Whitelisting fields via an explicit
    Pydantic model (rather than dumping the ORM row) makes that guarantee
    structural, not just a stylistic choice.
  - `MemoryOut` also omits `organization_id`, `user_id`, `deleted_at`,
    `embedding_model` — the caller is scoped by tenant + user already, and
    only ever gets their own live rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MemoryOut(BaseModel):
    id: UUID
    content: str
    kind: str
    source: str | None
    created_at: datetime


class PreferenceOut(BaseModel):
    key: str
    value: Any


class PreferenceUpsertRequest(BaseModel):
    value: Any
