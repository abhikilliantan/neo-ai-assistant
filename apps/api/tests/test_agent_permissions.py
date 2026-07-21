"""Phase 7d — workflow permissions: side-effecting workflows require the
operator agent, and every workflow invocation is audited.

The safety posture this slice locks in:
  - the DEFAULT agent is read-only; a plain chat can NEVER fire a workflow;
  - "operator" is the only built-in that can run workflows — selecting it IS
    the user's consent;
  - built-in agent permissions are DERIVED (read-only tools + workflow names),
    so they can't rot as tools grow, and an unclassified tool fails loudly;
  - a workflow invocation emits an INFO audit line (agent + workflow + ok, no
    arguments); a blocked attempt emits a WARNING.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import structlog.testing
from httpx import ASGITransport, AsyncClient

from app.ai.agents import AgentRunner, build_agent_registry
from app.ai.tools import READ_ONLY_TOOL_NAMES, ToolRegistry, WorkflowTool
from app.ai.tools import _assert_all_tools_classified as assert_classified
from app.ai.workflows import MockWorkflowClient, WorkflowRegistry, build_workflow_registry
from app.application.ports.agents import AgentDefinition
from app.application.ports.chat import (
    ChatCompletion,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.tools import ToolCall, ToolInvocation, ToolResult
from app.application.ports.workflows import WorkflowDefinition
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


# --- permission derivation (the maintenance trap) ---------------------------


def test_default_agent_is_read_only_operator_gets_workflows() -> None:
    """Adding a workflow name flows it to operator and NEVER to the read-only
    agents — the classification is derived, not hand-listed.
    """
    registry = build_agent_registry(_base(), workflow_names=["create_task", "send_email"])

    assistant = registry.get("assistant")
    operator = registry.get("operator")
    assert assistant is not None and operator is not None

    # Default agent: exactly the read-only tools, no workflow.
    assert set(assistant.tool_names or []) == set(READ_ONLY_TOOL_NAMES)
    assert "create_task" not in (assistant.tool_names or [])
    assert "send_email" not in (assistant.tool_names or [])

    # Operator: read-only PLUS every workflow.
    assert set(operator.tool_names or []) == set(READ_ONLY_TOOL_NAMES) | {
        "create_task",
        "send_email",
    }


def test_workflow_colliding_with_read_only_name_fails_to_build() -> None:
    with pytest.raises(RuntimeError, match="collide with read-only"):
        build_agent_registry(_base(), workflow_names=["search_memory"])


def test_build_agent_registry_requires_workflow_names() -> None:
    # Keyword is required — forgetting it is a TypeError, not a silent empty
    # operator (7d "fail loudly").
    with pytest.raises(TypeError):
        build_agent_registry(_base())  # type: ignore[call-arg]


# --- completeness guard: unclassified tool fails loudly ---------------------


class _RogueTool:
    @property
    def name(self) -> str:
        return "rogue"

    @property
    def description(self) -> str:
        return "unclassified"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def run(self, arguments: dict[str, Any]) -> str:  # pragma: no cover
        return "x"


def test_completeness_guard_raises_on_unclassified_tool() -> None:
    reg = ToolRegistry()
    reg.register(_RogueTool())  # neither read-only-classified nor a workflow
    with pytest.raises(RuntimeError, match="unclassified tool"):
        assert_classified(reg, WorkflowRegistry())


def test_completeness_guard_passes_when_everything_classified() -> None:
    from app.ai.tools.echo import EchoTool

    reg = ToolRegistry()
    reg.register(EchoTool())
    reg.register(
        WorkflowTool(
            definition=WorkflowDefinition(name="create_task", description="d", input_schema={}),
            client=MockWorkflowClient(),
        )
    )
    wf = build_workflow_registry(_base())  # knows create_task
    assert_classified(reg, wf)  # no raise


# --- AgentRunner audit: invoked (INFO) + blocked (WARNING) ------------------


async def _ok_executor(call: ToolCall) -> ToolResult:
    return ToolResult(tool_call_id=call.id, content="ran", is_error=False)


@pytest.mark.asyncio
async def test_runner_audits_workflow_invocation_with_actor_without_arguments() -> None:
    operator = AgentDefinition(name="operator", description="d", tool_names=["echo", "create_task"])
    runner = AgentRunner(
        operator,
        workflow_names=frozenset({"create_task"}),
        user_id="user-1",
        org_id="org-9",
    )
    _specs, wrapped = runner.filter_tools(
        [{"name": "create_task", "description": "d", "input_schema": {}}], _ok_executor
    )

    with structlog.testing.capture_logs() as logs:
        await wrapped(ToolCall(id="a", name="create_task", arguments={"title": "buy milk"}))

    audit = [e for e in logs if e.get("event") == "workflow.invoked"]
    assert len(audit) == 1
    assert audit[0]["agent"] == "operator"
    assert audit[0]["workflow"] == "create_task"
    assert audit[0]["ok"] is True
    # Actor is on the record, explicitly.
    assert audit[0]["user_id"] == "user-1"
    assert audit[0]["org_id"] == "org-9"
    # Arguments MUST NOT appear anywhere in the audit record (7a flag #4).
    assert "buy milk" not in repr(audit[0])


@pytest.mark.asyncio
async def test_runner_does_not_audit_plain_tool_calls() -> None:
    operator = AgentDefinition(name="operator", description="d", tool_names=["echo", "create_task"])
    runner = AgentRunner(operator, workflow_names=frozenset({"create_task"}))
    _specs, wrapped = runner.filter_tools(
        [{"name": "echo", "description": "d", "input_schema": {}}], _ok_executor
    )

    with structlog.testing.capture_logs() as logs:
        await wrapped(ToolCall(id="b", name="echo", arguments={"text": "hi"}))

    assert [e for e in logs if e.get("event", "").startswith("workflow.")] == []


@pytest.mark.asyncio
async def test_runner_audits_blocked_workflow_attempt() -> None:
    # A read-only agent that somehow sees a workflow call → blocked + WARNING.
    assistant = AgentDefinition(
        name="assistant", description="d", tool_names=["echo", "search_memory"]
    )
    runner = AgentRunner(
        assistant, workflow_names=frozenset({"create_task"}), user_id="user-1", org_id="org-9"
    )
    _specs, wrapped = runner.filter_tools(
        [{"name": "echo", "description": "d", "input_schema": {}}], _ok_executor
    )

    with structlog.testing.capture_logs() as logs:
        result = await wrapped(ToolCall(id="c", name="create_task", arguments={"title": "x"}))

    assert result.is_error is True
    blocked = [e for e in logs if e.get("event") == "workflow.blocked"]
    assert len(blocked) == 1
    assert blocked[0]["agent"] == "assistant"
    assert blocked[0]["workflow"] == "create_task"
    assert blocked[0]["user_id"] == "user-1"
    assert blocked[0]["log_level"] == "warning"


# --- end-to-end: default agent can't fire a workflow, operator can ----------


class _ToolRecordingProvider:
    def __init__(self) -> None:
        self.tools_seen: list[list[dict[str, Any]] | None] = []

    async def complete(
        self, *, tools: list[dict[str, Any]] | None = None, **_: object
    ) -> ChatCompletion:
        self.tools_seen.append(tools)
        return ChatCompletion(content="ok", model="rec", usage=None, finish_reason="stop")

    async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:  # pragma: no cover
        raise NotImplementedError
        yield


async def _names_for_agent(db_app: Any, *, agent: str | None) -> set[str]:
    spy = _ToolRecordingProvider()
    db_app.state.chat_provider = spy
    payload: dict[str, Any] = {"messages": [{"role": "user", "content": "hi"}]}
    if agent is not None:
        payload["agent"] = agent
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"7d-{agent or 'default'}@example.com"
        token = (await _register(c, email))["access_token"]
        r = await c.post("/api/v1/chat", headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert r.status_code == 200, r.text
    seen = spy.tools_seen[-1] or []
    return {s["name"] for s in seen}


@pytest.mark.asyncio
async def test_default_agent_never_offered_the_workflow(db_app) -> None:  # type: ignore[no-untyped-def]
    names = await _names_for_agent(db_app, agent=None)
    assert "create_task" not in names
    assert {"echo", "search_memory", "search_documents"} == names


@pytest.mark.asyncio
async def test_operator_agent_is_offered_the_workflow(db_app) -> None:  # type: ignore[no-untyped-def]
    names = await _names_for_agent(db_app, agent="operator")
    assert "create_task" in names
    assert {"echo", "search_memory"} <= names


# --- end-to-end audit: an operator workflow turn logs workflow.invoked ------


class _WorkflowCallingProvider:
    async def complete(
        self, *, tool_executor: ToolExecutor | None = None, **_: object
    ) -> ChatCompletion:
        assert tool_executor is not None
        call = ToolCall(id="w", name="create_task", arguments={"title": "buy milk"})
        result = await tool_executor(call)
        return ChatCompletion(
            content=f"done: {result.content}",
            model="scripted",
            usage=None,
            finish_reason="stop",
            tool_invocations=[ToolInvocation(name=call.name, ok=not result.is_error)],
        )

    async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:  # pragma: no cover
        raise NotImplementedError
        yield


@pytest.mark.asyncio
async def test_operator_workflow_turn_emits_audit_line(db_app) -> None:  # type: ignore[no-untyped-def]
    db_app.state.chat_provider = _WorkflowCallingProvider()
    transport = ASGITransport(app=db_app)
    with structlog.testing.capture_logs() as logs:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            reg = await _register(c, "7d-audit@example.com")
            token = reg["access_token"]
            user_id = reg["user_id"]
            org_id = reg["active_tenant_id"]
            r = await c.post(
                "/api/v1/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "agent": "operator",
                    "messages": [{"role": "user", "content": "make a task"}],
                },
            )
            assert r.status_code == 200, r.text

    audit = [e for e in logs if e.get("event") == "workflow.invoked"]
    assert len(audit) == 1
    assert audit[0]["agent"] == "operator"
    assert audit[0]["workflow"] == "create_task"
    assert audit[0]["ok"] is True
    # The ACTOR is on the record — this is the whole point of the audit trail.
    # Recorded EXPLICITLY (not via contextvars, which capture_logs strips and
    # which don't survive the /chat/stream generator's task boundary).
    assert audit[0]["user_id"] == user_id
    assert audit[0]["org_id"] == org_id
    # The workflow arguments never appear in the audit trail.
    assert "buy milk" not in repr(audit)
