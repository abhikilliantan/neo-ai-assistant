"""Phase 6f — agent framework foundation.

Covers the AgentDefinition VO shape + defaults, the registry surface
(register/get/list_names/definitions, duplicate-register raises), the
config-driven build, and the lifespan/dep wiring on app.state.

Nothing here exercises HTTP — 6f wires NO route. 6g wires it into /chat.
Mirrors tests/test_tools.py's shape 1:1 so the two feel like siblings.
"""

from __future__ import annotations

import pytest

from app.ai.agents import AgentRegistry, build_agent_registry
from app.application.ports.agents import AgentDefinition
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


# --- AgentDefinition VO shape + defaults ------------------------------------


def test_agent_definition_defaults_system_prompt_empty_and_tool_names_none() -> None:
    """The default shape is the byte-compat precondition for 6g's wire-up:
    empty system prompt means no persona injected; tool_names=None means the
    agent offers every registered tool. Together they reproduce today's
    /chat + /chat/stream behavior verbatim.
    """
    a = AgentDefinition(name="x", description="y")
    assert a.system_prompt == ""
    assert a.tool_names is None


def test_agent_definition_accepts_explicit_empty_tool_subset() -> None:
    """`tool_names=[]` is semantically distinct from `None`: a conversational
    persona with NO tools. Round-trip it verbatim; do NOT coerce to None.
    """
    a = AgentDefinition(name="q", description="chat-only", tool_names=[])
    assert a.tool_names == []


def test_agent_definition_accepts_explicit_subset() -> None:
    a = AgentDefinition(
        name="researcher",
        description="Does research.",
        system_prompt="You do deep research.",
        tool_names=["search_memory"],
    )
    assert a.tool_names == ["search_memory"]
    assert a.system_prompt == "You do deep research."


# --- Registry: register / get / list_names / definitions --------------------


def test_registry_register_and_get() -> None:
    r = AgentRegistry()
    agent = AgentDefinition(name="assistant", description="Default.")
    assert r.get("assistant") is None
    r.register(agent)
    assert r.get("assistant") is agent
    assert r.get("missing") is None


def test_registry_list_names_and_definitions_reflect_registration_order() -> None:
    r = AgentRegistry()
    r.register(AgentDefinition(name="assistant", description="Default."))
    r.register(AgentDefinition(name="researcher", description="Research."))
    assert r.list_names() == ["assistant", "researcher"]
    defs = r.definitions()
    assert [d.name for d in defs] == ["assistant", "researcher"]


def test_registry_empty_when_nothing_registered() -> None:
    r = AgentRegistry()
    assert r.list_names() == []
    assert r.definitions() == []


def test_registry_duplicate_register_raises() -> None:
    """Agents are a small, fixed, code-owned set — a second register() of the
    same name is a copy-paste bug, not an intended override. Fail loudly at
    startup so the misconfiguration surfaces on the first request instead of
    quietly serving the wrong persona at 3am.
    """
    r = AgentRegistry()
    r.register(AgentDefinition(name="assistant", description="Default."))
    with pytest.raises(ValueError, match="already registered: assistant"):
        r.register(AgentDefinition(name="assistant", description="Duplicate."))


# --- build_agent_registry ---------------------------------------------------


def test_build_agent_registry_registers_default_assistant() -> None:
    registry = build_agent_registry(_base(), workflow_names=["create_task"])
    assert isinstance(registry, AgentRegistry)
    # 7d adds the "operator" persona; order is [assistant, recall, operator].
    assert registry.list_names() == ["assistant", "recall", "operator"]

    assistant = registry.get("assistant")
    assert assistant is not None
    assert assistant.system_prompt == ""
    # 7d: default agent is READ-ONLY now — no None, no workflow. 8d added
    # search_documents (read-only), sorted into the read-only set.
    assert assistant.tool_names == ["echo", "search_documents", "search_memory"]
    assert "create_task" not in (assistant.tool_names or [])

    # 6h: recall persona exercises BOTH persona injection and tool subset.
    recall = registry.get("recall")
    assert recall is not None
    assert recall.description == "Answers from what you've told Neo before."
    assert recall.system_prompt.startswith("You are Neo's recall specialist.")
    assert recall.tool_names == ["search_memory"]

    # 7d: operator owns workflows — read-only tools PLUS every workflow name.
    operator = registry.get("operator")
    assert operator is not None
    assert operator.tool_names == ["echo", "search_documents", "search_memory", "create_task"]
    assert operator.system_prompt.startswith("You are Neo in operator mode.")
    # Its description reads like a consent prompt (shown in the picker).
    assert "actions" in operator.description.lower()


# --- lifespan wiring: app builds with agent_registry on state ---------------


def test_db_app_pins_agent_registry_on_state(db_app) -> None:  # type: ignore[no-untyped-def]
    """Parity with tool_registry — the fixture manually pins app.state.
    agent_registry because tests skip the lifespan. Confirms the wire-up
    and the shape a route dep would receive.
    """
    registry = db_app.state.agent_registry
    assert isinstance(registry, AgentRegistry)
    assert registry.get("assistant") is not None


def test_create_app_leaves_state_agent_registry_uninitialized_until_lifespan() -> None:
    """`create_app` builds the app instance; the registries are pinned inside
    the lifespan (fixtures pin manually because tests skip lifespan). Confirms
    the wire-up happens in the lifespan, not the factory — parity with the
    other providers.
    """
    app = create_app(_base())
    assert not hasattr(app.state, "agent_registry")


# --- startup log includes agents="assistant,recall" ------------------------


@pytest.mark.asyncio
async def test_lifespan_logs_agents_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the lifespan runs, its structlog "startup" line carries the
    joined agent names. Verified by capturing get_logger("lifespan") calls.

    Stubs the DB/Redis/provider builders so the lifespan can enter/exit
    without external resources — this is a pure wire-up assertion.
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
    # Fake infrastructure — none of it is exercised in this assertion.
    fake_db = SimpleNamespace(dispose=AsyncMock())
    fake_redis = SimpleNamespace(aclose=AsyncMock())
    fake_provider = SimpleNamespace(close=AsyncMock())
    fake_embed = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(main_mod, "build_database", lambda _s: fake_db)
    monkeypatch.setattr(main_mod, "build_system_database", lambda _s: fake_db)
    monkeypatch.setattr(main_mod, "build_redis", lambda _s: fake_redis)
    monkeypatch.setattr(main_mod, "build_chat_provider", lambda _s: fake_provider)
    monkeypatch.setattr(main_mod, "build_embedding_provider", lambda _s: fake_embed)
    monkeypatch.setattr(main_mod, "build_memory_extractor", lambda _s, _p: MagicMock())
    monkeypatch.setattr(main_mod, "DatabaseHealthCheck", lambda **_kw: MagicMock())
    monkeypatch.setattr(main_mod, "RedisHealthCheck", lambda **_kw: MagicMock())

    app = create_app(_base())
    async with main_mod.lifespan(app):
        pass

    assert captured.get("agents") == "assistant,recall,operator"
    # Sanity: existing "tools" line still carried too (no regression).
    assert "tools" in captured
