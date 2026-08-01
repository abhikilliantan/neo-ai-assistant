"""API-key use cases: create, authenticate, list, revoke.

Depend on repository ports + the security primitives. No HTTP, no DB imports —
mirrors use_cases/auth.py.

Authentication mirrors login's role split: matching a raw key to its row is a
cross-tenant read (the tenant lives inside the row), so it runs on the privileged
SystemRepository, exactly like find_user_by_email. The caller (a FastAPI dep)
then sets the same `app.current_tenant` GUC from the resolved org so downstream
RLS applies identically to the user-JWT path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from app.application.ports.repositories import ApiKeyRepositoryPort, SystemRepositoryPort
from app.infrastructure.security import (
    DEFAULT_SCOPES,
    SUPPORTED_SCOPES,
    generate_api_key,
    prefix_of,
    verify_api_key,
)
from app.shared.exceptions.auth import AuthenticationError, InsufficientScopeError
from app.shared.exceptions.common import BadRequestError

if TYPE_CHECKING:
    from app.infrastructure.db.models import ApiKey


@dataclass(slots=True)
class Principal:
    """Unified caller identity — a user JWT OR a service key resolve to this, so
    a combined endpoint can be protected by either (Slice 4). organization_id is
    the tenant used to set the RLS GUC.
    """

    kind: Literal["user", "service"]
    organization_id: UUID | None
    scopes: list[str] = field(default_factory=list)
    user_id: UUID | None = None
    api_key_id: UUID | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


async def create_api_key(
    *,
    organization_id: UUID,
    name: str,
    scopes: list[str] | None = None,
    keys: ApiKeyRepositoryPort,
) -> tuple[ApiKey, str]:
    """Mint a key for the org. Returns (row, raw_plaintext) — the plaintext is
    returned ONCE here and never persisted (only its hash + prefix are stored).
    Rejects scopes the system can't enforce."""
    requested = list(scopes) if scopes else list(DEFAULT_SCOPES)
    unknown = sorted(set(requested) - SUPPORTED_SCOPES)
    if unknown:
        raise BadRequestError(f"unsupported scope(s): {', '.join(unknown)}")

    generated = generate_api_key()
    key = await keys.create(
        organization_id=organization_id,
        name=name,
        key_prefix=generated.key_prefix,
        key_hash=generated.key_hash,
        scopes=requested,
    )
    return key, generated.raw


async def authenticate_api_key(
    raw: str,
    *,
    system: SystemRepositoryPort,
    required_scope: str = "read",
) -> Principal:
    """Validate a raw service key and return its Principal.

    Order of checks keeps the failure reason precise: unknown/revoked/expired all
    → 401 (AuthenticationError); wrong scope → 403 (InsufficientScopeError). Only
    a fully-valid, in-scope key touches last_used_at.
    """
    candidates = await system.find_api_keys_by_prefix(prefix_of(raw))
    matched = next((k for k in candidates if verify_api_key(raw, k.key_hash)), None)
    if matched is None:
        raise AuthenticationError("invalid api key")
    if matched.revoked_at is not None:
        raise AuthenticationError("api key revoked")
    if matched.expires_at is not None and matched.expires_at <= datetime.now(UTC):
        raise AuthenticationError("api key expired")
    if required_scope not in matched.scopes:
        raise InsufficientScopeError(required_scope)

    await system.touch_api_key_last_used(matched.id)
    return Principal(
        kind="service",
        organization_id=matched.organization_id,
        scopes=list(matched.scopes),
        api_key_id=matched.id,
    )
