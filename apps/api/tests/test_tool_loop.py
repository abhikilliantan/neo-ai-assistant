"""Phase 6b — tool-use loop wired into ChatProvider.complete + /chat.

Covers:
  - MockProvider ignores the new params (Protocol conformance, byte-identical
    behavior); pinned by conftest so all existing /chat tests remain green.
  - End-to-end tool loop via a scripted per-test provider double (same
    technique as 5d's recording provider): the double invokes the passed-in
    tool_executor and returns a final ChatCompletion that folds in the
    ToolResult.content. Assert the registry's echo ran, /chat returned 200
    with the folded content, and ONLY [user, assistant] were persisted.
  - Loop cap on AnthropicProvider: a mocked SDK that always returns
    stop_reason="tool_use" hits max_tool_iterations, returns with the cap
    flag, and never infinite-loops.
  - Tool error path: executor returns is_error=True (unknown tool); the
    provider still produces a final answer; endpoint still 200.
  - tools_enabled=False → /chat passes tools=None (spy provider).
  - AnthropicProvider tool loop: single-tool-round happy path with a mocked
    SDK, asserting the executor received the ToolCall, the follow-up SDK
    call carried the assistant + tool_result turns, and the returned
    ChatCompletion is the second call's text.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.mock import MockProvider
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


# --- MockProvider no-op ------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_provider_ignores_tools_and_executor() -> None:
    """MockProvider must accept the new params for Protocol conformance and
    ignore them — CI/test determinism depends on this no-op.
    """
    provider = MockProvider()
    executor_calls: list[ToolCall] = []

    async def executor(call: ToolCall) -> ToolResult:
        executor_calls.append(call)
        return ToolResult(tool_call_id=call.id, content="unused")

    completion = await provider.complete(
        messages=[ChatMessage(role="user", content="hello world")],
        tools=[{"name": "echo", "description": "x", "input_schema": {}}],
        tool_executor=executor,
    )
    assert completion.content == "(mock) hello world"
    assert completion.finish_reason == "stop"
    assert executor_calls == []


# --- end-to-end via a scripted provider double ------------------------------


class _EchoToolUsingProvider:
    """Scripted provider that ALWAYS invokes tool_executor once (echo tool)
    then returns a final answer. Not a subclass of MockProvider — we want the
    provider's contract with tools laid bare.
    """

    def __init__(self) -> None:
        self.tools_seen: list[list[dict[str, Any]] | None] = []

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        self.tools_seen.append(tools)
        assert tool_executor is not None, "test expects the endpoint to pass an executor"
        call = ToolCall(id="call_A", name="echo", arguments={"text": "ping"})
        result = await tool_executor(call)
        return ChatCompletion(
            content=f"final: {result.content}",
            model="scripted-1",
            usage=None,
            finish_reason="stop",
        )

    async def stream(  # never used in these tests but keeps the Protocol whole
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="scripted-1", finish_reason="stop")


@pytest.mark.asyncio
async def test_chat_runs_tool_via_registry_and_folds_result_into_final_text(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    scripted = _EchoToolUsingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "tool-e2e@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "tool please"}]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Echo actually ran — its result surfaced via the executor.
        assert body["message"]["content"] == "final: ping"
        conv_id = body["conversation_id"]

        # Ephemeral guarantee: only [user, assistant] were persisted. The
        # intermediate tool_use / tool_result turns are invisible to storage,
        # same shape as 5d's ephemeral memory injection.
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        msgs = detail.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "tool please"
        assert msgs[1]["content"] == "final: ping"

    # And the endpoint handed the provider the registered specs (not None).
    # 6c widened the request registry from {echo} to {echo, search_memory} —
    # assert set membership rather than a strict list, so future additions
    # don't churn this test.
    assert scripted.tools_seen
    assert scripted.tools_seen[-1] is not None
    assert "echo" in {s["name"] for s in scripted.tools_seen[-1]}


# --- Tool error path: executor reports is_error=True; chat still 200 --------


class _ErrorRecoveringProvider:
    """Provider that requests an unknown tool once, sees is_error=True in the
    result, and then produces a final apology-style answer. Mirrors how a
    real model would recover from a bad tool call.
    """

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
        result = await tool_executor(ToolCall(id="call_B", name="totally_not_a_tool", arguments={}))
        assert result.is_error is True  # registry surfaces unknown-tool as is_error
        return ChatCompletion(
            content=f"sorry, tool failed: {result.content}",
            model="scripted-2",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="scripted-2", finish_reason="stop")


@pytest.mark.asyncio
async def test_chat_still_200_when_executor_returns_is_error(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    db_app.state.chat_provider = _ErrorRecoveringProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "tool-err@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200, r.text
        assert "totally_not_a_tool" in r.json()["message"]["content"]


# --- tools_enabled=False → provider gets tools=None -------------------------


class _SpyProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        self.calls.append({"tools": tools, "tool_executor": tool_executor})
        return ChatCompletion(
            content=f"(spy) {messages[-1].content}",
            model="spy-1",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="spy-1", finish_reason="stop")


@pytest.mark.asyncio
async def test_tools_enabled_false_passes_tools_none_to_provider(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _SpyProvider()
    db_app.state.chat_provider = spy
    db_app.state.settings = db_app.state.settings.model_copy(update={"tools_enabled": False})

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "tools-off@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    assert spy.calls, "provider must have been called"
    assert spy.calls[-1]["tools"] is None
    assert spy.calls[-1]["tool_executor"] is None


@pytest.mark.asyncio
async def test_tools_enabled_true_passes_registered_specs(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _SpyProvider()
    db_app.state.chat_provider = spy

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "tools-on@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    assert spy.calls[-1]["tools"] is not None
    # 6c added search_memory to the request registry. Assert set membership
    # so future tool additions don't churn this test.
    assert "echo" in {s["name"] for s in spy.calls[-1]["tools"]}
    assert spy.calls[-1]["tool_executor"] is not None


# --- AnthropicProvider: SDK-level tool loop ---------------------------------


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
            SimpleNamespace(
                type="tool_use",
                id=call_id,
                name=tool_name,
                input=arguments,
            ),
        ],
        model="claude-fake",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        stop_reason="tool_use",
    )


def _anthropic_provider(create_mock: AsyncMock, *, max_iters: int = 5) -> AnthropicProvider:
    client = MagicMock()
    client.messages.create = create_mock
    client.close = AsyncMock()
    return AnthropicProvider(
        client=client,
        model="claude-sonnet-5",
        max_tokens=1024,
        max_tool_iterations=max_iters,
    )


@pytest.mark.asyncio
async def test_anthropic_provider_runs_one_tool_round_then_returns_final_text() -> None:
    """Round 1: SDK returns tool_use → provider calls executor with the right
    ToolCall → round 2 SDK call carries assistant + tool_result turns →
    SDK returns final text → provider returns that text as ChatCompletion.
    """
    responses = [
        _fake_tool_use_response(call_id="toolu_1", tool_name="echo", arguments={"text": "ping"}),
        _fake_text_response(text="i saw ping"),
    ]
    create = AsyncMock(side_effect=responses)
    provider = _anthropic_provider(create)

    executor_calls: list[ToolCall] = []

    async def executor(call: ToolCall) -> ToolResult:
        executor_calls.append(call)
        return ToolResult(tool_call_id=call.id, content="ping", is_error=False)

    completion = await provider.complete(
        messages=[ChatMessage(role="user", content="run echo")],
        tools=[{"name": "echo", "description": "x", "input_schema": {}}],
        tool_executor=executor,
    )

    # Executor called with the model's ToolCall verbatim.
    assert len(executor_calls) == 1
    assert executor_calls[0].id == "toolu_1"
    assert executor_calls[0].name == "echo"
    assert executor_calls[0].arguments == {"text": "ping"}

    # Two SDK round-trips.
    assert create.await_count == 2

    # Second call's messages carry the assistant+tool_result turns.
    second_call_msgs = create.await_args_list[1].kwargs["messages"]
    # The base user turn + assistant(tool_use) + user(tool_result) = 3 rows.
    assert [m["role"] for m in second_call_msgs] == ["user", "assistant", "user"]
    # Assistant turn preserves the tool_use block for the SDK.
    assert second_call_msgs[1]["content"][0]["type"] == "tool_use"
    assert second_call_msgs[1]["content"][0]["id"] == "toolu_1"
    # User turn is the tool_result block referencing that id.
    assert second_call_msgs[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_1",
        "content": "ping",
    }

    # Final ChatCompletion is the second call's text.
    assert completion.content == "i saw ping"
    assert completion.finish_reason == "end_turn"


@pytest.mark.asyncio
async def test_anthropic_provider_maps_is_error_true_onto_tool_result_block() -> None:
    responses = [
        _fake_tool_use_response(call_id="toolu_x", tool_name="bad", arguments={}),
        _fake_text_response(text="ok, sorry"),
    ]
    create = AsyncMock(side_effect=responses)
    provider = _anthropic_provider(create)

    async def executor(call: ToolCall) -> ToolResult:
        return ToolResult(tool_call_id=call.id, content="boom", is_error=True)

    await provider.complete(
        messages=[ChatMessage(role="user", content="try bad")],
        tools=[{"name": "bad", "description": "x", "input_schema": {}}],
        tool_executor=executor,
    )

    tool_result = create.await_args_list[1].kwargs["messages"][2]["content"][0]
    assert tool_result["is_error"] is True
    assert tool_result["content"] == "boom"


@pytest.mark.asyncio
async def test_anthropic_provider_hits_iteration_cap_and_returns_max_flag() -> None:
    """SDK always returns tool_use → provider caps out at max_tool_iterations
    (2 here for a fast test), returns the last text with finish_reason set.
    """
    always_tool_use = _fake_tool_use_response(
        call_id="toolu_loop", tool_name="echo", arguments={"text": "x"}
    )

    async def sdk_always_tool_use(**_kwargs: Any) -> SimpleNamespace:
        # Return a fresh object each call so shared state doesn't mask bugs.
        return _fake_tool_use_response(
            call_id="toolu_loop", tool_name="echo", arguments={"text": "x"}
        )

    create = AsyncMock(side_effect=sdk_always_tool_use)
    provider = _anthropic_provider(create, max_iters=2)

    async def executor(call: ToolCall) -> ToolResult:
        return ToolResult(tool_call_id=call.id, content="x")

    completion = await provider.complete(
        messages=[ChatMessage(role="user", content="loop")],
        tools=[{"name": "echo", "description": "x", "input_schema": {}}],
        tool_executor=executor,
    )

    # With max_iters=2 → up to 3 SDK calls (2 tool rounds + 1 more that also
    # returns tool_use and trips the cap). No infinite loop.
    assert create.await_count == 3
    assert completion.finish_reason == "max_tool_iterations"
    # Fabricated response has no text block, so content is empty — that's fine;
    # what matters is the cap tag and finite call count.
    assert completion.content == ""
    # Silence unused-var warning (kept for readability of what the SDK returns).
    del always_tool_use


@pytest.mark.asyncio
async def test_anthropic_provider_no_tools_kwarg_when_tools_none() -> None:
    create = AsyncMock(return_value=_fake_text_response(text="hi"))
    provider = _anthropic_provider(create)

    await provider.complete(messages=[ChatMessage(role="user", content="hi")])

    # Backward compat: no tools kwarg pushed to the SDK when caller passed None.
    assert "tools" not in create.await_args.kwargs


@pytest.mark.asyncio
async def test_anthropic_provider_passes_tools_kwarg_when_provided() -> None:
    create = AsyncMock(return_value=_fake_text_response(text="hi"))
    provider = _anthropic_provider(create)

    specs = [{"name": "echo", "description": "x", "input_schema": {"type": "object"}}]
    await provider.complete(messages=[ChatMessage(role="user", content="hi")], tools=specs)

    assert create.await_args.kwargs["tools"] == specs
