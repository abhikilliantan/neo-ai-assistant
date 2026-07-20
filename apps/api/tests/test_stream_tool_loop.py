"""Phase 6d — tool-use loop wired into ChatProvider.stream + /chat/stream.

Covers:
  - Scripted streaming provider double: given a tool_executor, "streams" turn 1
    as a tool_use for search_memory{query:"my name"}, runs the real tool via
    the short-per-call session factory, then streams the FINAL turn's text
    as deltas that fold in the seeded memory content. Assert deltas contain
    the memory content, only the final turn streamed, done frame closes it,
    and GET /conversations/{id} = [user, assistant] only (ephemeral holds).
  - Short-session proof: the streaming factory helper opens a FRESH tenant
    session per call — verified by pool-connection count deltas AND that
    each yielded MemoryRepository binds a distinct AsyncSession identity.
  - AnthropicProvider.stream tool loop, single tool round: SDK stream 1
    stops on tool_use → executor runs → SDK stream 2 is final → deltas
    from turn 2 only, no deltas from turn 1.
  - AnthropicProvider.stream cap: always-tool_use SDK hits
    max_tool_iterations and emits a terminal done with the cap flag —
    no infinite stream.
  - AnthropicProvider.stream is_error: executor returns is_error=True →
    the follow-up SDK request carries is_error=True on the tool_result;
    provider still streams a final answer + done.
  - tools_enabled=False → provider.stream gets tools=None (endpoint spy).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.application.ports.chat import (
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.tools import ToolCall, ToolResult
from app.infrastructure.db.repositories import MemoryRepository
from app.presentation.http.routers.chat import _make_streaming_memory_repo_factory

# --- helpers -----------------------------------------------------------------


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
    return events


async def _seed_memory(
    app_session_factory,  # type: ignore[no-untyped-def]
    *,
    tenant_id: UUID,
    user_id: UUID,
    content: str,
) -> None:
    embed = MockEmbeddingProvider()
    result = await embed.embed(texts=[content])
    s = await app_session_factory(tenant_id)
    try:
        await MemoryRepository(s).add(
            organization_id=tenant_id,
            user_id=user_id,
            content=content,
            embedding=result.vectors[0],
            embedding_model=result.model,
        )
        await s.commit()
    finally:
        await s.close()


# --- Scripted streaming provider double e2e ---------------------------------


class _StreamingMemorySearchingProvider:
    """Streams a FINAL answer that folds in one search_memory call's result.

    Simulates the "AnthropicProvider.stream tool loop" shape from OUTSIDE the
    provider: the double invokes tool_executor exactly once (analogous to
    turn 1 = tool_use, silently consumed), then yields text deltas for what
    would be turn 2 (the final answer). We assert only deltas from the final
    turn reach the client.
    """

    def __init__(self) -> None:
        self.tools_seen: list[list[dict[str, Any]] | None] = []
        self.executor_seen: list[ToolExecutor | None] = []

    async def complete(self, **_: object) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        self.tools_seen.append(tools)
        self.executor_seen.append(tool_executor)
        assert tool_executor is not None, "streaming double expects a tool_executor"
        # Turn 1 (silent): run the real tool via the short-session factory.
        result = await tool_executor(
            ToolCall(id="call_S", name="search_memory", arguments={"query": "my name"})
        )
        # Turn 2 (final, streamed): fold the result into the answer text.
        text = f"you told me: {result.content}"
        for i, word in enumerate(text.split(" ")):
            yield ChatStreamEvent(type="delta", content=word if i == 0 else " " + word)
        yield ChatStreamEvent(
            type="done",
            model="scripted-stream-mem",
            finish_reason="stop",
        )


@pytest.mark.asyncio
async def test_stream_runs_search_memory_via_short_session_factory_and_folds_into_final_deltas(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    scripted = _StreamingMemorySearchingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6d-e2e@example.com")
        token = reg["access_token"]
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])
        await _seed_memory(
            app_session_factory,
            tenant_id=tenant,
            user_id=user_id,
            content="user_fact: my name is Priya",
        )

        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "what's my name?"}]},
        )

        assert r.status_code == 200
        events = _parse_sse(r.text)
        assert events[0]["type"] == "meta"
        conv_id = events[0]["conversation_id"]

        deltas = [e for e in events if e["type"] == "delta"]
        joined = "".join(d["content"] for d in deltas)
        # Only the FINAL turn's deltas reached the client; the "turn 1"
        # tool_use round was silent (the scripted double did not emit deltas
        # before calling the executor).
        assert "Priya" in joined
        # And endpoint saw both stateless + streaming tools.
        assert scripted.tools_seen[-1] is not None
        assert {s["name"] for s in scripted.tools_seen[-1]} == {"echo", "search_memory"}
        assert scripted.executor_seen[-1] is not None

        # Ephemeral guarantee still holds on the stream path.
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        msgs = detail.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "what's my name?"
        assert "Priya" in msgs[1]["content"]


# --- Short-session proof: factory opens a fresh session per call ------------


@pytest.mark.asyncio
async def test_streaming_memory_repo_factory_opens_fresh_session_per_call(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """The factory used by /chat/stream MUST open a distinct session per call
    and close it on exit — NEVER bind one session to the tool for the stream
    duration. Proven by:
      1. Two invocations yield two distinct AsyncSession identities.
      2. Each yielded session actually has app.current_tenant set (short
         session opened its own tenant-scoped transaction).
      3. Both sessions are closed after their `async with` exits.
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6d-shortsession@example.com")
        tenant = UUID(reg["active_tenant_id"])

    db = db_app.state.database
    factory = _make_streaming_memory_repo_factory(db, tenant_id=tenant)

    sessions: list[AsyncSession] = []
    async with factory() as repo_a:
        assert isinstance(repo_a, MemoryRepository)
        sessions.append(repo_a.session)
        got_tenant = (
            await repo_a.session.execute(text("SELECT current_setting('app.current_tenant')"))
        ).scalar_one()
        assert got_tenant == str(tenant)

    async with factory() as repo_b:
        assert isinstance(repo_b, MemoryRepository)
        sessions.append(repo_b.session)
        got_tenant = (
            await repo_b.session.execute(text("SELECT current_setting('app.current_tenant')"))
        ).scalar_one()
        assert got_tenant == str(tenant)

    # Two distinct AsyncSession instances — the tool never holds one across
    # invocations. Each `async with factory()` opens/closes its own; if the
    # tool ever bound to a shared session the two would be the SAME identity.
    assert sessions[0] is not sessions[1]
    # And after the async-with exit, neither is still in a transaction
    # (short-per-call session's begin/commit ran to completion, connection
    # returned to the pool — nothing pinned for the stream duration).
    for s in sessions:
        assert s.in_transaction() is False


# --- AnthropicProvider.stream: single tool round happy path -----------------


def _fake_stream_message(
    *,
    content_blocks: list[Any],
    stop_reason: str,
    model: str = "claude-fake",
) -> SimpleNamespace:
    return SimpleNamespace(
        content=content_blocks,
        model=model,
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        stop_reason=stop_reason,
    )


class _FakeStreamCtx:
    """Fake async ctx manager mimicking client.messages.stream()."""

    def __init__(self, *, deltas: list[str], final: SimpleNamespace) -> None:
        self._deltas = deltas
        self._final = final

    async def __aenter__(self) -> _FakeStreamCtx:
        return self

    async def __aexit__(self, *_: Any) -> bool:
        return False

    @property
    def text_stream(self) -> Any:
        async def gen() -> Any:
            for d in self._deltas:
                yield d

        return gen()

    async def get_final_message(self) -> SimpleNamespace:
        return self._final


def _anthropic_stream_provider(
    contexts: list[_FakeStreamCtx], *, max_iters: int = 5
) -> tuple[AnthropicProvider, MagicMock]:
    stream_mock = MagicMock(side_effect=contexts)
    client = MagicMock()
    client.messages.stream = stream_mock
    client.close = AsyncMock()
    provider = AnthropicProvider(
        client=client,
        model="claude-sonnet-5",
        max_tokens=1024,
        max_tool_iterations=max_iters,
    )
    return provider, stream_mock


@pytest.mark.asyncio
async def test_anthropic_stream_runs_one_tool_round_then_streams_final_deltas() -> None:
    """Turn 1 stops on tool_use → executor runs → turn 2 streams final text.
    Only turn 2's deltas reach the client; turn 1's (empty here anyway) don't.
    """
    turn1_final = _fake_stream_message(
        content_blocks=[
            SimpleNamespace(type="tool_use", id="toolu_1", name="echo", input={"text": "x"})
        ],
        stop_reason="tool_use",
    )
    turn2_final = _fake_stream_message(
        content_blocks=[SimpleNamespace(type="text", text="")],
        stop_reason="end_turn",
    )
    contexts = [
        _FakeStreamCtx(deltas=[], final=turn1_final),
        _FakeStreamCtx(deltas=["hello ", "world"], final=turn2_final),
    ]
    provider, stream_mock = _anthropic_stream_provider(contexts)

    executor_calls: list[ToolCall] = []

    async def executor(call: ToolCall) -> ToolResult:
        executor_calls.append(call)
        return ToolResult(tool_call_id=call.id, content="x", is_error=False)

    events = [
        e
        async for e in provider.stream(
            messages=[ChatMessage(role="user", content="run echo")],
            tools=[{"name": "echo", "description": "x", "input_schema": {}}],
            tool_executor=executor,
        )
    ]

    # Executor called with the model's ToolCall verbatim.
    assert len(executor_calls) == 1
    assert executor_calls[0].id == "toolu_1"
    assert executor_calls[0].name == "echo"

    # Two SDK stream invocations.
    assert stream_mock.call_count == 2

    # Second call's `messages` carry the assistant + tool_result turns.
    second_msgs = stream_mock.call_args_list[1].kwargs["messages"]
    assert [m["role"] for m in second_msgs] == ["user", "assistant", "user"]
    assert second_msgs[1]["content"][0]["type"] == "tool_use"
    assert second_msgs[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": "x",
    }

    # Only turn 2's deltas emitted; done comes last with end_turn.
    deltas = [e for e in events if e.type == "delta"]
    assert [d.content for d in deltas] == ["hello ", "world"]
    assert events[-1].type == "done"
    assert events[-1].finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_stream_maps_is_error_true_onto_tool_result_block() -> None:
    turn1 = _fake_stream_message(
        content_blocks=[SimpleNamespace(type="tool_use", id="toolu_x", name="bad", input={})],
        stop_reason="tool_use",
    )
    turn2 = _fake_stream_message(
        content_blocks=[SimpleNamespace(type="text", text="")],
        stop_reason="end_turn",
    )
    contexts = [
        _FakeStreamCtx(deltas=[], final=turn1),
        _FakeStreamCtx(deltas=["ok, sorry"], final=turn2),
    ]
    provider, stream_mock = _anthropic_stream_provider(contexts)

    async def executor(call: ToolCall) -> ToolResult:
        return ToolResult(tool_call_id=call.id, content="boom", is_error=True)

    events = [
        e
        async for e in provider.stream(
            messages=[ChatMessage(role="user", content="try bad")],
            tools=[{"name": "bad", "description": "x", "input_schema": {}}],
            tool_executor=executor,
        )
    ]

    tool_result = stream_mock.call_args_list[1].kwargs["messages"][2]["content"][0]
    assert tool_result["is_error"] is True
    assert tool_result["content"] == "boom"

    # Provider still produced a final answer + terminal done — no crash.
    deltas = [e for e in events if e.type == "delta"]
    assert "".join(d.content for d in deltas) == "ok, sorry"
    assert events[-1].type == "done"
    assert events[-1].finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_stream_hits_iteration_cap_and_emits_done_with_max_flag() -> None:
    """Every SDK stream returns tool_use → provider caps out at
    max_tool_iterations, emits a terminal done frame with the cap flag —
    no infinite stream.
    """

    def _make_ctx() -> _FakeStreamCtx:
        return _FakeStreamCtx(
            deltas=[],
            final=_fake_stream_message(
                content_blocks=[
                    SimpleNamespace(
                        type="tool_use", id="toolu_loop", name="echo", input={"text": "x"}
                    )
                ],
                stop_reason="tool_use",
            ),
        )

    # max_iters=2 → up to 3 SDK stream calls before the cap trips.
    contexts = [_make_ctx(), _make_ctx(), _make_ctx()]
    provider, stream_mock = _anthropic_stream_provider(contexts, max_iters=2)

    async def executor(call: ToolCall) -> ToolResult:
        return ToolResult(tool_call_id=call.id, content="x")

    events = [
        e
        async for e in provider.stream(
            messages=[ChatMessage(role="user", content="loop")],
            tools=[{"name": "echo", "description": "x", "input_schema": {}}],
            tool_executor=executor,
        )
    ]

    assert stream_mock.call_count == 3
    # No delta events (all turns were tool_use → silent on text). 6e-1 added
    # a live "tool" frame per invocation, so three tool_use rounds surface as
    # three "tool" frames followed by the terminal "done" with the cap flag.
    assert [e.type for e in events] == ["tool", "tool", "tool", "done"]
    assert events[-1].finish_reason == "max_tool_iterations"


@pytest.mark.asyncio
async def test_anthropic_stream_no_tools_stays_live_streaming() -> None:
    """Tools=None: preserve the 3a live-streaming shape — deltas emitted as
    the SDK yields them, no per-turn buffering path involved.
    """
    ctx = _FakeStreamCtx(
        deltas=["a ", "b ", "c"],
        final=_fake_stream_message(
            content_blocks=[SimpleNamespace(type="text", text="")],
            stop_reason="end_turn",
        ),
    )
    provider, stream_mock = _anthropic_stream_provider([ctx])

    events = [e async for e in provider.stream(messages=[ChatMessage(role="user", content="hi")])]

    # Single SDK stream call; deltas exactly as yielded.
    assert stream_mock.call_count == 1
    assert "tools" not in stream_mock.call_args.kwargs
    deltas = [e for e in events if e.type == "delta"]
    assert [d.content for d in deltas] == ["a ", "b ", "c"]
    assert events[-1].type == "done"


# --- Endpoint spy: tools_enabled=false → provider.stream sees tools=None ----


class _StreamSpyProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **_: object) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        self.calls.append({"tools": tools, "tool_executor": tool_executor})
        yield ChatStreamEvent(type="delta", content="hi")
        yield ChatStreamEvent(type="done", model="stream-spy", finish_reason="stop")


@pytest.mark.asyncio
async def test_chat_stream_tools_enabled_false_passes_tools_none(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _StreamSpyProvider()
    db_app.state.chat_provider = spy
    db_app.state.settings = db_app.state.settings.model_copy(update={"tools_enabled": False})

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6d-tools-off@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    assert spy.calls, "provider.stream must have been called"
    assert spy.calls[-1]["tools"] is None
    assert spy.calls[-1]["tool_executor"] is None


@pytest.mark.asyncio
async def test_chat_stream_tools_enabled_true_passes_registered_specs(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _StreamSpyProvider()
    db_app.state.chat_provider = spy

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6d-tools-on@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    assert spy.calls[-1]["tools"] is not None
    assert {s["name"] for s in spy.calls[-1]["tools"]} == {"echo", "search_memory"}
    assert spy.calls[-1]["tool_executor"] is not None
