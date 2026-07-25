"""Capability 1, Slice 1d — dataset tools wired into a non-streaming /chat turn.

Uses the 6b/6e scripted-provider technique: a provider double receives the REAL
tool_executor from /chat and drives the actual tools against the DB —
list_datasets to discover the dataset, then query_dataset with a status filter —
and returns a final answer carrying the count. We assert the tools ran, the
number is right, tenant isolation holds, and the tool turns stay ephemeral
(GET /conversations/{id} = [user, assistant] only).

MockProvider remains the CI default (db_app pins it); we swap ONLY chat_provider.
"""

from __future__ import annotations

import csv
import io
import json
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
from app.application.ports.tools import ToolCall, ToolInvocation


def _csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


_TRACKER = [
    ["Action", "Status", "Owner"],
    ["Fix login", "Open", "Ada"],
    ["Ship docs", "Done", "Bob"],
    ["Patch RLS", "Open", "Cy"],
    ["Review PR", "Closed", "Ada"],
]  # 2 rows with Status == "Open"


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password12345"}
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


class _TrackerQueryingProvider:
    """Drives list_datasets → query_dataset against the real executor, exactly as
    the grounding prompt instructs the model to. Records the tool specs it was
    handed so the test can assert both dataset tools reached the provider.
    """

    def __init__(self) -> None:
        self.seen_tools: list[str] = []

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
        self.seen_tools = [t["name"] for t in (tools or [])]

        # 1) discover the dataset + its columns
        list_res = await tool_executor(ToolCall(id="c1", name="list_datasets", arguments={}))
        datasets = json.loads(list_res.content)["datasets"]
        ds = datasets[0]

        # 2) count rows where Status == "Open"
        q_res = await tool_executor(
            ToolCall(
                id="c2",
                name="query_dataset",
                arguments={
                    "dataset_id": ds["dataset_id"],
                    "filters": [{"column_key": "status", "op": "eq", "value": "Open"}],
                    "aggregate": {"func": "count"},
                },
            )
        )
        data = json.loads(q_res.content)
        return ChatCompletion(
            content=f"There are {data['value']} open actions in {data['dataset_name']}.",
            model="scripted-1d",
            usage=None,
            finish_reason="stop",
            tool_invocations=[
                ToolInvocation(name="list_datasets", ok=not list_res.is_error),
                ToolInvocation(name="query_dataset", ok=not q_res.is_error),
            ],
        )

    async def stream(  # pragma: no cover — not used
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="scripted-1d", finish_reason="stop")


class _ListOnlyProvider:
    """Runs only list_datasets and echoes the raw result — lets a test observe
    what a tenant's chat turn can see (for the isolation check)."""

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
            content=res.content, model="scripted-1d", usage=None, finish_reason="stop"
        )

    async def stream(  # pragma: no cover — not used
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="scripted-1d", finish_reason="stop")


async def _ingest(client: AsyncClient, token: str, name: str) -> str:
    r = await client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("tracker.csv", _csv(_TRACKER), "text/csv")},
        data={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()["dataset_id"]  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_chat_runs_dataset_tools_and_answers_with_count(db_app) -> None:  # type: ignore[no-untyped-def]
    provider = _TrackerQueryingProvider()
    db_app.state.chat_provider = provider
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "1d-happy@example.com")
        token = reg["access_token"]
        await _ingest(c, token, "Q3 Tracker")

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "How many actions are still open?"}]},
        )
        assert r.status_code == 200, r.text
        body = r.json()

        # The two dataset tools reached the provider as specs.
        assert {"list_datasets", "query_dataset"} <= set(provider.seen_tools)
        # Both tools ran, ok, surfaced live for this turn.
        assert body["tool_invocations"] == [
            {"name": "list_datasets", "ok": True},
            {"name": "query_dataset", "ok": True},
        ]
        # The grounded answer carries the CORRECT count from the real query.
        assert body["message"]["content"] == "There are 2 open actions in Q3 Tracker."

        # Ephemeral: tool turns are not persisted — history is [user, assistant].
        conv_id = body["conversation_id"]
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert [m["role"] for m in detail.json()["messages"]] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_project_analyst_answers_status_via_query_dataset(db_app) -> None:  # type: ignore[no-untyped-def]
    """The Project Analyst agent answers a status question by querying a tracker:
    its filtered tool subset (dataset tools + read-only lookups, NOT echo) reaches
    the provider, and the grounded count comes back."""
    provider = _TrackerQueryingProvider()
    db_app.state.chat_provider = provider
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "pa-status@example.com")
        token = reg["access_token"]
        await _ingest(c, token, "Q3 Tracker")

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "messages": [{"role": "user", "content": "How many actions are still open?"}],
                "agent": "project_analyst",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["agent"] == "project_analyst"
        # The agent's tool subset was enforced — dataset tools + read-only lookups
        # reached the provider; echo (not in the analyst subset) was filtered out.
        assert set(provider.seen_tools) == {
            "list_datasets",
            "query_dataset",
            "search_documents",
            "search_memory",
        }
        # Grounded: both tools ran and the count is the real query result.
        assert body["tool_invocations"] == [
            {"name": "list_datasets", "ok": True},
            {"name": "query_dataset", "ok": True},
        ]
        assert body["message"]["content"] == "There are 2 open actions in Q3 Tracker."


@pytest.mark.asyncio
async def test_chat_dataset_tools_are_tenant_isolated(db_app) -> None:  # type: ignore[no-untyped-def]
    db_app.state.chat_provider = _ListOnlyProvider()
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        owner = await _register(c, "1d-owner@example.com")
        other = await _register(c, "1d-other@example.com")  # separate org
        await _ingest(c, owner["access_token"], "Owner Tracker")

        # Owner's chat sees the dataset...
        r_owner = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {owner['access_token']}"},
            json={"messages": [{"role": "user", "content": "list"}]},
        )
        assert "Owner Tracker" in r_owner.json()["message"]["content"]

        # ...the other org's chat does NOT (list_datasets is tenant-scoped).
        r_other = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {other['access_token']}"},
            json={"messages": [{"role": "user", "content": "list"}]},
        )
        content = r_other.json()["message"]["content"]
        assert "Owner Tracker" not in content
        assert content == "No datasets have been uploaded yet."
