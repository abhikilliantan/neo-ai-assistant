"""Conversation read endpoints + streaming persistence + HTTP-layer tenant isolation."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
    return events


# --- streaming persistence --------------------------------------------------


@pytest.mark.asyncio
async def test_stream_meta_frame_first_and_assistant_persisted(db_app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register(c, "stream-persist@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hello stream"}]},
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        assert events[0]["type"] == "meta"
        conv_id = events[0]["conversation_id"]
        assert conv_id
        deltas = [e for e in events if e["type"] == "delta"]
        assert deltas, "expected at least one delta"
        full = "".join(d["content"] for d in deltas)
        assert full == "(mock) hello stream"
        assert events[-1]["type"] == "done"

        # After the stream finishes, the assistant row is persisted via the
        # second short tenant write-txn (Txn B) inside the generator.
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        body = detail.json()
        assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
        assert body["messages"][0]["content"] == "hello stream"
        assert body["messages"][1]["content"] == full
        assert body["messages"][1]["model"] == "mock-1"


@pytest.mark.asyncio
async def test_stream_with_unknown_conversation_id_returns_404(db_app) -> None:  # type: ignore[no-untyped-def]
    from uuid import uuid4

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register(c, "stream-404@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "conversation_id": str(uuid4()),
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"


# --- conversation read endpoints -------------------------------------------


@pytest.mark.asyncio
async def test_list_conversations_requires_auth(db_client: AsyncClient) -> None:
    r = await db_client.get("/api/v1/conversations")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_get_conversation_requires_auth(db_client: AsyncClient) -> None:
    from uuid import uuid4

    r = await db_client.get(f"/api/v1/conversations/{uuid4()}")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_empty_when_no_conversations(db_client: AsyncClient) -> None:
    token = await _register(db_client, "empty-list@example.com")
    r = await db_client.get("/api/v1/conversations", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


# --- HTTP-layer tenant isolation --------------------------------------------


@pytest.mark.asyncio
async def test_org_B_cannot_see_org_A_conversation(db_client: AsyncClient) -> None:
    # Alice (org A) creates a conversation.
    alice = await _register(db_client, "alice-iso@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {alice}"},
        json={"messages": [{"role": "user", "content": "alice's turn"}]},
    )
    assert r.status_code == 200
    alice_conv_id = r.json()["conversation_id"]

    # Bob (org B — separate register → separate org).
    bob = await _register(db_client, "bob-iso@example.com")

    # Bob's list must not include Alice's conversation.
    lst = await db_client.get("/api/v1/conversations", headers={"Authorization": f"Bearer {bob}"})
    assert lst.status_code == 200
    assert alice_conv_id not in [c["id"] for c in lst.json()]

    # Bob GET on Alice's conversation → 404 (RLS makes it invisible; no
    # existence oracle across tenants).
    detail = await db_client.get(
        f"/api/v1/conversations/{alice_conv_id}",
        headers={"Authorization": f"Bearer {bob}"},
    )
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "not_found"

    # And Bob trying to POST /chat with Alice's conversation_id → 404 (same reason).
    post = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {bob}"},
        json={
            "conversation_id": alice_conv_id,
            "messages": [{"role": "user", "content": "hijack attempt"}],
        },
    )
    assert post.status_code == 404
