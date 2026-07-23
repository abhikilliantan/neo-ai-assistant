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
async def test_chat_default_agent_injects_grounding_persona(db_app) -> None:  # type: ignore[no-untyped-def]
    """/chat with the default assistant agent:
    - agent lookup uses DEFAULT_AGENT_NAME ("assistant"),
    - the provider receives the grounding persona as a leading system message
      (a fresh user has no memories, so the persona is the ONLY system message),
    - the user turn follows it,
    - the read-only tool set is present (nothing filtered for the default agent).
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

    # The grounding persona is prepended as a leading system message; the user
    # turn follows. No memory system message (fresh user, nothing retrieved).
    assert spy_provider.last_messages is not None
    msgs = spy_provider.last_messages
    assert msgs[0].role == "system"
    assert msgs[0].content.startswith("You are Neo, a helpful assistant.")
    assert "NO INVENTED METRICS" in msgs[0].content
    assert msgs[1:] == [ChatMessage(role="user", content="hello")]

    # Tools present — the full request-registry set (nothing filtered).
    assert spy_provider.last_tools is not None
    seen_names = {s["name"] for s in spy_provider.last_tools}
    # Baseline (6c) tools; assert membership rather than exact equality so
    # future tools don't churn this test.
    assert "echo" in seen_names
    assert "search_memory" in seen_names


@pytest.mark.asyncio
async def test_chat_stream_default_agent_injects_grounding_persona(db_app) -> None:  # type: ignore[no-untyped-def]
    """Same proof for /chat/stream: default agent lookup runs, the grounding
    persona leads the messages, tools are present.
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

    assert spy_provider.last_messages is not None
    msgs = spy_provider.last_messages
    assert msgs[0].role == "system"
    assert msgs[0].content.startswith("You are Neo, a helpful assistant.")
    assert msgs[1:] == [ChatMessage(role="user", content="hello")]
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
    # Registration order: assistant, recall, then operator (7d).
    assert [a["name"] for a in body] == ["assistant", "recall", "operator"]
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


# --- Phase 6i-1: server echoes the resolved agent back to the client -------


def _parse_sse(text: str) -> list[dict[str, Any]]:
    """Local copy of the SSE frame parser used across the streaming tests."""
    import json as _json

    events: list[dict[str, Any]] = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.split("\n"):
            if line.startswith("data:"):
                events.append(_json.loads(line[len("data:") :].strip()))
    return events


@pytest.mark.asyncio
async def test_chat_response_echoes_default_agent_when_no_agent_field(db_client) -> None:  # type: ignore[no-untyped-def]
    token = await _register_and_token(db_client, "echo-default@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["agent"] == DEFAULT_AGENT_NAME  # "assistant"


@pytest.mark.asyncio
async def test_chat_response_echoes_selected_recall_agent(db_client) -> None:  # type: ignore[no-untyped-def]
    token = await _register_and_token(db_client, "echo-recall@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent": "recall",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["agent"] == "recall"


@pytest.mark.asyncio
async def test_chat_stream_meta_carries_default_agent_when_no_agent_field(  # type: ignore[no-untyped-def]
    db_app,
) -> None:
    """Meta frame gains `agent`; delta / done stay clean (no agent field)."""
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "echo-stream-default@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200
    frames = _parse_sse(r.text)
    assert frames[0]["type"] == "meta"
    assert frames[0]["agent"] == DEFAULT_AGENT_NAME
    assert frames[0]["conversation_id"]
    # Delta + done frames must NOT carry an agent field — meta is the sole home.
    for f in frames[1:]:
        assert "agent" not in f


@pytest.mark.asyncio
async def test_chat_stream_meta_carries_selected_recall_agent(db_app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "echo-stream-recall@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "agent": "recall",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
    assert r.status_code == 200
    frames = _parse_sse(r.text)
    assert frames[0]["type"] == "meta"
    assert frames[0]["agent"] == "recall"


@pytest.mark.asyncio
async def test_agent_choice_persists_on_conversation_but_not_on_messages(  # type: ignore[no-untyped-def]
    db_client,
) -> None:
    """Narrowed from 6i-1 for 6j:
    - the CONVERSATION now carries the agent (persistence landed);
    - MESSAGES still carry no agent — the agent belongs to the thread,
      not to each turn (per-message agent would be a later slice if
      useful).
    """
    token = await _register_and_token(db_client, "echo-ephemeral@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "agent": "recall",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 200
    conv_id = r.json()["conversation_id"]

    detail = await db_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    body = detail.json()
    # 6j: conversation-level agent surfaces on reload.
    assert body["agent"] == "recall"
    # Messages remain agent-free.
    msgs = body["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    for m in msgs:
        assert "agent" not in m


# --- Phase 6j: per-conversation agent persistence --------------------------


@pytest.mark.asyncio
async def test_new_conversation_with_recall_persists_agent_name(db_client) -> None:  # type: ignore[no-untyped-def]
    token = await _register_and_token(db_client, "6j-new-recall@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"agent": "recall", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    conv_id = r.json()["conversation_id"]

    detail = await db_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["agent"] == "recall"


@pytest.mark.asyncio
async def test_new_conversation_no_agent_stores_null_reads_as_default(  # type: ignore[no-untyped-def]
    db_client,
    db_session,
) -> None:
    """No `agent` in body → row's agent_name is NULL (never explicitly set).
    Read-side resolves NULL → DEFAULT_AGENT_NAME, so the UI restores the
    picker to "assistant" without a None branch. Stored-as-NULL is what
    lets the default be renamed in the future without touching old rows.
    """
    from uuid import UUID

    from sqlalchemy import text as _text

    token = await _register_and_token(db_client, "6j-new-noagent@example.com")
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    conv_id = r.json()["conversation_id"]

    # Raw DB check via the privileged (RLS-bypass) session: agent_name IS NULL.
    row = (
        await db_session.execute(
            _text("SELECT agent_name FROM conversations WHERE id = :id").bindparams(
                id=UUID(conv_id)
            )
        )
    ).one()
    assert row.agent_name is None

    # HTTP read resolves NULL → default.
    detail = await db_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["agent"] == DEFAULT_AGENT_NAME


@pytest.mark.asyncio
async def test_continuing_existing_recall_with_no_agent_resolves_recall(  # type: ignore[no-untyped-def]
    db_app,
) -> None:
    """THE 6j point: continuing a thread with NO body.agent must resolve to
    the STORED value, not silently fall back to the default. Proven with a
    spy provider that receives the recall persona on turn 2 even though
    body.agent is absent.
    """
    spy_provider = _RecordingProvider()
    db_app.state.chat_provider = spy_provider

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "6j-continue-recall@example.com")
        # Turn 1: pick recall explicitly.
        r1 = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "agent": "recall",
                "messages": [{"role": "user", "content": "turn one"}],
            },
        )
        assert r1.status_code == 200
        conv_id = r1.json()["conversation_id"]

        # Turn 2: NO agent in body. Server should still resolve "recall".
        r2 = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "conversation_id": conv_id,
                "messages": [
                    {"role": "user", "content": "turn one"},
                    {"role": "assistant", "content": "ok"},
                    {"role": "user", "content": "turn two"},
                ],
            },
        )
    assert r2.status_code == 200
    assert r2.json()["agent"] == "recall"
    # Provider on turn 2 got the recall persona as leading system message.
    assert spy_provider.last_messages is not None
    assert spy_provider.last_messages[0] == ChatMessage(role="system", content=_RECALL_PERSONA)


@pytest.mark.asyncio
async def test_continuing_and_switching_to_assistant_updates_stored_agent(  # type: ignore[no-untyped-def]
    db_client,
) -> None:
    """Update-on-change semantic: the thread follows the user's latest
    explicit picker choice. Turn 1: recall. Turn 2: assistant. GET must
    return assistant — otherwise the picker (which now shows "assistant")
    would silently disagree with the stored value.
    """
    token = await _register_and_token(db_client, "6j-switch@example.com")
    r1 = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"agent": "recall", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r1.status_code == 200
    conv_id = r1.json()["conversation_id"]

    r2 = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "conversation_id": conv_id,
            "agent": "assistant",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "different"},
            ],
        },
    )
    assert r2.status_code == 200
    assert r2.json()["agent"] == "assistant"

    detail = await db_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["agent"] == "assistant"


@pytest.mark.asyncio
async def test_pre_existing_null_agent_row_reads_as_default_and_chat_works(  # type: ignore[no-untyped-def]
    db_client,
    app_session_factory,
) -> None:
    """Existing rows created before 6j have agent_name = NULL. GET must
    return the default, and continuing the chat must still work. This is
    the backward-compat guarantee for existing conversations.
    """
    from uuid import UUID

    from app.infrastructure.db.repositories import ConversationRepository as _CR

    reg = await db_client.post(
        "/api/v1/auth/register",
        json={"email": "6j-pre-null@example.com", "password": "password12345"},
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    tenant_id = UUID(reg.json()["active_tenant_id"])
    user_id = UUID(reg.json()["user_id"])

    # Insert a conversation row directly with NULL agent_name — models a
    # pre-6j row that survived the migration.
    session = await app_session_factory(tenant_id)
    try:
        conv = await _CR(session).create(
            organization_id=tenant_id,
            user_id=user_id,
            title="legacy",
            agent_name=None,
        )
        await session.commit()
        conv_id = str(conv.id)
    finally:
        await session.close()

    # Read: agent resolves to default.
    detail = await db_client.get(
        f"/api/v1/conversations/{conv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["agent"] == DEFAULT_AGENT_NAME

    # Continue: chat still works (no exceptions, resolves to default).
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "hi legacy"}],
        },
    )
    assert r.status_code == 200
    assert r.json()["agent"] == DEFAULT_AGENT_NAME


@pytest.mark.asyncio
async def test_chat_stream_unknown_agent_writes_no_conversation_row(  # type: ignore[no-untyped-def]
    db_app,
) -> None:
    """Beyond the 6h assertion (JSON 404, no SSE frames): also verify NO
    orphan user-message / conversation row was written. Fresh user, so any
    write would show as a non-empty /conversations list.
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = await _register_and_token(c, "6j-stream-orphan@example.com")
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "agent": "does-not-exist",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 404

        listing = await c.get(
            "/api/v1/conversations",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert listing.status_code == 200
    assert listing.json() == []


# --- Phase 6k-1: defensive-fallback warn log --------------------------------


@pytest.mark.asyncio
async def test_chat_defensive_fallback_warn_fires_and_serves_default(  # type: ignore[no-untyped-def]
    db_client,
    app_session_factory,
    monkeypatch,
) -> None:
    """A pre-existing row can hold an agent name that no longer exists in
    the registry (agent renamed or removed in a code deploy). The 6j
    defensive fallback swaps in the default so the user keeps working —
    but an operator needs to know the stored data references a ghost.

    Capture "chat.agent.fallback" warn calls by monkeypatching get_logger
    on the router module. Assert the turn still 200s on the default.
    """
    from uuid import UUID

    import app.presentation.http.routers.chat as chat_router
    from app.infrastructure.db.repositories import ConversationRepository as _CR

    reg = await db_client.post(
        "/api/v1/auth/register",
        json={"email": "6k-fallback@example.com", "password": "password12345"},
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    tenant_id = UUID(reg.json()["active_tenant_id"])
    user_id = UUID(reg.json()["user_id"])

    # Seed a conversation row that references a ghost agent (never
    # registered in build_agent_registry).
    session = await app_session_factory(tenant_id)
    try:
        conv = await _CR(session).create(
            organization_id=tenant_id,
            user_id=user_id,
            title="ghost",
            agent_name="ghost-agent",
        )
        await session.commit()
        conv_id = str(conv.id)
    finally:
        await session.close()

    # Intercept get_logger on the router module. The router calls
    # `get_logger("chat.agent.fallback").warning("chat.agent.fallback", ...)`;
    # we replace get_logger for that name only (leave others intact) and
    # record the warning kwargs.
    warnings: list[dict[str, object]] = []
    real_get_logger = chat_router.get_logger

    class _CapturingLog:
        def info(self, *_a: object, **_kw: object) -> None:
            pass

        def warning(self, event: str, **kwargs: object) -> None:
            if event == "chat.agent.fallback":
                warnings.append(kwargs)

    def _fake_get_logger(name: str) -> object:
        if name == "chat.agent.fallback":
            return _CapturingLog()
        return real_get_logger(name)

    monkeypatch.setattr(chat_router, "get_logger", _fake_get_logger)

    # POST with the ghost conversation and NO body.agent — resolver reaches
    # the stored "ghost-agent", registry.get returns None, warn fires,
    # fallback to default, turn succeeds.
    r = await db_client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "conversation_id": conv_id,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert r.status_code == 200
    assert r.json()["agent"] == DEFAULT_AGENT_NAME
    assert len(warnings) == 1
    assert warnings[0]["missing"] == "ghost-agent"
    assert warnings[0]["fallback"] == DEFAULT_AGENT_NAME
    assert warnings[0]["user_id"] == str(user_id)
