"""Phase 7b — workflows become tools.

The adapter slice: a WorkflowDefinition enters the model-facing tool list via
WorkflowTool and runs through the EXISTING tool-use loop, registry, per-agent
filtering, and chip/frame surfaces — no parallel execution path. These tests
prove "everything composes":

  - a workflow appears in the tool specs alongside echo/search_memory, schema
    passed through verbatim;
  - end-to-end through the real loop on BOTH endpoints (create_task runs against
    MockWorkflowClient, folds into the final answer);
  - the ephemeral invariant still holds after a workflow turn;
  - a workflow call surfaces as a normal chip (ToolInvocation on /chat, "tool"
    SSE frame on /chat/stream) with NO arguments;
  - error mapping: ok=False AND a raising client BOTH become is_error=True via
    the registry's existing catch;
  - collision: a workflow whose name collides with a tool fails at BUILD time;
  - kill switches on BOTH paths;
  - per-agent filtering excludes the workflow for an agent that didn't ask for it.

Mocks pinned by conftest; NO network anywhere.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.ai.tools import (
    ToolRegistry,
    WorkflowTool,
    build_streaming_request_tool_registry,
)
from app.ai.workflows import (
    MockWorkflowClient,
    WorkflowRegistry,
    build_workflow_registry,
)
from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.tools import ToolCall, ToolInvocation
from app.application.ports.workflows import WorkflowDefinition, WorkflowRun
from app.infrastructure.config import Settings


def _base(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {
        "python_env": "test",
        "database_url": "postgresql+asyncpg://x/x",
        "app_database_url": "postgresql+asyncpg://x/x",
        "redis_url": "redis://x",
        "jwt_secret_key": "test-secret-key-at-least-32-bytes-long-xxxxx",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


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


async def _unused_factory() -> AsyncIterator[Any]:  # pragma: no cover
    """A MemoryRepoFactory stand-in for builder tests that only read specs /
    trigger the workflow merge — the session factory is never opened there.
    """
    yield None


def _wf_registry_with(*names: str) -> WorkflowRegistry:
    r = WorkflowRegistry()
    for n in names:
        r.register(
            WorkflowDefinition(
                name=n,
                description=f"{n} workflow",
                input_schema={"type": "object", "properties": {}, "required": []},
            )
        )
    return r


def _build_registry(
    *, workflow_registry: WorkflowRegistry, settings: Settings | None = None
) -> ToolRegistry:
    return build_streaming_request_tool_registry(
        settings=settings or _base(),
        memory_repo_factory=_unused_factory,  # type: ignore[arg-type]
        document_repo_factory=_unused_factory,  # type: ignore[arg-type]
        embedding_provider=MockEmbeddingProvider(),
        organization_id=uuid4(),
        user_id=uuid4(),
        workflow_registry=workflow_registry,
        workflow_client=MockWorkflowClient(),
    )


# --- specs: workflow joins the tool list, schema verbatim -------------------


def test_workflow_appears_in_specs_with_input_schema_passed_through() -> None:
    wf_registry = build_workflow_registry(_base())  # seeds create_task
    registry = _build_registry(workflow_registry=wf_registry)

    specs = registry.specs()
    by_name = {s["name"]: s for s in specs}
    # Sits alongside the baseline + request tools.
    assert {"echo", "search_memory", "create_task"} <= set(by_name)

    # input_schema is the definition's, VERBATIM (7a's Anthropic shape → 7b
    # passes it through with zero reshaping).
    create_task_def = wf_registry.get("create_task")
    assert create_task_def is not None
    assert by_name["create_task"]["input_schema"] == create_task_def.input_schema
    assert by_name["create_task"]["description"] == create_task_def.description


# --- adapter unit + error mapping (via the registry's existing catch) --------


def _create_task_def() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="create_task",
        description="Create a task.",
        input_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    )


def test_workflow_tool_reads_fields_off_the_definition() -> None:
    definition = _create_task_def()
    tool = WorkflowTool(definition=definition, client=MockWorkflowClient())
    assert tool.name == "create_task"
    assert tool.description == "Create a task."
    assert tool.input_schema is definition.input_schema


@pytest.mark.asyncio
async def test_workflow_tool_run_ok_true_returns_output() -> None:
    tool = WorkflowTool(definition=_create_task_def(), client=MockWorkflowClient())
    out = await tool.run({"title": "ship it"})
    assert out == f"[mock-workflow:create_task] {json.dumps({'title': 'ship it'}, sort_keys=True)}"


class _OkFalseClient:
    """Returns ok=False with a failure description in `output` (the shape 7c's
    n8n client uses when the backend rejects a run).
    """

    async def run(self, *, name: str, arguments: dict[str, Any]) -> WorkflowRun:
        return WorkflowRun(ok=False, output="backend rejected: quota exceeded")


class _RaisingClient:
    """Raises (network/timeout) — the shape 7c's client uses on transport error."""

    async def run(self, *, name: str, arguments: dict[str, Any]) -> WorkflowRun:
        raise ConnectionError("n8n unreachable")


@pytest.mark.asyncio
async def test_ok_false_becomes_is_error_via_existing_registry_catch() -> None:
    """ok=False → WorkflowTool RAISES with run.output → ToolRegistry.execute's
    EXISTING best-effort catch maps it to is_error=True, and the model reads
    run.output as the failure text. No second try/except in the adapter.
    """
    registry = ToolRegistry()
    registry.register(WorkflowTool(definition=_create_task_def(), client=_OkFalseClient()))
    result = await registry.execute(ToolCall(id="c1", name="create_task", arguments={"title": "x"}))
    assert result.is_error is True
    assert result.content == "backend rejected: quota exceeded"


@pytest.mark.asyncio
async def test_raising_client_is_caught_by_existing_registry_catch_not_500() -> None:
    """A raising client propagates out of run() and is caught by the SAME
    registry catch — it becomes is_error=True, never escapes as a 500.
    """
    registry = ToolRegistry()
    registry.register(WorkflowTool(definition=_create_task_def(), client=_RaisingClient()))
    result = await registry.execute(ToolCall(id="c2", name="create_task", arguments={"title": "x"}))
    assert result.is_error is True
    assert result.content == "n8n unreachable"


# --- collision check: build-time ValueError ---------------------------------


def test_collision_with_existing_tool_raises_at_build_time() -> None:
    """A workflow named like a tool (search_memory) must fail loudly when the
    registry is BUILT — before any provider/tool-loop runs — not silently
    overwrite. Proven by the builder raising, so no partial registry escapes.
    """
    colliding = _wf_registry_with("search_memory")
    with pytest.raises(ValueError, match="collides with an existing tool: 'search_memory'"):
        _build_registry(workflow_registry=colliding)


def test_non_colliding_workflow_builds_fine() -> None:
    registry = _build_registry(workflow_registry=_wf_registry_with("create_task"))
    assert registry.get("create_task") is not None


# --- e2e scaffolding: scripted providers that call create_task ---------------


class _WorkflowCallingProvider:
    """Non-streaming double: invokes the executor once for create_task, folds
    the result into the final answer. Records the tools it was handed.
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
        assert tool_executor is not None
        call = ToolCall(id="w1", name="create_task", arguments={"title": "buy milk"})
        result = await tool_executor(call)
        return ChatCompletion(
            content=f"done: {result.content}",
            model="scripted-wf",
            usage=None,
            finish_reason="stop",
            # Mirror AnthropicProvider: one ToolInvocation per executed tool_use,
            # built from call.name + is_error only (no arguments) — the chip the
            # endpoint passes straight through to ChatResponse.
            tool_invocations=[ToolInvocation(name=call.name, ok=not result.is_error)],
        )

    async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:  # pragma: no cover
        raise NotImplementedError
        yield


class _StreamingWorkflowCallingProvider:
    """Streaming double: runs create_task via the executor (silent turn 1), then
    streams the final answer folding the result.
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
        result = await tool_executor(
            ToolCall(id="w2", name="create_task", arguments={"title": "buy milk"})
        )
        # 6d surfaces a "tool" frame for each executed tool_use — mirror that.
        yield ChatStreamEvent(type="tool", tool_name="create_task", tool_ok=not result.is_error)
        text = f"done: {result.content}"
        for i, word in enumerate(text.split(" ")):
            yield ChatStreamEvent(type="delta", content=word if i == 0 else " " + word)
        yield ChatStreamEvent(type="done", model="scripted-wf-stream", finish_reason="stop")


@pytest.mark.asyncio
async def test_chat_runs_workflow_via_loop_and_folds_result(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    scripted = _WorkflowCallingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = (await _register(c, "7b-chat@example.com"))["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            # 7d: workflows require the operator agent (deliberate consent).
            json={
                "agent": "operator",
                "messages": [{"role": "user", "content": "make a task"}],
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # MockWorkflowClient output folded into the final answer.
        expected = (
            f"[mock-workflow:create_task] {json.dumps({'title': 'buy milk'}, sort_keys=True)}"
        )
        assert body["message"]["content"] == f"done: {expected}"
        conv_id = body["conversation_id"]

        # Chip: normal ToolInvocation, name+ok only, NO arguments (7a flag #4).
        invocations = body["tool_invocations"]
        assert {"name": "create_task", "ok": True} in invocations
        for inv in invocations:
            assert set(inv.keys()) == {"name", "ok"}
            assert "arguments" not in inv

        # Ephemeral invariant: tool_use/tool_result stay provider-internal.
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert [m["role"] for m in detail.json()["messages"]] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_chat_stream_runs_workflow_and_emits_tool_frame(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    db_app.state.chat_provider = _StreamingWorkflowCallingProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = (await _register(c, "7b-stream@example.com"))["access_token"]
        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            # 7d: workflows require the operator agent.
            json={
                "agent": "operator",
                "messages": [{"role": "user", "content": "make a task"}],
            },
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        conv_id = events[0]["conversation_id"]
        assert events[-1]["type"] == "done"

        # Chip: a "tool" frame for the workflow — tool_name+tool_ok, NO arguments.
        tool_frames = [e for e in events if e["type"] == "tool"]
        assert len(tool_frames) == 1
        assert tool_frames[0]["tool_name"] == "create_task"
        assert tool_frames[0]["tool_ok"] is True
        assert "arguments" not in tool_frames[0]

        # Ephemeral invariant on the stream path.
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert [m["role"] for m in detail.json()["messages"]] == ["user", "assistant"]


# --- collision fires at BUILD time, before the provider runs ----------------


class _NeverCalledProvider:
    def __init__(self) -> None:
        self.tools_seen: list[Any] = []

    async def complete(self, *, tools: Any = None, **_: object) -> ChatCompletion:
        self.tools_seen.append(tools)  # pragma: no cover — must never be reached
        return ChatCompletion(content="x", model="x", usage=None, finish_reason="stop")

    async def stream(self, *, tools: Any = None, **_: object) -> AsyncIterator[ChatStreamEvent]:
        self.tools_seen.append(tools)  # pragma: no cover — must never be reached
        yield ChatStreamEvent(type="done", model="x", finish_reason="stop")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/chat", "/api/v1/chat/stream"])
async def test_collision_fails_before_provider_runs_on_both_paths(
    db_app,  # type: ignore[no-untyped-def]
    path: str,
) -> None:
    """Pin a colliding workflow registry; the per-request tool-registry build
    raises BEFORE the provider is called — proving it's build-time, not a
    mid-conversation surprise. The provider is never invoked.
    """
    db_app.state.workflow_registry = _wf_registry_with("search_memory")
    spy = _NeverCalledProvider()
    db_app.state.chat_provider = spy

    # raise_app_exceptions=False → the build-time ValueError surfaces as a real
    # 500 response (as it would in production) instead of propagating out of
    # the client. The point of the test is WHEN it fires, not the status code.
    transport = ASGITransport(app=db_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = (await _register(c, f"7b-collide-{path.count('/')}{len(path)}@example.com"))[
            "access_token"
        ]
        r = await c.post(
            path,
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 500  # build-time ValueError → not a graceful client error
    assert spy.tools_seen == []  # provider never ran — collision fired at build time


# --- kill switches on BOTH paths --------------------------------------------


class _ToolRecordingProvider:
    """Records the tools it was handed on either endpoint; runs no tool loop."""

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
        return ChatCompletion(content="ok", model="rec-1", usage=None, finish_reason="stop")

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
        yield ChatStreamEvent(type="done", model="rec-1", finish_reason="stop")


async def _tools_seen_for_turn(
    db_app: Any, *, path: str, email: str, agent: str | None = None
) -> list[dict[str, Any]] | None:
    """Run one turn on `path` and return the tools the provider was handed."""
    spy = _ToolRecordingProvider()
    db_app.state.chat_provider = spy
    payload: dict[str, Any] = {"messages": [{"role": "user", "content": "hi"}]}
    if agent is not None:
        payload["agent"] = agent
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = (await _register(c, email))["access_token"]
        r = await c.post(path, headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert r.status_code == 200, r.text
        if path.endswith("/stream"):
            _ = r.text  # drain the stream so provider.stream runs to completion
    return spy.tools_seen[-1]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/chat", "/api/v1/chat/stream"])
async def test_tools_enabled_false_yields_no_specs_on_both_paths(
    db_app,  # type: ignore[no-untyped-def]
    path: str,
) -> None:
    db_app.state.settings = db_app.state.settings.model_copy(update={"tools_enabled": False})
    seen = await _tools_seen_for_turn(
        db_app, path=path, email=f"7b-notools-{len(path)}@example.com"
    )
    assert seen is None  # kill switch → tools=None, no specs (workflows included)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/chat", "/api/v1/chat/stream"])
async def test_workflows_enabled_false_keeps_tools_but_drops_workflows_on_both_paths(
    db_app,  # type: ignore[no-untyped-def]
    path: str,
) -> None:
    db_app.state.settings = db_app.state.settings.model_copy(update={"workflows_enabled": False})
    # Use operator (which WOULD receive create_task) so create_task's absence
    # proves the kill switch, not just the default agent's read-only filter (7d).
    seen = await _tools_seen_for_turn(
        db_app, path=path, email=f"7b-nowf-{len(path)}@example.com", agent="operator"
    )
    assert seen is not None
    names = {s["name"] for s in seen}
    assert "create_task" not in names  # workflow specs withheld
    assert {"echo", "search_memory"} <= names  # ordinary tools still present


# --- per-agent filtering: workflows inherit 6g's filter for free ------------


@pytest.mark.asyncio
async def test_agent_tool_subset_excludes_the_workflow(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """The 'recall' agent declares tool_names=["search_memory"]. The workflow
    create_task is a tool like any other, so filter_tools drops it for this
    agent — proving workflows compose with 6g's per-agent filtering rather than
    bypassing it. This is the "everything composes" proof.
    """
    seen = await _tools_seen_for_turn(
        db_app, path="/api/v1/chat", email="7b-agentfilter@example.com", agent="recall"
    )
    assert seen is not None
    names = {s["name"] for s in seen}
    assert names == {"search_memory"}
    assert "create_task" not in names
