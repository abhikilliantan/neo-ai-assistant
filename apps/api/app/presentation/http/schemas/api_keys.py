"""Pydantic schemas for API-key management + the service whoami probe.

The plaintext secret appears in exactly ONE response model
(`ApiKeyCreatedResponse.api_key`) and nowhere else — list/read never expose it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # None → server applies DEFAULT_SCOPES (["read"]). Unknown scopes → 400.
    scopes: list[str] | None = None


class ApiKeyCreatedResponse(BaseModel):
    """Returned ONCE on creation — the only place `api_key` (plaintext) is shown."""

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    api_key: str = Field(description="Plaintext secret — shown once, store it now.")


class ApiKeyOut(BaseModel):
    """Safe metadata view — never includes the secret or its hash."""

    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class WhoAmIResponse(BaseModel):
    organization_id: UUID | None
    scopes: list[str]
