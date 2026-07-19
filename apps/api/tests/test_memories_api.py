"""Phase 5e-1 — memory management API.

Covers:
  - GET /api/v1/memories       (list, user + tenant scoped)
  - DELETE /api/v1/memories/{id}  (soft-delete, own-check + RLS)
  - GET /api/v1/preferences    (list, user + tenant scoped)
  - PUT /api/v1/preferences/{k}   (upsert)

The two isolation properties the tests exercise:
  - RLS keeps cross-tenant rows invisible → cross-tenant DELETE → 404.
  - user_id filter/check keeps same-tenant users from touching each other's
    rows → same-tenant-different-user DELETE → 404.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.infrastructure.db.models import Membership, Memory, Role
from app.infrastructure.db.repositories import MemoryRepository, UserPreferenceRepository


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _make_second_user_in_org(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    email: str,
    organization_id: UUID,
) -> dict[str, Any]:
    """Register a second user, then move them into `organization_id` and log
    them in so their token's active_tenant_id points at the target org.

    Registration always spins up a fresh personal org for the new user, but
    the tenant-selection use case picks the oldest active membership
    (created_at asc). To make login pick the shared org we:
      1) attach a new active Membership to the target org, and
      2) delete the register-time membership (their solo org).
    Uses the privileged `db_session` (neo, RLS bypassed).

    This is only needed for the "two users in one tenant" tests — a real
    invite flow doesn't exist yet in this codebase.
    """
    reg = await _register(client, email)
    user_id = UUID(reg["user_id"])

    role = (await db_session.execute(select(Role).where(Role.name == "owner"))).scalar_one()
    db_session.add(
        Membership(
            user_id=user_id,
            organization_id=organization_id,
            role_id=role.id,
            status="active",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id)
        .where(Membership.organization_id != organization_id)
    )
    for m in (await db_session.execute(stmt)).scalars().all():
        await db_session.delete(m)
    await db_session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password12345"},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["active_tenant_id"] == str(organization_id), (
        f"expected active tenant {organization_id}, got {body['active_tenant_id']}"
    )
    return body  # type: ignore[no-any-return]


async def _seed_memory(
    app_session_factory,  # type: ignore[no-untyped-def]
    *,
    tenant_id: UUID,
    user_id: UUID,
    content: str,
) -> UUID:
    provider = MockEmbeddingProvider()
    result = await provider.embed(texts=[content])
    s = await app_session_factory(tenant_id)
    try:
        m = await MemoryRepository(s).add(
            organization_id=tenant_id,
            user_id=user_id,
            content=content,
            embedding=result.vectors[0],
            embedding_model=result.model,
        )
        await s.commit()
        return m.id
    finally:
        await s.close()


# --- auth --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memories_endpoints_require_auth(db_client: AsyncClient) -> None:
    cases = [
        ("GET", "/api/v1/memories", None),
        ("DELETE", f"/api/v1/memories/{uuid4()}", None),
        ("GET", "/api/v1/preferences", None),
        ("PUT", "/api/v1/preferences/foo", {"value": "x"}),
    ]
    for method, path, body in cases:
        if method == "GET":
            r = await db_client.get(path)
        elif method == "DELETE":
            r = await db_client.delete(path)
        else:
            r = await db_client.put(path, json=body)
        assert r.status_code == 401, f"{method} {path}: {r.status_code} {r.text}"
        assert r.json()["error"]["code"] == "authentication_failed"


# --- listing: user + tenant scoping -----------------------------------------


@pytest.mark.asyncio
async def test_list_memories_returns_only_current_user_rows(
    db_app,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """A1 lists → only A1's rows: not A2's (same tenant, different user),
    not B1's (different tenant). Covers both scoping axes in one assertion.
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        a1 = await _register(c, "5e1-a1@example.com")
        a1_token = a1["access_token"]
        tenant_a = UUID(a1["active_tenant_id"])
        a1_user = UUID(a1["user_id"])

        a2 = await _make_second_user_in_org(
            c, db_session, email="5e1-a2@example.com", organization_id=tenant_a
        )
        a2_user = UUID(a2["user_id"])

        b1 = await _register(c, "5e1-b1@example.com")
        tenant_b = UUID(b1["active_tenant_id"])
        b1_user = UUID(b1["user_id"])

        m1 = await _seed_memory(
            app_session_factory, tenant_id=tenant_a, user_id=a1_user, content="a1-one"
        )
        m2 = await _seed_memory(
            app_session_factory, tenant_id=tenant_a, user_id=a1_user, content="a1-two"
        )
        await _seed_memory(
            app_session_factory, tenant_id=tenant_a, user_id=a2_user, content="a2-only"
        )
        await _seed_memory(
            app_session_factory, tenant_id=tenant_b, user_id=b1_user, content="b1-only"
        )

        r = await c.get(
            "/api/v1/memories",
            headers={"Authorization": f"Bearer {a1_token}"},
        )
        assert r.status_code == 200, r.text
        got = r.json()
        ids = {row["id"] for row in got}
        assert ids == {str(m1), str(m2)}, ids
        contents = {row["content"] for row in got}
        assert contents == {"a1-one", "a1-two"}

        # Response shape whitelist: no embedding, no user_id, no org_id.
        for row in got:
            assert set(row.keys()) == {"id", "content", "kind", "source", "created_at"}


# --- DELETE: own → 204, then hidden ------------------------------------------


@pytest.mark.asyncio
async def test_delete_own_memory_soft_deletes(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        a1 = await _register(c, "5e1-del-own@example.com")
        token = a1["access_token"]
        tenant = UUID(a1["active_tenant_id"])
        user_id = UUID(a1["user_id"])
        m_id = await _seed_memory(
            app_session_factory, tenant_id=tenant, user_id=user_id, content="ephemeral"
        )

        d = await c.delete(
            f"/api/v1/memories/{m_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert d.status_code == 204, d.text
        assert d.content == b""

        r = await c.get("/api/v1/memories", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []

    s = await app_session_factory(tenant)
    try:
        row = (await s.execute(select(Memory).where(Memory.id == m_id))).scalar_one()
        assert row.deleted_at is not None
    finally:
        await s.close()


# --- DELETE: same tenant, different user → 404 (the ownership guard) --------


@pytest.mark.asyncio
async def test_delete_other_users_memory_same_tenant_returns_404(
    db_app,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """The point of the endpoint-layer ownership check: A1 must NOT be able
    to delete A2's memory even though RLS lets A1 see it (same tenant).
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        a1 = await _register(c, "5e1-guard-a1@example.com")
        tenant = UUID(a1["active_tenant_id"])
        a1_token = a1["access_token"]

        a2 = await _make_second_user_in_org(
            c, db_session, email="5e1-guard-a2@example.com", organization_id=tenant
        )
        a2_user = UUID(a2["user_id"])

        a2_mem_id = await _seed_memory(
            app_session_factory, tenant_id=tenant, user_id=a2_user, content="a2 secret"
        )

        r = await c.delete(
            f"/api/v1/memories/{a2_mem_id}",
            headers={"Authorization": f"Bearer {a1_token}"},
        )
        assert r.status_code == 404, r.text
        assert r.json()["error"]["code"] == "not_found"

    # Row is NOT soft-deleted — the guard blocked it before soft_delete ran.
    s = await app_session_factory(tenant)
    try:
        row = (await s.execute(select(Memory).where(Memory.id == a2_mem_id))).scalar_one()
        assert row.deleted_at is None
    finally:
        await s.close()


# --- DELETE: cross-tenant → 404 (RLS hides existence) -----------------------


@pytest.mark.asyncio
async def test_delete_cross_tenant_memory_returns_404(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        a1 = await _register(c, "5e1-xtenant-a@example.com")
        b1 = await _register(c, "5e1-xtenant-b@example.com")

        b_mem_id = await _seed_memory(
            app_session_factory,
            tenant_id=UUID(b1["active_tenant_id"]),
            user_id=UUID(b1["user_id"]),
            content="b1 secret",
        )

        r = await c.delete(
            f"/api/v1/memories/{b_mem_id}",
            headers={"Authorization": f"Bearer {a1['access_token']}"},
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_delete_random_uuid_returns_404(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "5e1-del-nonexistent@example.com")
    r = await db_client.delete(
        f"/api/v1/memories/{uuid4()}",
        headers={"Authorization": f"Bearer {reg['access_token']}"},
    )
    assert r.status_code == 404


# --- preferences: upsert round-trip + idempotency ---------------------------


@pytest.mark.asyncio
async def test_preferences_round_trip_and_update_in_place(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "5e1-prefs@example.com")
        token = reg["access_token"]
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        r1 = await c.put(
            "/api/v1/preferences/tone",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": {"style": "concise", "language": "en"}},
        )
        assert r1.status_code == 200, r1.text
        assert r1.json() == {
            "key": "tone",
            "value": {"style": "concise", "language": "en"},
        }

        g = await c.get("/api/v1/preferences", headers={"Authorization": f"Bearer {token}"})
        assert g.status_code == 200
        assert g.json() == [{"key": "tone", "value": {"style": "concise", "language": "en"}}]

        # Same key again → updates in place, still exactly one row.
        r2 = await c.put(
            "/api/v1/preferences/tone",
            headers={"Authorization": f"Bearer {token}"},
            json={"value": "verbose"},
        )
        assert r2.status_code == 200
        assert r2.json() == {"key": "tone", "value": "verbose"}

    s = await app_session_factory(tenant)
    try:
        rows = await UserPreferenceRepository(s).list_for_user(
            organization_id=tenant, user_id=user_id
        )
        assert len(rows) == 1
        assert rows[0].key == "tone"
        assert rows[0].value == "verbose"
    finally:
        await s.close()


# --- preferences: user + tenant isolation -----------------------------------


@pytest.mark.asyncio
async def test_preferences_isolated_across_users_and_tenants(
    db_app,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        a1 = await _register(c, "5e1-pref-a1@example.com")
        tenant_a = UUID(a1["active_tenant_id"])
        a2 = await _make_second_user_in_org(
            c, db_session, email="5e1-pref-a2@example.com", organization_id=tenant_a
        )
        b1 = await _register(c, "5e1-pref-b1@example.com")

        for actor, val in (
            (a1["access_token"], "a1-value"),
            (a2["access_token"], "a2-value"),
            (b1["access_token"], "b1-value"),
        ):
            r = await c.put(
                "/api/v1/preferences/nickname",
                headers={"Authorization": f"Bearer {actor}"},
                json={"value": val},
            )
            assert r.status_code == 200, r.text

        for actor, expected in (
            (a1["access_token"], "a1-value"),
            (a2["access_token"], "a2-value"),
            (b1["access_token"], "b1-value"),
        ):
            r = await c.get(
                "/api/v1/preferences",
                headers={"Authorization": f"Bearer {actor}"},
            )
            assert r.status_code == 200
            assert r.json() == [{"key": "nickname", "value": expected}]
