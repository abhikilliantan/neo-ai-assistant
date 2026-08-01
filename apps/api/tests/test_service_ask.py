"""Slice 2A — POST /api/v1/service/ask.

Service-key-authed one-shot Q&A that runs the project_analyst agent for the
key's org. DB-backed (real Alembic + RLS). The LLM is mocked so tests never
spend: the default MockProvider (pinned by db_app) ignores tools and echoes the
question; the isolation test swaps in a stub that drives the REAL tool_executor
so we observe exactly what datasets a key's org can see.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.tools import ToolCall


def _csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


_TRACKER = [
    ["Action", "Status", "Owner"],
    ["Fix login", "Open", "Ada"],
    ["Ship docs", "Done", "Bob"],
]


class _ListOnlyProvider:
    """Runs only list_datasets via the real executor and echoes the raw result —
    lets a test observe exactly what datasets a key's org can see."""

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        assert tool_executor is not None
        res = await tool_executor(ToolCall(id="c1", name="list_datasets", arguments={}))
        return ChatCompletion(
            content=res.content, model=model or "scripted", usage=None, finish_reason="stop"
        )

    async def stream(  # pragma: no cover — /ask never streams
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="scripted", finish_reason="stop")


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password12345"}
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _create_key(client: AsyncClient, jwt: str, name: str = "n8n") -> str:
    r = await client.post(
        "/api/v1/api-keys", json={"name": name}, headers={"Authorization": f"Bearer {jwt}"}
    )
    assert r.status_code == 201, r.text
    return r.json()["api_key"]  # type: ignore[no-any-return]


async def _ingest(client: AsyncClient, jwt: str, name: str) -> None:
    r = await client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("tracker.csv", _csv(_TRACKER), "text/csv")},
        data={"name": name},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_ask_with_valid_key_returns_answer(db_client: AsyncClient) -> None:
    """Valid key → 200 with an answer. Default MockProvider (no real spend)
    ignores tools and echoes the question; the economy model override surfaces
    on `model`."""
    reg = await _register(db_client, "owner@ask.example")
    key = await _create_key(db_client, reg["access_token"])

    r = await db_client.post(
        "/api/v1/service/ask",
        json={"question": "What is the status of the project?"},
        headers={"X-API-Key": key},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "What is the status of the project?" in body["answer"]
    assert body["sources"] == []  # mock ran no tools


@pytest.mark.asyncio
async def test_ask_missing_key_401(db_client: AsyncClient) -> None:
    r = await db_client.post("/api/v1/service/ask", json={"question": "hi"})
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_ask_garbage_key_401(db_client: AsyncClient) -> None:
    r = await db_client.post(
        "/api/v1/service/ask",
        json={"question": "hi"},
        headers={"Authorization": "Bearer neo_sk_not-a-real-key"},
    )
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_ask_empty_question_400(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "owner@empty.example")
    key = await _create_key(db_client, reg["access_token"])

    r = await db_client.post(
        "/api/v1/service/ask", json={"question": "   "}, headers={"X-API-Key": key}
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_ask_is_tenant_scoped_to_key_org(db_app) -> None:  # type: ignore[no-untyped-def]
    """The agent sees ONLY the key-org's datasets. Org A and B each ingest a
    distinctly-named tracker; A's key must surface A's dataset and never B's."""
    db_app.state.chat_provider = _ListOnlyProvider()
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg_a = await _register(c, "a@askiso.example")
        reg_b = await _register(c, "b@askiso.example")
        await _ingest(c, reg_a["access_token"], "Alpha Tracker")
        await _ingest(c, reg_b["access_token"], "Beta Tracker")
        key_a = await _create_key(c, reg_a["access_token"], name="A-key")

        r = await c.post(
            "/api/v1/service/ask",
            json={"question": "list my datasets"},
            headers={"X-API-Key": key_a},
        )
        assert r.status_code == 200, r.text
        answer = r.json()["answer"]
        assert "Alpha Tracker" in answer
        assert "Beta Tracker" not in answer
