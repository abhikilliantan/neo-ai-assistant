"""Service API-key auth: generation, management endpoints, whoami, scope +
tenant isolation. DB-backed (real Alembic + RLS), mirroring test_auth_endpoints
and test_rls_isolation.
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import ApiKey
from app.infrastructure.security import generate_api_key, hash_api_key, verify_api_key
from app.presentation.http.deps import PrincipalDep, ServiceSessionDep

# --- unit: generation + verify ----------------------------------------------


def test_generate_api_key_shape_and_verify() -> None:
    g = generate_api_key()
    assert g.raw.startswith("neo_sk_")
    assert g.key_prefix == g.raw[:15]
    assert g.key_hash == hash_api_key(g.raw)
    assert g.key_hash != g.raw  # never store plaintext
    assert verify_api_key(g.raw, g.key_hash) is True
    assert verify_api_key(g.raw + "x", g.key_hash) is False
    assert verify_api_key("garbage", g.key_hash) is False


# --- helpers ----------------------------------------------------------------


async def _register(client: AsyncClient, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345", "organization_name": email},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_key(client: AsyncClient, jwt: str, name: str = "n8n") -> dict:
    r = await client.post(
        "/api/v1/api-keys",
        json={"name": name},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


# --- management endpoints ----------------------------------------------------


@pytest.mark.asyncio
async def test_create_key_returns_plaintext_once_and_stores_only_hash(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "owner@create.example")
    created = await _create_key(db_client, reg["access_token"])

    assert created["api_key"].startswith("neo_sk_")
    assert created["scopes"] == ["read"]
    assert created["key_prefix"] == created["api_key"][:15]

    # DB stores the hash + prefix, never the plaintext.
    row = (await db_session.execute(select(ApiKey))).scalar_one()
    assert row.key_hash == hash_api_key(created["api_key"])
    assert row.key_hash != created["api_key"]

    # List never leaks the secret or hash.
    r = await db_client.get(
        "/api/v1/api-keys", headers={"Authorization": f"Bearer {reg['access_token']}"}
    )
    assert r.status_code == 200, r.text
    listed = r.json()
    assert len(listed) == 1
    assert "api_key" not in listed[0]
    assert "key_hash" not in listed[0]
    assert listed[0]["last_used_at"] is None


@pytest.mark.asyncio
async def test_create_key_rejects_unsupported_scope(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "owner@scope.example")
    r = await db_client.post(
        "/api/v1/api-keys",
        json={"name": "bad", "scopes": ["write"]},
        headers={"Authorization": f"Bearer {reg['access_token']}"},
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "bad_request"


# --- whoami (service-key auth) ----------------------------------------------


@pytest.mark.asyncio
async def test_whoami_with_valid_key_returns_org_and_scopes(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "owner@whoami.example")
    created = await _create_key(db_client, reg["access_token"])
    raw = created["api_key"]

    # Bearer form.
    r = await db_client.get("/api/v1/service/whoami", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"organization_id": reg["active_tenant_id"], "scopes": ["read"]}

    # X-API-Key form works too.
    r2 = await db_client.get("/api/v1/service/whoami", headers={"X-API-Key": raw})
    assert r2.status_code == 200, r2.text
    assert r2.json()["organization_id"] == reg["active_tenant_id"]

    # last_used_at got stamped.
    row = (await db_session.execute(select(ApiKey))).scalar_one()
    assert row.last_used_at is not None


@pytest.mark.asyncio
async def test_whoami_garbage_key_401(db_client: AsyncClient) -> None:
    r = await db_client.get(
        "/api/v1/service/whoami", headers={"Authorization": "Bearer neo_sk_not-a-real-key"}
    )
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_whoami_missing_key_401(db_client: AsyncClient) -> None:
    assert (await db_client.get("/api/v1/service/whoami")).status_code == 401


@pytest.mark.asyncio
async def test_whoami_revoked_key_401(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "owner@revoke.example")
    created = await _create_key(db_client, reg["access_token"])
    raw = created["api_key"]

    # Revoke via the management endpoint.
    r = await db_client.delete(
        f"/api/v1/api-keys/{created['id']}",
        headers={"Authorization": f"Bearer {reg['access_token']}"},
    )
    assert r.status_code == 204, r.text

    r2 = await db_client.get("/api/v1/service/whoami", headers={"Authorization": f"Bearer {raw}"})
    assert r2.status_code == 401, r2.text


@pytest.mark.asyncio
async def test_whoami_missing_scope_403(db_client: AsyncClient, db_session: AsyncSession) -> None:
    """A key with no scopes is authenticated but not authorized for `read`."""
    reg = await _register(db_client, "owner@noscope.example")
    g = generate_api_key()
    db_session.add(
        ApiKey(
            organization_id=reg["active_tenant_id"],
            name="scopeless",
            key_prefix=g.key_prefix,
            key_hash=g.key_hash,
            scopes=[],
        )
    )
    await db_session.commit()

    r = await db_client.get("/api/v1/service/whoami", headers={"Authorization": f"Bearer {g.raw}"})
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "insufficient_scope"


# --- tenant isolation (RLS) --------------------------------------------------


@pytest.mark.asyncio
async def test_service_key_tenant_isolation(db_app, db_client: AsyncClient) -> None:  # type: ignore[no-untyped-def]
    """An org-A key, driving an RLS-scoped session, reads only org-A rows."""
    router = APIRouter()

    @router.get("/_test/service/keys")
    async def _list_keys(session: ServiceSessionDep) -> list[dict[str, str]]:
        rows = (await session.execute(select(ApiKey))).scalars().all()
        return [{"name": k.name} for k in rows]

    db_app.include_router(router)

    reg_a = await _register(db_client, "a@iso.example")
    reg_b = await _register(db_client, "b@iso.example")
    key_a = await _create_key(db_client, reg_a["access_token"], name="A-key")
    await _create_key(db_client, reg_b["access_token"], name="B-key")

    r = await db_client.get(
        "/_test/service/keys", headers={"Authorization": f"Bearer {key_a['api_key']}"}
    )
    assert r.status_code == 200, r.text
    assert [k["name"] for k in r.json()] == ["A-key"]


# --- combined principal (Slice 4): JWT OR key -------------------------------


@pytest.mark.asyncio
async def test_combined_principal_accepts_jwt_and_key(db_app, db_client: AsyncClient) -> None:  # type: ignore[no-untyped-def]
    router = APIRouter()

    @router.get("/_test/principal")
    async def _who(principal: PrincipalDep) -> dict[str, str | None]:
        return {
            "kind": principal.kind,
            "organization_id": str(principal.organization_id),
        }

    db_app.include_router(router)

    reg = await _register(db_client, "combined@iso.example")
    created = await _create_key(db_client, reg["access_token"])
    org = reg["active_tenant_id"]

    r_jwt = await db_client.get(
        "/_test/principal", headers={"Authorization": f"Bearer {reg['access_token']}"}
    )
    assert r_jwt.status_code == 200, r_jwt.text
    assert r_jwt.json() == {"kind": "user", "organization_id": org}

    r_key = await db_client.get(
        "/_test/principal", headers={"Authorization": f"Bearer {created['api_key']}"}
    )
    assert r_key.status_code == 200, r_key.text
    assert r_key.json() == {"kind": "service", "organization_id": org}
