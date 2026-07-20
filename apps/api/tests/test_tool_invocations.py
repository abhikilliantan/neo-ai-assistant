"""Phase 6e-1 — surface tool invocations from the backend.

Covers:
  - Non-streaming: AnthropicProvider.complete accumulates one ToolInvocation
    per tool_use it runs (name = call.name, ok = not result.is_error).
    /chat response body carries tool_invocations; msg_repo stays
    [user, assistant] (GET /conversations/{id} unchanged — ephemeral holds).
  - Non-streaming is_error: executor returns is_error=True → invocation
    ok=false surfaced; chat still 200.
  - Streaming: scripted streaming provider that runs search_memory mid-turn
    emits a data: frame with type:"tool", tool_name:"search_memory",
    tool_ok:true BEFORE the final delta frames; the endpoint's accumulator
    (delta-only) doesn't fold it into the persisted assistant content —
    GET /conversations/{id} = [user, assistant] only.
  - AnthropicProvider.stream directly: a real tool_use round yields a
    ChatStreamEvent(type="tool", tool_name=..., tool_ok=...) BEFORE the
    final-turn delta events.
  - Mock unchanged: /chat body carries tool_invocations=[]; /chat/stream
    emits no "tool" frames.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.anthropic import AnthropicProvider
from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.tools import ToolCall, ToolResult

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


# --- Non-streaming: scripted double surfaces invocations --------------------


class _EchoUsingProvider:
    """Scripted provider that runs the echo tool once and returns a final
    ChatCompletion carrying one ToolInvocation for it. Simulates what
    AnthropicProvider.complete does on a single tool round — same pattern
    as 6b/6c's e2e doubles.
    """

    def __init__(self, *, executor_error: bool = False) -> None:
        self._executor_error = executor_error

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
        # Force is_error branch via an unknown tool when the test wants it;
        # otherwise use a real registered tool ("echo") for the success path.
        tool_name = "totally_not_a_tool" if self._executor_error else "echo"
        call = ToolCall(id="call_A", name=tool_name, arguments={"text": "ping"})
        result = await tool_executor(call)
        # Mirror AnthropicProvider.complete's ToolInvocation accumulation.
        from app.application.ports.tools import ToolInvocation

        return ChatCompletion(
            content=f"final: {result.content}",
            model="scripted-6e1",
            usage=None,
            finish_reason="stop",
            tool_invocations=[ToolInvocation(name=call.name, ok=not result.is_error)],
        )

    async def stream(  # pragma: no cover — not used in these tests
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="scripted-6e1", finish_reason="stop")


@pytest.mark.asyncio
async def test_chat_surfaces_tool_invocations_and_stays_ephemeral(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    db_app.state.chat_provider = _EchoUsingProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6e1-happy@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200, r.text
        body = r.json()

        # Invocation surfaced live for THIS turn (name + ok).
        assert body["tool_invocations"] == [{"name": "echo", "ok": True}]
        conv_id = body["conversation_id"]

        # Ephemeral guarantee: GET /conversations/{id} still shows exactly
        # [user, assistant] — invocations are NOT persisted onto rows.
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        msgs = detail.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        # And the persisted rows carry NO tool_invocations field (the
        # conversation detail schema doesn't include it).
        assert "tool_invocations" not in msgs[0]
        assert "tool_invocations" not in msgs[1]


@pytest.mark.asyncio
async def test_chat_surfaces_is_error_invocation_with_ok_false(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """Executor surfaces is_error=True (unknown tool) → invocation ok=false;
    /chat still 200. Mirrors 6b's is_error recovery shape.
    """
    db_app.state.chat_provider = _EchoUsingProvider(executor_error=True)

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6e1-err@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["tool_invocations"] == [{"name": "totally_not_a_tool", "ok": False}]


# --- Non-streaming: MockProvider byte-for-byte identical --------------------


@pytest.mark.asyncio
async def test_chat_mock_returns_empty_tool_invocations(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """MockProvider ignores tools → tool_invocations is the additive default
    (empty list). Keeps the no-tools response byte-for-byte identical modulo
    this additive default field.
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6e1-mock@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        assert r.json()["tool_invocations"] == []


# --- Streaming: scripted provider emits a "tool" frame ---------------------


class _StreamingToolFrameProvider:
    """Streams: turn 1 runs search_memory AND emits its "tool" frame before
    running the executor's follow-up; turn 2 is the final answer's deltas.
    Assert the "tool" frame appears BEFORE the deltas and does NOT enter the
    persisted assistant content (endpoint's accumulator gates on delta-only).
    """

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
        assert tool_executor is not None
        call = ToolCall(id="call_S", name="search_memory", arguments={"query": "q"})
        result = await tool_executor(call)
        # Live "tool" frame — the 6e-1 signal the UI renders as a chip.
        yield ChatStreamEvent(type="tool", tool_name=call.name, tool_ok=not result.is_error)
        # Final-turn deltas — these ARE what the accumulator persists.
        for chunk in ["finished ", "the search"]:
            yield ChatStreamEvent(type="delta", content=chunk)
        yield ChatStreamEvent(type="done", model="scripted-stream-6e1", finish_reason="stop")


@pytest.mark.asyncio
async def test_chat_stream_emits_tool_frame_and_does_not_persist_it(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    db_app.state.chat_provider = _StreamingToolFrameProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6e1-stream@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        frames = _parse_sse(r.text)

        # Frame ordering: meta → tool → delta(s) → done. The "tool" frame
        # arrives BEFORE any deltas — the live signal fires the moment the
        # provider runs the tool.
        types = [f["type"] for f in frames]
        assert types[0] == "meta"
        assert types.count("tool") == 1
        tool_ix = types.index("tool")
        first_delta_ix = types.index("delta")
        assert tool_ix < first_delta_ix
        assert types[-1] == "done"

        tool_frame = frames[tool_ix]
        assert tool_frame["tool_name"] == "search_memory"
        assert tool_frame["tool_ok"] is True

        # Persisted content is only the deltas — the "tool" frame did NOT
        # enter the assistant row. GET /conversations/{id} = [user, assistant]
        # and assistant content is the joined deltas ONLY.
        conv_id = frames[0]["conversation_id"]
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        msgs = detail.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[1]["content"] == "finished the search"


@pytest.mark.asyncio
async def test_chat_stream_mock_emits_no_tool_frames(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """MockProvider.stream is a no-op w.r.t. tools — no "tool" frames on
    the wire. Keeps every existing stream test byte-for-byte identical.
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6e1-stream-mock@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        types = [f["type"] for f in _parse_sse(r.text)]
        assert "tool" not in types
        assert types[0] == "meta"
        assert types[-1] == "done"


# --- AnthropicProvider.stream directly: tool frame precedes final deltas ---


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


@pytest.mark.asyncio
async def test_anthropic_stream_yields_tool_frame_per_tool_use_before_final_deltas() -> None:
    turn1 = _fake_stream_message(
        content_blocks=[
            SimpleNamespace(type="tool_use", id="toolu_1", name="echo", input={"text": "x"})
        ],
        stop_reason="tool_use",
    )
    turn2 = _fake_stream_message(
        content_blocks=[SimpleNamespace(type="text", text="")],
        stop_reason="end_turn",
    )
    stream_mock = MagicMock(
        side_effect=[
            _FakeStreamCtx(deltas=[], final=turn1),
            _FakeStreamCtx(deltas=["ok"], final=turn2),
        ]
    )
    client = MagicMock()
    client.messages.stream = stream_mock
    client.close = AsyncMock()
    provider = AnthropicProvider(client=client, model="claude-sonnet-5", max_tokens=1024)

    async def executor(call: ToolCall) -> ToolResult:
        return ToolResult(tool_call_id=call.id, content="pong", is_error=False)

    events = [
        e
        async for e in provider.stream(
            messages=[ChatMessage(role="user", content="run echo")],
            tools=[{"name": "echo", "description": "x", "input_schema": {}}],
            tool_executor=executor,
        )
    ]

    types = [e.type for e in events]
    # tool frame first (from turn 1's executor run), then delta(s) from turn
    # 2, then done. The "tool" frame arrives BEFORE any delta.
    assert types[0] == "tool"
    assert events[0].tool_name == "echo"
    assert events[0].tool_ok is True
    first_delta_ix = types.index("delta")
    assert types.index("tool") < first_delta_ix
    assert types[-1] == "done"


@pytest.mark.asyncio
async def test_anthropic_stream_tool_frame_carries_ok_false_on_is_error() -> None:
    turn1 = _fake_stream_message(
        content_blocks=[SimpleNamespace(type="tool_use", id="toolu_x", name="bad", input={})],
        stop_reason="tool_use",
    )
    turn2 = _fake_stream_message(
        content_blocks=[SimpleNamespace(type="text", text="")],
        stop_reason="end_turn",
    )
    stream_mock = MagicMock(
        side_effect=[
            _FakeStreamCtx(deltas=[], final=turn1),
            _FakeStreamCtx(deltas=["sorry"], final=turn2),
        ]
    )
    client = MagicMock()
    client.messages.stream = stream_mock
    client.close = AsyncMock()
    provider = AnthropicProvider(client=client, model="claude-sonnet-5", max_tokens=1024)

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

    tool_events = [e for e in events if e.type == "tool"]
    assert len(tool_events) == 1
    assert tool_events[0].tool_name == "bad"
    assert tool_events[0].tool_ok is False


# --- AnthropicProvider.complete: tool_invocations accumulated --------------


def _fake_text_response(
    *, text: str, model: str = "claude-fake", stop_reason: str = "end_turn"
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        model=model,
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        stop_reason=stop_reason,
    )


def _fake_tool_use_response(
    *, call_id: str, tool_name: str, arguments: dict[str, Any]
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", id=call_id, name=tool_name, input=arguments),
        ],
        model="claude-fake",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        stop_reason="tool_use",
    )


@pytest.mark.asyncio
async def test_anthropic_complete_accumulates_tool_invocations() -> None:
    responses = [
        _fake_tool_use_response(call_id="toolu_1", tool_name="echo", arguments={"text": "x"}),
        _fake_text_response(text="done"),
    ]
    create = AsyncMock(side_effect=responses)
    client = MagicMock()
    client.messages.create = create
    client.close = AsyncMock()
    provider = AnthropicProvider(client=client, model="claude-sonnet-5", max_tokens=1024)

    async def executor(call: ToolCall) -> ToolResult:
        return ToolResult(tool_call_id=call.id, content="x", is_error=False)

    completion = await provider.complete(
        messages=[ChatMessage(role="user", content="run echo")],
        tools=[{"name": "echo", "description": "x", "input_schema": {}}],
        tool_executor=executor,
    )

    assert len(completion.tool_invocations) == 1
    assert completion.tool_invocations[0].name == "echo"
    assert completion.tool_invocations[0].ok is True


@pytest.mark.asyncio
async def test_anthropic_complete_no_tools_returns_empty_invocations() -> None:
    """No tools → completion.tool_invocations is the additive default (empty
    list). Backward-compat contract preserved.
    """
    create = AsyncMock(return_value=_fake_text_response(text="hi"))
    client = MagicMock()
    client.messages.create = create
    client.close = AsyncMock()
    provider = AnthropicProvider(client=client, model="claude-sonnet-5", max_tokens=1024)
    completion = await provider.complete(messages=[ChatMessage(role="user", content="hi")])
    assert completion.tool_invocations == []
