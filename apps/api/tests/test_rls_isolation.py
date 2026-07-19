"""RLS isolation + prod safety: `/_test/*` routes are unreachable in prod.

Requires: migrations applied (RLS ENABLE + FORCE + policies), and the
`neo_app` role provisioned (both done by alembic upgrade head).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import ApiKey, Membership, Organization, Role, User
from app.presentation.http.deps import TenantSessionDep


async def _seed_two_tenants(db_session: AsyncSession) -> tuple[UUID, UUID]:
    """As neo (bypasses RLS): create orgs A and B, each with a user + membership + api key."""
    owner = (await db_session.execute(select(Role).where(Role.name == "owner"))).scalar_one()

    org_a = Organization(name="Org A", slug="org-a")
    org_b = Organization(name="Org B", slug="org-b")
    user_a = User(email="alice@a.example", password_hash="x")
    user_b = User(email="bob@b.example", password_hash="x")
    db_session.add_all([org_a, org_b, user_a, user_b])
    await db_session.flush()

    db_session.add_all(
        [
            Membership(user_id=user_a.id, organization_id=org_a.id, role_id=owner.id),
            Membership(user_id=user_b.id, organization_id=org_b.id, role_id=owner.id),
            ApiKey(
                organization_id=org_a.id,
                name="A key",
                key_prefix="a_",
                key_hash="ha",
            ),
            ApiKey(
                organization_id=org_b.id,
                name="B key",
                key_prefix="b_",
                key_hash="hb",
            ),
        ]
    )
    await db_session.commit()
    return org_a.id, org_b.id


@pytest.mark.asyncio
async def test_neo_app_confirms_it_is_not_privileged(app_engine) -> None:  # type: ignore[no-untyped-def]
    """Sanity: the runtime role is non-superuser + non-BYPASSRLS."""
    async with app_engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            )
        ).one()
    assert row.current_user == "neo_app"
    assert row.rolsuper is False
    assert row.rolbypassrls is False


@pytest.mark.asyncio
async def test_no_tenant_context_hides_everything(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    await _seed_two_tenants(db_session)
    s = await app_session_factory(None)
    try:
        mems = (await s.execute(select(Membership))).scalars().all()
        keys = (await s.execute(select(ApiKey))).scalars().all()
        assert mems == []
        assert keys == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_tenant_context_A_sees_only_A(db_session: AsyncSession, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    org_a, org_b = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        mem_orgs = [
            m.organization_id for m in (await s.execute(select(Membership))).scalars().all()
        ]
        key_orgs = [k.organization_id for k in (await s.execute(select(ApiKey))).scalars().all()]
        assert mem_orgs == [org_a]
        assert key_orgs == [org_a]
        assert org_b not in mem_orgs
        assert org_b not in key_orgs
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_tenant_context_B_sees_only_B(db_session: AsyncSession, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    org_a, org_b = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_b)
    try:
        mem_orgs = [
            m.organization_id for m in (await s.execute(select(Membership))).scalars().all()
        ]
        assert mem_orgs == [org_b]
        assert org_a not in mem_orgs
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_where_clause_targeting_other_tenant_is_still_filtered(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """RLS applies BEFORE the WHERE — a targeted cross-tenant query returns nothing."""
    org_a, org_b = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        stmt = select(Membership).where(Membership.organization_id == org_b)
        rows = (await s.execute(stmt)).scalars().all()
        assert rows == []
        # Same for api_keys.
        stmt2 = select(ApiKey).where(ApiKey.organization_id == org_b)
        assert (await s.execute(stmt2)).scalars().all() == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_full_auth_flow_under_role_split(db_app, db_session: AsyncSession) -> None:  # type: ignore[no-untyped-def]
    """End-to-end: two users register (system bootstrap), each hits a tenant-scoped
    test route (RLS-scoped via TenantSessionDep) and sees only their own api_keys.
    """
    from fastapi import APIRouter
    from httpx import ASGITransport, AsyncClient

    router = APIRouter()

    @router.get("/_test/api-keys")
    async def _list_keys(session: TenantSessionDep) -> list[dict[str, str]]:
        rows = (await session.execute(select(ApiKey))).scalars().all()
        return [{"id": str(k.id), "name": k.name} for k in rows]

    db_app.include_router(router)

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Register two users — creates orgs A and B via system bootstrap.
        ra = await c.post(
            "/api/v1/auth/register",
            json={"email": "alice@aflow.example", "password": "password12345"},
        )
        assert ra.status_code == 201, ra.text
        rb = await c.post(
            "/api/v1/auth/register",
            json={"email": "bob@bflow.example", "password": "password12345"},
        )
        assert rb.status_code == 201, rb.text

        # As neo (admin session), attach one api key per org.
        alice_tenant = UUID(ra.json()["active_tenant_id"])
        bob_tenant = UUID(rb.json()["active_tenant_id"])
        db_session.add_all(
            [
                ApiKey(
                    organization_id=alice_tenant,
                    name="alice-key",
                    key_prefix="a_",
                    key_hash="ha",
                    expires_at=datetime.now(UTC),
                ),
                ApiKey(
                    organization_id=bob_tenant,
                    name="bob-key",
                    key_prefix="b_",
                    key_hash="hb",
                    expires_at=datetime.now(UTC),
                ),
            ]
        )
        await db_session.commit()

        # Alice's token → sees alice-key only.
        alice_access = ra.json()["access_token"]
        r_alice = await c.get(
            "/_test/api-keys",
            headers={"Authorization": f"Bearer {alice_access}"},
        )
        assert r_alice.status_code == 200, r_alice.text
        assert [k["name"] for k in r_alice.json()] == ["alice-key"]

        # Bob's token → sees bob-key only.
        bob_access = rb.json()["access_token"]
        r_bob = await c.get(
            "/_test/api-keys",
            headers={"Authorization": f"Bearer {bob_access}"},
        )
        assert r_bob.status_code == 200, r_bob.text
        assert [k["name"] for k in r_bob.json()] == ["bob-key"]


@pytest.mark.asyncio
async def test_neo_app_cannot_bypass_via_reset_role(app_engine) -> None:  # type: ignore[no-untyped-def]
    """neo_app is not a superuser — SET ROLE to a privileged role must be forbidden."""
    from sqlalchemy.exc import DBAPIError

    async with app_engine.connect() as conn:
        with pytest.raises(DBAPIError):
            await conn.execute(text("SET ROLE neo"))


@pytest.mark.asyncio
async def test_can_still_insert_into_own_tenant(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """WITH CHECK: inserting into own tenant works; wrong-tenant insert is rejected."""
    org_a, org_b = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        # Insert into A is allowed.
        s.add(
            ApiKey(
                organization_id=org_a,
                name="new A key",
                key_prefix="a2",
                key_hash="ha2",
            )
        )
        await s.flush()
        # Insert into B is rejected by WITH CHECK.
        s.add(
            ApiKey(
                organization_id=org_b,
                name="sneaky B key",
                key_prefix="bs",
                key_hash="hbs",
            )
        )
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(DBAPIError):
            await s.flush()
    finally:
        await s.rollback()
        await s.close()


@pytest.mark.asyncio
async def test_prod_app_blocks_underscore_test_paths() -> None:
    """create_app with python_env != 'test' must return 404 for any /_test/* URL,
    even if someone accidentally mounted a router there."""
    from fastapi import APIRouter
    from httpx import ASGITransport, AsyncClient

    from app.infrastructure.config import Settings
    from app.main import create_app

    prod_like = Settings(
        python_env="production",
        database_url="postgresql+asyncpg://x/x",
        app_database_url="postgresql+asyncpg://x/x",
        redis_url="redis://x",
        jwt_secret_key="test-secret-key-at-least-32-bytes-long-xxxxx",
    )
    app = create_app(prod_like)
    app.state.database = None
    app.state.system_database = None
    app.state.redis = None
    app.state.health_checks = []

    # Simulate the accidental case: register a /_test/* route on prod app.
    r = APIRouter()

    @r.get("/_test/leak")
    async def _leak() -> dict[str, str]:
        return {"leaked": "yes"}

    app.include_router(r)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/_test/leak")
        assert resp.status_code == 404
        assert resp.json() == {"error": "not found"}
        # Sanity: a real route (/health) still works.
        assert (await c.get("/health")).status_code == 200
