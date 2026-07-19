"""Chat endpoint — mock provider, tenant-scoped session, auth guard."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _register_and_token(client: AsyncClient) -> str:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "chatter@example.com", "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_chat_returns_mock_reply(db_client: AsyncClient) -> None:
    token = await _register_and_token(db_client)
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "hello world"}]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == "(mock) hello world"
    assert body["model"] == "mock-1"
    assert body["usage"] is None
    # Phase 4b: response now carries the (auto-created) conversation id.
    assert body["conversation_id"]


@pytest.mark.asyncio
async def test_chat_requires_bearer_token(db_client: AsyncClient) -> None:
    r = await db_client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_chat_rejects_invalid_token(db_client: AsyncClient) -> None:
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_chat_empty_messages_returns_validation_envelope(
    db_client: AsyncClient,
) -> None:
    token = await _register_and_token(db_client)
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": []},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_chat_no_user_message_returns_422(db_client: AsyncClient) -> None:
    token = await _register_and_token(db_client)
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "system", "content": "you are helpful"}]},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert "user message" in body["error"]["message"].lower()


# --- persistence flow (phase 4b) --------------------------------------------


async def _fresh_token(db_client: AsyncClient, email: str) -> str:
    r = await db_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_chat_creates_and_returns_conversation_id_on_first_turn(
    db_client: AsyncClient,
) -> None:
    token = await _fresh_token(db_client, "flow-first@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "first hello"}]},
    )
    assert r.status_code == 200, r.text
    conv_id = r.json()["conversation_id"]
    assert conv_id

    # List: exactly one conversation, and it's this one.
    lst = await db_client.get("/api/v1/conversations", headers={"Authorization": f"Bearer {token}"})
    assert lst.status_code == 200
    assert [c["id"] for c in lst.json()] == [conv_id]

    # Detail: 2 messages in order.
    detail = await db_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["content"] == "first hello"
    assert body["messages"][1]["content"] == "(mock) first hello"
    assert body["messages"][1]["model"] == "mock-1"


@pytest.mark.asyncio
async def test_chat_appends_to_existing_conversation(db_client: AsyncClient) -> None:
    token = await _fresh_token(db_client, "flow-append@example.com")
    r1 = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "turn one"}]},
    )
    assert r1.status_code == 200
    conv_id = r1.json()["conversation_id"]

    r2 = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "conversation_id": conv_id,
            "messages": [
                {"role": "user", "content": "turn one"},
                {"role": "assistant", "content": "(mock) turn one"},
                {"role": "user", "content": "turn two"},
            ],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["conversation_id"] == conv_id

    detail = await db_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    msgs = detail.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in msgs] == [
        "turn one",
        "(mock) turn one",
        "turn two",
        "(mock) turn two",
    ]


@pytest.mark.asyncio
async def test_chat_with_unknown_conversation_id_returns_404(
    db_client: AsyncClient,
) -> None:
    from uuid import uuid4

    token = await _fresh_token(db_client, "flow-404@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "conversation_id": str(uuid4()),
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
