"""Conversation management — DELETE (soft) + PATCH (rename), owner-scoped.

The reads (list/get) are org-scoped, but mutations are OWNER-scoped: mirroring
DELETE /memories/{id}, a same-tenant user must not delete or rename another
user's thread. Unknown / cross-tenant / same-tenant-other-user all collapse to
404 (no existence oracle).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import Membership, Role


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_conversation(client: AsyncClient, token: str, text: str = "hello") -> str:
    """Create a thread by sending one chat turn; return its conversation_id."""
    r = await client.post(
        "/api/v1/chat",
        headers=_auth(token),
        json={"messages": [{"role": "user", "content": text}]},
    )
    assert r.status_code == 200, r.text
    return r.json()["conversation_id"]  # type: ignore[no-any-return]


async def _make_second_user_in_org(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    email: str,
    organization_id: UUID,
) -> dict[str, Any]:
    """Register a second user and move them into `organization_id` (attach an
    active membership, drop their register-time solo org), then log in so their
    token's active tenant is the shared org. Mirrors the memories test helper."""
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
    assert body["active_tenant_id"] == str(organization_id)
    return body  # type: ignore[no-any-return]


def _list_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [c["id"] for c in rows]


# --- DELETE -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_own_conversation_204_and_gone_from_list(db_client: AsyncClient) -> None:
    token = (await _register(db_client, "conv-del-own@example.com"))["access_token"]
    conv_id = await _new_conversation(db_client, token)

    lst = await db_client.get("/api/v1/conversations", headers=_auth(token))
    assert conv_id in _list_ids(lst.json())

    d = await db_client.delete(f"/api/v1/conversations/{conv_id}", headers=_auth(token))
    assert d.status_code == 204, d.text

    # Gone from the (soft-delete-aware) list, and a direct GET is now 404.
    lst2 = await db_client.get("/api/v1/conversations", headers=_auth(token))
    assert conv_id not in _list_ids(lst2.json())
    g = await db_client.get(f"/api/v1/conversations/{conv_id}", headers=_auth(token))
    assert g.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_conversation_404(db_client: AsyncClient) -> None:
    token = (await _register(db_client, "conv-del-unknown@example.com"))["access_token"]
    d = await db_client.delete(f"/api/v1/conversations/{uuid4()}", headers=_auth(token))
    assert d.status_code == 404
    assert d.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_delete_cross_tenant_conversation_404_and_survives(db_client: AsyncClient) -> None:
    alice = (await _register(db_client, "conv-del-alice@example.com"))["access_token"]
    conv_id = await _new_conversation(db_client, alice)

    bob = (await _register(db_client, "conv-del-bob@example.com"))["access_token"]
    d = await db_client.delete(f"/api/v1/conversations/{conv_id}", headers=_auth(bob))
    assert d.status_code == 404  # RLS-hidden → no existence oracle

    # Alice's conversation is untouched.
    lst = await db_client.get("/api/v1/conversations", headers=_auth(alice))
    assert conv_id in _list_ids(lst.json())


@pytest.mark.asyncio
async def test_delete_same_tenant_other_user_404_and_survives(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    a1 = await _register(db_client, "conv-del-a1@example.com")
    org_id = UUID(a1["active_tenant_id"])
    conv_id = await _new_conversation(db_client, a1["access_token"])

    a2 = await _make_second_user_in_org(
        db_client, db_session, email="conv-del-a2@example.com", organization_id=org_id
    )
    # A2 is in the SAME org (RLS lets them see it) but is NOT the owner.
    d = await db_client.delete(
        f"/api/v1/conversations/{conv_id}", headers=_auth(a2["access_token"])
    )
    assert d.status_code == 404

    # The owner's thread survives the failed delete.
    lst = await db_client.get("/api/v1/conversations", headers=_auth(a1["access_token"]))
    assert conv_id in _list_ids(lst.json())


# --- PATCH (rename) ---------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_own_conversation_updates_title(db_client: AsyncClient) -> None:
    token = (await _register(db_client, "conv-rename-own@example.com"))["access_token"]
    conv_id = await _new_conversation(db_client, token)

    r = await db_client.patch(
        f"/api/v1/conversations/{conv_id}",
        headers=_auth(token),
        json={"title": "  Quarterly planning  "},  # trimmed by the validator
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == conv_id
    assert r.json()["title"] == "Quarterly planning"

    # Persisted: the list reflects the new title.
    lst = await db_client.get("/api/v1/conversations", headers=_auth(token))
    got = {c["id"]: c["title"] for c in lst.json()}
    assert got[conv_id] == "Quarterly planning"


@pytest.mark.asyncio
async def test_rename_blank_title_rejected_422(db_client: AsyncClient) -> None:
    token = (await _register(db_client, "conv-rename-blank@example.com"))["access_token"]
    conv_id = await _new_conversation(db_client, token)
    r = await db_client.patch(
        f"/api/v1/conversations/{conv_id}", headers=_auth(token), json={"title": "   "}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_rename_same_tenant_other_user_404_and_unchanged(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    a1 = await _register(db_client, "conv-rename-a1@example.com")
    org_id = UUID(a1["active_tenant_id"])
    conv_id = await _new_conversation(db_client, a1["access_token"])
    await db_client.patch(
        f"/api/v1/conversations/{conv_id}",
        headers=_auth(a1["access_token"]),
        json={"title": "owner title"},
    )

    a2 = await _make_second_user_in_org(
        db_client, db_session, email="conv-rename-a2@example.com", organization_id=org_id
    )
    r = await db_client.patch(
        f"/api/v1/conversations/{conv_id}",
        headers=_auth(a2["access_token"]),
        json={"title": "hijacked title"},
    )
    assert r.status_code == 404

    # Owner's title is unchanged.
    lst = await db_client.get("/api/v1/conversations", headers=_auth(a1["access_token"]))
    got = {c["id"]: c["title"] for c in lst.json()}
    assert got[conv_id] == "owner title"
