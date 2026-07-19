"""End-to-end auth flow: register, login, refresh, logout, get_current_user."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.config import get_settings
from app.infrastructure.db.models import Membership, Organization, Session, User
from app.presentation.http.deps import CurrentUserDep


async def _register(client: AsyncClient, **overrides: object) -> dict:
    payload = {
        "email": "alice@example.com",
        "password": "correct horse battery staple",
        "organization_name": "Alice Co",
        **overrides,
    }
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_register_creates_user_org_membership(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    body = await _register(db_client)

    assert body["email"] == "alice@example.com"
    assert body["active_tenant_id"] is not None
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0

    users = (await db_session.execute(select(User))).scalars().all()
    assert [u.email for u in users] == ["alice@example.com"]

    orgs = (await db_session.execute(select(Organization))).scalars().all()
    assert len(orgs) == 1
    assert orgs[0].slug.startswith("alice-co")

    mems = (await db_session.execute(select(Membership))).scalars().all()
    assert len(mems) == 1
    assert str(mems[0].organization_id) == body["active_tenant_id"]
    assert mems[0].status == "active"

    sessions = (await db_session.execute(select(Session))).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is None


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(db_client: AsyncClient) -> None:
    await _register(db_client)
    r = await db_client.post(
        "/api/v1/auth/register",
        json={"email": "ALICE@example.com", "password": "another password 12345"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_already_registered"


@pytest.mark.asyncio
async def test_login_success(db_client: AsyncClient) -> None:
    await _register(db_client)
    r = await db_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery staple"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["active_tenant_id"] is not None
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_generic_401(db_client: AsyncClient) -> None:
    await _register(db_client)
    r = await db_client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_login_unknown_user_returns_same_generic_401(
    db_client: AsyncClient,
) -> None:
    r = await db_client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "anything at all"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_refresh_rotates_and_reuse_is_rejected(db_client: AsyncClient) -> None:
    body = await _register(db_client)
    old_refresh = body["refresh_token"]

    r = await db_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new_body = r.json()
    assert new_body["refresh_token"] != old_refresh
    assert new_body["access_token"]

    # Replay old refresh → 401.
    replay = await db_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_is_rejected(db_client: AsyncClient) -> None:
    body = await _register(db_client)
    r = await db_client.post("/api/v1/auth/refresh", json={"refresh_token": body["access_token"]})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_and_is_idempotent(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    body = await _register(db_client)
    refresh = body["refresh_token"]

    r1 = await db_client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert r1.status_code == 204

    r2 = await db_client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert r2.status_code == 204

    sessions = (await db_session.execute(select(Session))).scalars().all()
    assert len(sessions) == 1
    assert sessions[0].revoked_at is not None

    # After logout, refresh must fail too.
    r3 = await db_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r3.status_code == 401


# --- get_current_user via a tiny protected route ----------------------------


@pytest_asyncio.fixture
async def me_app(db_app):  # type: ignore[no-untyped-def]
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/_test/me")
    async def me(user: CurrentUserDep) -> dict[str, str]:
        return {"id": str(user.id), "email": user.email}

    db_app.include_router(router)
    return db_app


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_bearer(me_app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=me_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/_test/me")
        assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_get_current_user_accepts_valid_token(me_app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=me_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await c.post(
            "/api/v1/auth/register",
            json={"email": "bob@example.com", "password": "long enough password"},
        )
        access = reg.json()["access_token"]
        r = await c.get("/_test/me", headers={"Authorization": f"Bearer {access}"})
        assert r.status_code == 200
        assert r.json()["email"] == "bob@example.com"


@pytest.mark.asyncio
async def test_get_current_user_rejects_tampered_token(me_app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=me_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await c.post(
            "/api/v1/auth/register",
            json={"email": "carol@example.com", "password": "long enough password"},
        )
        access = reg.json()["access_token"]
        # Corrupt the signature segment (JWT = header.payload.signature).
        h, p, sig = access.rsplit(".", 2)
        tampered = f"{h}.{p}.{'A' * len(sig)}"
        r = await c.get("/_test/me", headers={"Authorization": f"Bearer {tampered}"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_expired_token(me_app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    s = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=5)
    expired = jwt.encode(
        {
            "sub": str(uuid4()),
            "type": "access",
            "iat": int(past.timestamp()),
            "exp": int(past.timestamp()),
        },
        s.jwt_secret_key,
        algorithm=s.jwt_algorithm,
    )
    transport = ASGITransport(app=me_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/_test/me", headers={"Authorization": f"Bearer {expired}"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_refresh_token_used_as_access(me_app) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=me_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await c.post(
            "/api/v1/auth/register",
            json={"email": "dave@example.com", "password": "long enough password"},
        )
        refresh = reg.json()["refresh_token"]
        r = await c.get("/_test/me", headers={"Authorization": f"Bearer {refresh}"})
        assert r.status_code == 401
