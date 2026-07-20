"""Phase 6g — AgentRunner unit tests + endpoint transparent-default spies.

Two shapes here:
  1. Pure `AgentRunner` unit tests (no HTTP, no DB): prepare_messages and
     filter_tools across the shapes locked in the spec — empty / non-empty
     persona, `tool_names is None` / `[]` / explicit subset, allowed-vs-not
     executor delegation.
  2. Endpoint spy tests that swap in a recording ChatProvider and assert
     both `/chat` and `/chat/stream` hand the provider EXACTLY the same
     messages + tools as the pre-6g wire-up would — the byte-compat proof
     for the default `assistant` agent.

The "endpoint uses the default agent" assertion is done via a spy registry
whose `.get()` records the lookup, so we can prove the DEFAULT_AGENT_NAME
constant is what the endpoint resolves.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.agents import DEFAULT_AGENT_NAME, AgentRegistry, AgentRunner
from app.application.ports.agents import AgentDefinition
from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.tools import ToolCall, ToolResult

# --- AgentRunner.prepare_messages ------------------------------------------


def test_prepare_messages_empty_persona_returns_input_unchanged() -> None:
    """Byte-compat precondition for /chat + /chat/stream default path: the
    default agent has system_prompt="", which must produce IDENTICAL messages
    (same list object, no allocation) so today's provider payload is preserved.
    """
    runner = AgentRunner(AgentDefinition(name="assistant", description="d"))
    messages = [
        ChatMessage(role="system", content="memory context"),
        ChatMessage(role="user", content="hi"),
    ]
    out = runner.prepare_messages(messages)
    # Identity — no new allocation for the default path.
    assert out is messages


def test_prepare_messages_non_empty_persona_prepends_single_system_message() -> None:
    """Non-empty persona prepends EXACTLY one system message, ahead of the
    5d memory system message the endpoint already prepended → wire order is
    [persona, memory, ...user/assistant].
    """
    runner = AgentRunner(AgentDefinition(name="p", description="d", system_prompt="you are grumpy"))
    messages = [
        ChatMessage(role="system", content="memory context"),
        ChatMessage(role="user", content="hi"),
    ]
    out = runner.prepare_messages(messages)
    assert len(out) == 3
    assert out[0] == ChatMessage(role="system", content="you are grumpy")
    assert out[1:] == messages
    # Original list untouched.
    assert len(messages) == 2


# --- AgentRunner.filter_tools ----------------------------------------------


async def _delegating_executor_recording() -> tuple[ToolExecutor, list[ToolCall]]:
    seen: list[ToolCall] = []

    async def _exec(call: ToolCall) -> ToolResult:
        seen.append(call)
        return ToolResult(tool_call_id=call.id, content=f"ran:{call.name}")

    return _exec, seen


@pytest.mark.asyncio
async def test_filter_tools_none_returns_specs_and_executor_unchanged() -> None:
    """Byte-compat precondition: `tool_names is None` → identity on both
    the specs list and the executor callable.
    """
    runner = AgentRunner(AgentDefinition(name="assistant", description="d"))
    exec_, _seen = await _delegating_executor_recording()
    specs = [
        {"name": "echo", "description": "x", "input_schema": {}},
        {"name": "search_memory", "description": "x", "input_schema": {}},
    ]
    out_specs, out_exec = runner.filter_tools(specs, exec_)
    assert out_specs is specs
    assert out_exec is exec_


@pytest.mark.asyncio
async def test_filter_tools_explicit_subset_filters_specs_to_just_that_name() -> None:
    runner = AgentRunner(AgentDefinition(name="r", description="d", tool_names=["search_memory"]))
    exec_, _seen = await _delegating_executor_recording()
    specs = [
        {"name": "echo", "description": "x", "input_schema": {}},
        {"name": "search_memory", "description": "x", "input_schema": {}},
    ]
    out_specs, _out_exec = runner.filter_tools(specs, exec_)
    assert [s["name"] for s in out_specs] == ["search_memory"]


@pytest.mark.asyncio
async def test_filter_tools_wrapped_executor_delegates_allowed_and_blocks_others() -> None:
    runner = AgentRunner(AgentDefinition(name="r", description="d", tool_names=["search_memory"]))
    exec_, seen = await _delegating_executor_recording()
    specs = [
        {"name": "echo", "description": "x", "input_schema": {}},
        {"name": "search_memory", "description": "x", "input_schema": {}},
    ]
    _out_specs, out_exec = runner.filter_tools(specs, exec_)

    # Allowed → delegates.
    allowed_result = await out_exec(ToolCall(id="c1", name="search_memory", arguments={"q": "x"}))
    assert allowed_result.is_error is False
    assert allowed_result.content == "ran:search_memory"
    assert [c.name for c in seen] == ["search_memory"]

    # Not allowed → is_error, does NOT reach the wrapped executor.
    blocked_result = await out_exec(ToolCall(id="c2", name="echo", arguments={}))
    assert blocked_result.is_error is True
    assert blocked_result.tool_call_id == "c2"
    assert "not permitted" in blocked_result.content
    # Wrapped executor was NOT called for the blocked call.
    assert [c.name for c in seen] == ["search_memory"]


@pytest.mark.asyncio
async def test_filter_tools_empty_subset_yields_empty_specs() -> None:
    """`tool_names=[]` → filtered=[]. The endpoint's `if specs:` gate then
    flips `tools=None` before the provider call — a conversational persona
    with no tools available. Any call attempted still returns is_error.
    """
    runner = AgentRunner(AgentDefinition(name="quiet", description="d", tool_names=[]))
    exec_, _seen = await _delegating_executor_recording()
    specs = [{"name": "echo", "description": "x", "input_schema": {}}]
    out_specs, out_exec = runner.filter_tools(specs, exec_)
    assert out_specs == []
    result = await out_exec(ToolCall(id="c3", name="echo", arguments={}))
    assert result.is_error is True


# --- Endpoint spy tests — transparent-default (the byte-compat proof) ------


class _RecordingProvider:
    """Records exactly what the endpoint hands the provider on both paths.

    Non-streaming: `complete` returns a canned answer.
    Streaming: `stream` emits one delta + one done (matches MockProvider's
    frame contract closely enough that persistence still succeeds).
    """

    def __init__(self) -> None:
        self.last_messages: list[ChatMessage] | None = None
        self.last_tools: list[dict[str, Any]] | None = None
        self.last_executor: ToolExecutor | None = None
        self.streamed = False

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        self.last_messages = list(messages)
        self.last_tools = tools
        self.last_executor = tool_executor
        return ChatCompletion(
            content="ok",
            model="spy-1",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        self.last_messages = list(messages)
        self.last_tools = tools
        self.last_executor = tool_executor
        self.streamed = True
        yield ChatStreamEvent(type="delta", content="ok")
        yield ChatStreamEvent(type="done", model="spy-1", usage=None, finish_reason="stop")


class _RecordingAgentRegistry:
    """Wraps a real AgentRegistry and records `.get()` lookups so we can
    prove the endpoint asked for DEFAULT_AGENT_NAME.
    """

    def __init__(self, inner: AgentRegistry) -> None:
        self._inner = inner
        self.get_calls: list[str] = []

    def get(self, name: str) -> AgentDefinition | None:
        self.get_calls.append(name)
        return self._inner.get(name)


async def _register_and_token(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_chat_default_agent_is_transparent(db_app) -> None:  # type: ignore[no-untyped-def]
    """/chat with the default assistant agent:
    - agent lookup uses DEFAULT_AGENT_NAME ("assistant"),
    - provider receives messages IDENTICAL to `augmented` (no extra
      persona system message — new user, so retrieval yields nothing and
      augmented == body.messages),
    - provider receives tools whose names match the full request-registry
      set (nothing filtered out).
    """
    spy_provider = _RecordingProvider()
    spy_registry = _RecordingAgentRegistry(db_app.state.agent_registry)
    db_app.state.chat_provider = spy_provider
    db_app.state.agent_registry = spy_registry

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "spy-chat@example.com")
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
    assert r.status_code == 200, r.text

    # Endpoint asked the registry for the default agent — and only that.
    assert spy_registry.get_calls == [DEFAULT_AGENT_NAME]

    # No persona system message injected — messages are exactly what
    # `augmented` would be (identical to body.messages for a fresh user
    # with no memories retrieved).
    assert spy_provider.last_messages == [ChatMessage(role="user", content="hello")]

    # Tools unfiltered — the full request-registry set is present.
    assert spy_provider.last_tools is not None
    seen_names = {s["name"] for s in spy_provider.last_tools}
    # Baseline (6c) tools; assert membership rather than exact equality so
    # future tools don't churn this test.
    assert "echo" in seen_names
    assert "search_memory" in seen_names


@pytest.mark.asyncio
async def test_chat_stream_default_agent_is_transparent(db_app) -> None:  # type: ignore[no-untyped-def]
    """Same byte-compat proof for /chat/stream: default agent lookup runs,
    messages pass through unchanged, tools are unfiltered.
    """
    spy_provider = _RecordingProvider()
    spy_registry = _RecordingAgentRegistry(db_app.state.agent_registry)
    db_app.state.chat_provider = spy_provider
    db_app.state.agent_registry = spy_registry

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "spy-stream@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
    assert r.status_code == 200, r.text
    assert spy_provider.streamed is True

    assert spy_registry.get_calls == [DEFAULT_AGENT_NAME]

    assert spy_provider.last_messages == [ChatMessage(role="user", content="hello")]
    assert spy_provider.last_tools is not None
    seen_names = {s["name"] for s in spy_provider.last_tools}
    assert "echo" in seen_names
    assert "search_memory" in seen_names


# --- Phase 6h: request-driven selection ("recall" persona + tool subset) ----

_RECALL_PERSONA = (
    "You are Neo's recall specialist. Before answering, search the user's "
    "saved memories and ground your answer in what you find. If nothing "
    "relevant is stored, say so plainly rather than guessing."
)


@pytest.mark.asyncio
async def test_chat_recall_agent_injects_persona_and_filters_tools(db_app) -> None:  # type: ignore[no-untyped-def]
    """/chat with agent="recall":
    - leading system message is EXACTLY the recall persona (ahead of any
      memory system message — memory is empty for a fresh user, but the
      persona is still the first message);
    - tool specs are filtered to ["search_memory"] only (echo absent).
    """
    spy_provider = _RecordingProvider()
    db_app.state.chat_provider = spy_provider

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "spy-recall-chat@example.com")
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "agent": "recall",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 200, r.text

    assert spy_provider.last_messages is not None
    assert spy_provider.last_messages[0] == ChatMessage(role="system", content=_RECALL_PERSONA)
    # No memories for the fresh user → only the persona + the user turn.
    assert spy_provider.last_messages[1:] == [ChatMessage(role="user", content="hi")]

    assert spy_provider.last_tools is not None
    assert [s["name"] for s in spy_provider.last_tools] == ["search_memory"]


@pytest.mark.asyncio
async def test_chat_stream_recall_agent_injects_persona_and_filters_tools(  # type: ignore[no-untyped-def]
    db_app,
) -> None:
    """Same recall-agent assertions on the streaming path."""
    spy_provider = _RecordingProvider()
    db_app.state.chat_provider = spy_provider

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "spy-recall-stream@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "agent": "recall",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 200, r.text
    assert spy_provider.streamed is True

    assert spy_provider.last_messages is not None
    assert spy_provider.last_messages[0] == ChatMessage(role="system", content=_RECALL_PERSONA)
    assert spy_provider.last_messages[1:] == [ChatMessage(role="user", content="hi")]

    assert spy_provider.last_tools is not None
    assert [s["name"] for s in spy_provider.last_tools] == ["search_memory"]


# --- Phase 6h: unknown agent → 404, never a stream frame -------------------


@pytest.mark.asyncio
async def test_chat_unknown_agent_returns_404_envelope(db_app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "unknown-agent-chat@example.com")
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "agent": "does-not-exist",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert "agent" in body["error"]["message"].lower()


@pytest.mark.asyncio
async def test_chat_stream_unknown_agent_returns_json_404_not_sse_frame(  # type: ignore[no-untyped-def]
    db_app,
) -> None:
    """CRITICAL: the stream must reject the unknown agent BEFORE it opens the
    SSE response — the client gets a plain JSON 404, NOT a `data:` error frame.
    Same discipline as the 4b conversation-not-found 404.
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "unknown-agent-stream@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "agent": "does-not-exist",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 404
    # Plain JSON envelope, NOT text/event-stream — proves we short-circuited
    # before StreamingResponse was returned.
    assert r.headers["content-type"].startswith("application/json")
    assert "data:" not in r.text
    body = r.json()
    assert body["error"]["code"] == "not_found"


# --- Phase 6h: GET /api/v1/agents whitelist -------------------------------


@pytest.mark.asyncio
async def test_list_agents_returns_only_name_and_description(db_client) -> None:  # type: ignore[no-untyped-def]
    """The listing must NOT leak system_prompt (prompt-engineering IP +
    jailbreak surface) or tool_names (internal policy). Whitelist is
    enforced structurally by AgentOut — this test guards the contract.
    """
    token = await _register_and_token(db_client, "agents-list@example.com")
    r = await db_client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    # Registration order: assistant then recall.
    assert [a["name"] for a in body] == ["assistant", "recall"]
    for item in body:
        assert set(item.keys()) == {"name", "description"}
        # Belt-and-braces: even if keys() ever grew, these two must never appear.
        assert "system_prompt" not in item
        assert "tool_names" not in item
    recall = next(a for a in body if a["name"] == "recall")
    assert recall["description"] == "Answers from what you've told Neo before."


@pytest.mark.asyncio
async def test_list_agents_requires_bearer_token(db_client) -> None:  # type: ignore[no-untyped-def]
    r = await db_client.get("/api/v1/agents")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"
