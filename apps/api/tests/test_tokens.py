"""JWT create/decode, expiry, tampering, refresh-hash stability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.infrastructure.config import get_settings
from app.infrastructure.security import (
    ExpiredTokenError,
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)


def test_access_token_roundtrip() -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    token = create_access_token(subject=user_id, tenant_id=tenant_id)
    payload = decode_token(token)
    assert payload.sub == str(user_id)
    assert payload.tenant_id == str(tenant_id)
    assert payload.type == "access"


def test_access_token_without_tenant() -> None:
    payload = decode_token(create_access_token(subject=uuid4()))
    assert payload.tenant_id is None
    assert payload.type == "access"


def test_refresh_token_roundtrip() -> None:
    user_id = uuid4()
    jti = uuid4()
    payload = decode_token(create_refresh_token(subject=user_id, jti=jti))
    assert payload.sub == str(user_id)
    assert payload.jti == str(jti)
    assert payload.type == "refresh"


def test_expired_token_raises() -> None:
    s = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=5)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "iat": int(past.timestamp()),
            "exp": int(past.timestamp()),
        },
        s.jwt_secret_key,
        algorithm=s.jwt_algorithm,
    )
    with pytest.raises(ExpiredTokenError):
        decode_token(token)


def test_tampered_token_raises() -> None:
    token = create_access_token(subject=uuid4())
    # Corrupt the signature segment (last-char flip can be a base64 no-op).
    h, p, sig = token.rsplit(".", 2)
    tampered = f"{h}.{p}.{'A' * len(sig)}"
    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_wrong_type_detectable_on_payload() -> None:
    access = decode_token(create_access_token(subject=uuid4()))
    refresh = decode_token(create_refresh_token(subject=uuid4(), jti=uuid4()))
    assert access.type == "access"
    assert refresh.type == "refresh"


def test_hash_refresh_token_stable_and_distinct() -> None:
    a = "some.refresh.token"
    b = "another.refresh.token"
    assert hash_refresh_token(a) == hash_refresh_token(a)
    assert hash_refresh_token(a) != hash_refresh_token(b)
    assert len(hash_refresh_token(a)) == 64  # sha256 hex
