"""JWT access + refresh tokens.

Access tokens carry (sub, tenant_id, type='access'). Refresh tokens carry
(sub, jti, type='refresh') — the jti is what a sessions row keys off to
revoke a specific refresh token.

We persist the SHA-256 hex of the raw refresh token in sessions.refresh_token_hash
(via `hash_refresh_token`) — SHA-256 is a lookup index; the token itself is
already high-entropy so KDF-grade hashing isn't required.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

import jwt
from pydantic import BaseModel, ValidationError

from app.infrastructure.config import get_settings


class InvalidTokenError(Exception):
    """Token failed signature check, is malformed, or has bad claims."""


class ExpiredTokenError(InvalidTokenError):
    """Token signature is valid but `exp` is in the past."""


class TokenPayload(BaseModel):
    sub: str
    type: Literal["access", "refresh"]
    iat: int
    exp: int
    jti: str | None = None
    tenant_id: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(claims: dict[str, Any]) -> str:
    s = get_settings()
    return jwt.encode(claims, s.jwt_secret_key, algorithm=s.jwt_algorithm)


def create_access_token(
    subject: UUID | str,
    tenant_id: UUID | str | None = None,
    **extra: Any,
) -> str:
    s = get_settings()
    now = _now()
    claims: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.access_token_expire_minutes)).timestamp()),
        "tenant_id": str(tenant_id) if tenant_id is not None else None,
        **extra,
    }
    return _encode(claims)


def create_refresh_token(subject: UUID | str, jti: UUID | str) -> str:
    s = get_settings()
    now = _now()
    claims: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=s.refresh_token_expire_days)).timestamp()),
        "jti": str(jti),
    }
    return _encode(claims)


def decode_token(token: str) -> TokenPayload:
    """Verify signature + expiry, then validate claim shape. Raises on any failure."""
    s = get_settings()
    try:
        raw = jwt.decode(token, s.jwt_secret_key, algorithms=[s.jwt_algorithm])
    except jwt.ExpiredSignatureError as e:
        raise ExpiredTokenError("token has expired") from e
    except jwt.PyJWTError as e:
        raise InvalidTokenError(f"invalid token: {e}") from e

    try:
        return TokenPayload.model_validate(raw)
    except ValidationError as e:
        raise InvalidTokenError(f"invalid token claims: {e}") from e


def decode_access_token(token: str) -> TokenPayload:
    """Decode + require `type == "access"`. Raises InvalidTokenError on mismatch."""
    payload = decode_token(token)
    if payload.type != "access":
        raise InvalidTokenError(f"expected access token, got {payload.type!r}")
    return payload


def decode_refresh_token(token: str) -> TokenPayload:
    """Decode + require `type == "refresh"`. Raises InvalidTokenError on mismatch."""
    payload = decode_token(token)
    if payload.type != "refresh":
        raise InvalidTokenError(f"expected refresh token, got {payload.type!r}")
    return payload


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex — deterministic lookup key for sessions.refresh_token_hash."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
