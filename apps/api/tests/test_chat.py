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
