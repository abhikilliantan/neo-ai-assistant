"""Auth use cases: register, login, refresh, logout.

Depend on repository ports + phase-2b security primitives. No HTTP, no DB imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.application.ports.repositories import (
    MembershipRepositoryPort,
    OrganizationRepositoryPort,
    RoleRepositoryPort,
    SessionRepositoryPort,
    UserRepositoryPort,
)
from app.infrastructure.config import get_settings
from app.infrastructure.security import (
    ExpiredTokenError,
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    verify_password,
)
from app.shared.exceptions.auth import AuthenticationError, EmailAlreadyRegisteredError

# A fixed argon2 hash used as a decoy when the login user doesn't exist.
# Keeps timing constant so callers can't enumerate valid emails by response time.
_DECOY_PASSWORD_HASH = hash_password("decoy-value-never-matches")


@dataclass(slots=True)
class AuthResult:
    user_id: UUID
    email: str
    active_tenant_id: UUID | None
    access_token: str
    refresh_token: str
    expires_in: int


def _access_expires_in_seconds() -> int:
    return get_settings().access_token_expire_minutes * 60


def _refresh_expires_at() -> datetime:
    return datetime.now(UTC) + timedelta(days=get_settings().refresh_token_expire_days)


async def _issue_tokens(
    *,
    user_id: UUID,
    email: str,
    tenant_id: UUID | None,
    sessions: SessionRepositoryPort,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthResult:
    jti = uuid4()
    access = create_access_token(subject=user_id, tenant_id=tenant_id)
    refresh = create_refresh_token(subject=user_id, jti=jti)
    await sessions.create(
        user_id=user_id,
        refresh_token_hash=hash_refresh_token(refresh),
        expires_at=_refresh_expires_at(),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return AuthResult(
        user_id=user_id,
        email=email,
        active_tenant_id=tenant_id,
        access_token=access,
        refresh_token=refresh,
        expires_in=_access_expires_in_seconds(),
    )


async def register(
    email: str,
    password: str,
    organization_name: str | None = None,
    *,
    users: UserRepositoryPort,
    organizations: OrganizationRepositoryPort,
    memberships: MembershipRepositoryPort,
    roles: RoleRepositoryPort,
    sessions: SessionRepositoryPort,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthResult:
    email_norm = normalize_email(email)

    if await users.get_by_email_normalized(email_norm) is not None:
        raise EmailAlreadyRegisteredError(email_norm)

    owner_role = await roles.get_by_name("owner")
    if owner_role is None:
        # Seed data missing — indicates a broken deploy, not a user error.
        raise RuntimeError("system role 'owner' is missing; seed data not applied")

    user = await users.create(email=email_norm, password_hash=hash_password(password))

    org_name = organization_name or f"{email_norm.split('@')[0]}'s workspace"
    org = await organizations.create_with_unique_slug(org_name)

    # Guardrail: only embed tenant_id in the token AFTER the membership row exists.
    await memberships.create(
        user_id=user.id,
        organization_id=org.id,
        role_id=owner_role.id,
    )

    return await _issue_tokens(
        user_id=user.id,
        email=user.email,
        tenant_id=org.id,
        sessions=sessions,
        user_agent=user_agent,
        ip_address=ip_address,
    )


async def login(
    email: str,
    password: str,
    *,
    users: UserRepositoryPort,
    memberships: MembershipRepositoryPort,
    sessions: SessionRepositoryPort,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthResult:
    email_norm = normalize_email(email)
    user = await users.get_by_email_normalized(email_norm)

    # Constant-time behavior: always run argon2 verify, even for unknown users.
    hash_to_check = user.password_hash if user is not None else _DECOY_PASSWORD_HASH
    if not verify_password(password, hash_to_check) or user is None:
        raise AuthenticationError("invalid credentials")

    if not user.is_active:
        raise AuthenticationError("invalid credentials")

    active = await memberships.list_for_user(user.id, active_only=True)
    # Guardrail: only embed tenant_id when a membership exists.
    tenant_id = active[0].organization_id if active else None

    return await _issue_tokens(
        user_id=user.id,
        email=user.email,
        tenant_id=tenant_id,
        sessions=sessions,
        user_agent=user_agent,
        ip_address=ip_address,
    )


async def refresh(
    refresh_token: str,
    *,
    users: UserRepositoryPort,
    memberships: MembershipRepositoryPort,
    sessions: SessionRepositoryPort,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthResult:
    try:
        payload = decode_refresh_token(refresh_token)
    except (InvalidTokenError, ExpiredTokenError) as e:
        raise AuthenticationError("invalid refresh token") from e

    stored = await sessions.get_by_refresh_hash(hash_refresh_token(refresh_token))
    if stored is None or stored.revoked_at is not None:
        raise AuthenticationError("session not found or revoked")
    if stored.expires_at <= datetime.now(UTC):
        raise AuthenticationError("session expired")

    user = await users.get_by_id(UUID(payload.sub))
    if user is None or not user.is_active:
        raise AuthenticationError("user not found or inactive")

    # Rotate: revoke old FIRST, then mint new. Prevents a window where both are valid.
    await sessions.revoke(stored.id)

    active = await memberships.list_for_user(user.id, active_only=True)
    # Note: refresh does NOT preserve the previously-active tenant selection —
    # it picks the user's first active membership. Explicit org-switch endpoint
    # will replace this behavior later.
    tenant_id = active[0].organization_id if active else None

    return await _issue_tokens(
        user_id=user.id,
        email=user.email,
        tenant_id=tenant_id,
        sessions=sessions,
        user_agent=user_agent,
        ip_address=ip_address,
    )


async def logout(
    refresh_token: str,
    *,
    sessions: SessionRepositoryPort,
) -> None:
    """Idempotent — revoking a missing/already-revoked session is a no-op success."""
    stored = await sessions.get_by_refresh_hash(hash_refresh_token(refresh_token))
    if stored is not None and stored.revoked_at is None:
        await sessions.revoke(stored.id)
