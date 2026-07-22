"""Phase 7a — workflow platform foundation.

Covers the port VOs (WorkflowDefinition / WorkflowRun, incl. input_schema
round-tripping verbatim), the deterministic MockWorkflowClient, the registry
surface (register/get/list_names/definitions + duplicate-register RAISES), the
config-driven builders (mock vs n8n→NotImplementedError), the kill switch's
inert-at-this-stage meaning, and the lifespan/dep wiring on app.state.

Nothing here exercises HTTP — 7a wires NO route (WORKFLOWS ARE TOOLS; 7b wires
them into the tool loop). Mirrors tests/test_tools.py + tests/test_agents.py
1:1 so the three feel like siblings.
"""

from __future__ import annotations

import json

import pytest

from app.ai.workflows import (
    MockWorkflowClient,
    WorkflowRegistry,
    build_workflow_client,
    build_workflow_registry,
)
from app.application.ports.workflows import WorkflowDefinition, WorkflowRun
from app.infrastructure.config import Settings
from app.main import create_app


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


# --- VO shape ---------------------------------------------------------------


def test_workflow_definition_shape_and_input_schema_round_trips_verbatim() -> None:
    """`input_schema` is Anthropic tool-input-schema shape, passed to the model
    VERBATIM in 7b — so it must round-trip through the VO byte-for-byte, no
    coercion, no reshaping.
    """
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Task title."},
            "due_date": {"type": "string"},
        },
        "required": ["title"],
    }
    d = WorkflowDefinition(name="create_task", description="Create a task.", input_schema=schema)
    assert d.name == "create_task"
    assert d.description == "Create a task."
    # Same object content, unchanged — this is the property 7b's adapter relies on.
    assert d.input_schema == schema
    assert d.model_dump()["input_schema"] == schema


def test_workflow_run_shape_output_is_string() -> None:
    """`output` is a STRING — it becomes tool_result content (text on the wire).
    A JSON-returning workflow is serialized by the client, not the port.
    """
    run = WorkflowRun(ok=True, output="anything")
    assert run.ok is True
    assert run.output == "anything"
    assert isinstance(run.output, str)


# --- MockWorkflowClient: deterministic, no network --------------------------


@pytest.mark.asyncio
async def test_mock_client_returns_ok_true_with_expected_output_shape() -> None:
    client = MockWorkflowClient()
    args = {"title": "ship it", "due_date": "2026-08-01"}
    run = await client.run(name="create_task", arguments=args)
    assert run.ok is True
    expected = f"[mock-workflow:create_task] {json.dumps(args, sort_keys=True)}"
    assert run.output == expected


@pytest.mark.asyncio
async def test_mock_client_is_deterministic_and_order_independent() -> None:
    """Same name + arguments → identical output every call, regardless of the
    dict insertion order (sort_keys=True in the mock).
    """
    client = MockWorkflowClient()
    run_a = await client.run(name="create_task", arguments={"b": 2, "a": 1})
    run_b = await client.run(name="create_task", arguments={"a": 1, "b": 2})
    assert run_a.output == run_b.output
    expected = "[mock-workflow:create_task] " + json.dumps({"a": 1, "b": 2}, sort_keys=True)
    assert run_a.output == expected


# --- Registry: register / get / list_names / definitions --------------------


def test_registry_register_and_get() -> None:
    r = WorkflowRegistry()
    wf = WorkflowDefinition(name="create_task", description="Create.", input_schema={})
    assert r.get("create_task") is None
    r.register(wf)
    assert r.get("create_task") is wf
    assert r.get("missing") is None


def test_registry_list_names_and_definitions_reflect_registration_order() -> None:
    r = WorkflowRegistry()
    r.register(WorkflowDefinition(name="create_task", description="Create.", input_schema={}))
    r.register(WorkflowDefinition(name="send_email", description="Send.", input_schema={}))
    assert r.list_names() == ["create_task", "send_email"]
    assert [d.name for d in r.definitions()] == ["create_task", "send_email"]


def test_registry_empty_when_nothing_registered() -> None:
    r = WorkflowRegistry()
    assert r.list_names() == []
    assert r.definitions() == []


def test_registry_duplicate_register_raises() -> None:
    """Chose RAISE (AgentRegistry semantic), NOT ToolRegistry's overwrite:
    workflows are a small code-owned set registered once at startup, so a
    duplicate name is a copy-paste bug. And the workflow name IS the tool name
    the model calls in 7b — a silent overwrite would route a call to the wrong
    definition. Fail loudly at startup.
    """
    r = WorkflowRegistry()
    r.register(WorkflowDefinition(name="create_task", description="Create.", input_schema={}))
    with pytest.raises(ValueError, match="already registered: create_task"):
        r.register(WorkflowDefinition(name="create_task", description="Dup.", input_schema={}))


# --- build_workflow_registry: seeds the demo workflow -----------------------


def test_build_workflow_registry_seeds_create_task_demo() -> None:
    registry = build_workflow_registry(_base())
    assert isinstance(registry, WorkflowRegistry)
    assert registry.list_names() == ["create_task"]

    create_task = registry.get("create_task")
    assert create_task is not None
    # input_schema is Anthropic tool-input-schema shape (verbatim for 7b).
    assert create_task.input_schema["type"] == "object"
    assert create_task.input_schema["required"] == ["title"]
    assert "title" in create_task.input_schema["properties"]


# --- build_workflow_client: config-driven -----------------------------------


def test_build_workflow_client_returns_mock_on_mock() -> None:
    client = build_workflow_client(_base(workflow_client="mock"))
    assert isinstance(client, MockWorkflowClient)


def test_build_workflow_client_n8n_without_config_fails_fast() -> None:
    """7c implemented the n8n branch; it no longer raises NotImplementedError.
    Selecting n8n without its config fails fast with a RuntimeError rather than
    silently falling back to mock. (Full n8n coverage: test_n8n_workflow_client.)
    """
    with pytest.raises(RuntimeError, match="N8N_BASE_URL"):
        build_workflow_client(_base(workflow_client="n8n"))


# --- workflows_enabled: inert at this stage ---------------------------------


def test_workflows_enabled_defaults_true() -> None:
    assert _base().workflows_enabled is True


def test_workflows_enabled_false_is_inert_this_slice() -> None:
    """At 7a NOTHING consumes `workflows_enabled` — it mirrors `tools_enabled`,
    which build_tool_registry also ignores; the gate is a route-level concern
    landing in 7b. So flipping it False changes nothing observable: the client
    is still the mock and the registry is still fully seeded. Asserting exactly
    that, rather than testing a hollow no-op.
    """
    settings = _base(workflows_enabled=False)
    assert settings.workflows_enabled is False
    assert isinstance(build_workflow_client(settings), MockWorkflowClient)
    assert build_workflow_registry(settings).list_names() == ["create_task"]


# --- lifespan wiring: db_app fixture pins client + registry -----------------


def test_db_app_pins_workflow_client_and_registry_on_state(db_app) -> None:  # type: ignore[no-untyped-def]
    """Parity with tool_registry / agent_registry — the fixture manually pins
    app.state because tests skip the lifespan. Confirms the wire-up and the
    shape a route dep would receive.
    """
    assert isinstance(db_app.state.workflow_client, MockWorkflowClient)
    registry = db_app.state.workflow_registry
    assert isinstance(registry, WorkflowRegistry)
    assert registry.get("create_task") is not None


def test_create_app_leaves_state_workflow_wiring_uninitialized_until_lifespan() -> None:
    """`create_app` builds the app instance; workflow client + registry are
    pinned inside the lifespan (fixtures pin manually because tests skip it).
    Parity with the other providers.
    """
    app = create_app(_base())
    assert not hasattr(app.state, "workflow_client")
    assert not hasattr(app.state, "workflow_registry")


# --- startup log includes workflows="create_task" ---------------------------


@pytest.mark.asyncio
async def test_lifespan_logs_workflows_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the lifespan runs, its structlog "startup" line carries the joined
    workflow names, alongside the existing tools/agents fields. Same technique
    as the 6f startup-log test.
    """
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    import app.main as main_mod

    captured: dict[str, object] = {}

    class _CapturingLog:
        def info(self, event: str, **kwargs: object) -> None:
            if event == "startup":
                captured.update(kwargs)

        def warning(self, event: str, **kwargs: object) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(main_mod, "get_logger", lambda _name: _CapturingLog())
    fake_db = SimpleNamespace(dispose=AsyncMock())
    fake_redis = SimpleNamespace(aclose=AsyncMock())
    fake_provider = SimpleNamespace(close=AsyncMock())
    fake_embed = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(main_mod, "build_database", lambda _s: fake_db)
    monkeypatch.setattr(main_mod, "build_system_database", lambda _s: fake_db)
    monkeypatch.setattr(main_mod, "build_redis", lambda _s: fake_redis)
    monkeypatch.setattr(main_mod, "build_chat_provider", lambda _s: fake_provider)
    monkeypatch.setattr(main_mod, "build_embedding_provider", lambda _s: fake_embed)
    monkeypatch.setattr(main_mod, "probe_storage_writable", AsyncMock())
    monkeypatch.setattr(main_mod, "build_memory_extractor", lambda _s, _p: MagicMock())
    monkeypatch.setattr(main_mod, "DatabaseHealthCheck", lambda **_kw: MagicMock())
    monkeypatch.setattr(main_mod, "RedisHealthCheck", lambda **_kw: MagicMock())

    app = create_app(_base())
    async with main_mod.lifespan(app):
        pass

    assert captured.get("workflows") == "create_task"
    # Sanity: existing tools/agents lines still carried too (no regression).
    assert "tools" in captured
    assert "agents" in captured
