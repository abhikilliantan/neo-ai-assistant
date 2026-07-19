"""Streaming chat: MockProvider.stream() + /api/v1/chat/stream endpoint."""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.mock import MockProvider
from app.application.ports.chat import ChatMessage

# --- MockProvider.stream() unit tests ---------------------------------------


@pytest.mark.asyncio
async def test_mock_stream_deltas_concatenate_and_end_with_done() -> None:
    provider = MockProvider()
    events = [
        e async for e in provider.stream(messages=[ChatMessage(role="user", content="hello world")])
    ]

    assert events[-1].type == "done"
    assert events[-1].model == "mock-1"
    assert events[-1].usage is None
    assert events[-1].finish_reason == "stop"

    deltas = [e for e in events if e.type == "delta"]
    assert "".join(d.content for d in deltas) == "(mock) hello world"


# --- endpoint SSE tests -----------------------------------------------------


async def _register_and_token(client: AsyncClient) -> str:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "streamer@example.com", "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _parse_sse(text: str) -> list[dict]:
    """Parse `data: {...}\\n\\n` frames into a list of dicts."""
    events: list[dict] = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
    return events


@pytest.mark.asyncio
async def test_chat_stream_happy_path(db_app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c)
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hello world"}]},
        )

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.text)
    # First frame is the endpoint meta frame carrying conversation_id.
    assert events[0]["type"] == "meta"
    assert events[0]["conversation_id"]
    deltas = [e for e in events if e["type"] == "delta"]
    dones = [e for e in events if e["type"] == "done"]
    assert "".join(d["content"] for d in deltas) == "(mock) hello world"
    assert len(dones) == 1
    assert dones[0]["model"] == "mock-1"
    assert dones[0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_chat_stream_requires_bearer_token(db_client: AsyncClient) -> None:
    r = await db_client.post(
        "/api/v1/chat/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_chat_stream_rejects_invalid_token(db_client: AsyncClient) -> None:
    r = await db_client.post(
        "/api/v1/chat/stream",
        headers={"Authorization": "Bearer bogus"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_chat_stream_empty_messages_returns_422(db_client: AsyncClient) -> None:
    # Register + token; then submit empty messages.
    reg = await db_client.post(
        "/api/v1/auth/register",
        json={"email": "sv@example.com", "password": "password12345"},
    )
    token = reg.json()["access_token"]
    r = await db_client.post(
        "/api/v1/chat/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": []},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_chat_stream_mid_stream_provider_error_emits_error_frame(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """Force the provider to raise mid-stream → terminal error frame + 200 body."""
    from collections.abc import AsyncIterator

    from app.application.ports.chat import ChatStreamEvent
    from app.shared.exceptions.ai import ProviderRateLimitError

    class _FailingProvider:
        async def complete(self, **_: object) -> object:  # pragma: no cover
            raise NotImplementedError

        async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:
            yield ChatStreamEvent(type="delta", content="partial")
            raise ProviderRateLimitError("slow down")

    # Swap the pinned mock for the failing provider on this test's app.
    db_app.state.chat_provider = _FailingProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c)
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert r.status_code == 200  # headers already sent when error hits
    events = _parse_sse(r.text)
    assert events[0]["type"] == "meta"
    assert events[1]["type"] == "delta"
    assert events[1]["content"] == "partial"
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "provider_rate_limited"
