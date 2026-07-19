"""Phase 6a — tool framework foundation.

Covers the port VOs, the mock EchoTool, the registry's best-effort execute
(unknown name + raising tool both → is_error=True, no propagation), the
config-driven build, and the lifespan/dep wiring on app.state.

Nothing here exercises HTTP — 6a wires no route. 6b will.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.ai.tools import EchoTool, ToolRegistry, build_tool_registry
from app.application.ports.tools import ToolCall, ToolResult
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


# --- EchoTool ---------------------------------------------------------------


def test_echo_tool_spec_shape() -> None:
    tool = EchoTool()
    assert tool.name == "echo"
    assert tool.description == "Echo back the provided text."
    assert tool.input_schema == {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }


@pytest.mark.asyncio
async def test_echo_tool_run_returns_the_text() -> None:
    tool = EchoTool()
    out = await tool.run({"text": "hello world"})
    assert out == "hello world"


# --- Registry: register / get / specs ---------------------------------------


def test_registry_register_and_get() -> None:
    r = ToolRegistry()
    tool = EchoTool()
    assert r.get("echo") is None
    r.register(tool)
    assert r.get("echo") is tool
    assert r.get("missing") is None


def test_registry_specs_shape_matches_anthropic_tool_use_format() -> None:
    """The list matches Anthropic's tool-use `tools=[...]` shape verbatim, so
    the 6b provider adapter can pass this through without reshaping.
    """
    r = ToolRegistry()
    r.register(EchoTool())
    specs = r.specs()
    assert isinstance(specs, list)
    assert len(specs) == 1
    spec = specs[0]
    assert set(spec.keys()) == {"name", "description", "input_schema"}
    assert spec["name"] == "echo"
    assert spec["description"] == "Echo back the provided text."
    assert spec["input_schema"]["type"] == "object"


def test_registry_specs_empty_when_nothing_registered() -> None:
    assert ToolRegistry().specs() == []


# --- Registry.execute: best-effort, never raises ----------------------------


@pytest.mark.asyncio
async def test_execute_known_tool_returns_non_error_result_with_content() -> None:
    r = ToolRegistry()
    r.register(EchoTool())
    result = await r.execute(ToolCall(id="call_1", name="echo", arguments={"text": "hi"}))
    assert isinstance(result, ToolResult)
    assert result.tool_call_id == "call_1"
    assert result.content == "hi"
    assert result.is_error is False


@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_error_result_and_does_not_raise() -> None:
    r = ToolRegistry()
    r.register(EchoTool())
    result = await r.execute(ToolCall(id="call_2", name="not_a_tool", arguments={}))
    assert result.is_error is True
    assert result.tool_call_id == "call_2"
    assert "not_a_tool" in result.content


class _RaisingTool:
    """Stub tool whose run() always raises. Used to prove propagation is caught."""

    @property
    def name(self) -> str:
        return "raiser"

    @property
    def description(self) -> str:
        return "Always raises."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def run(self, arguments: dict[str, Any]) -> str:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_execute_when_tool_raises_returns_error_result_no_propagation() -> None:
    r = ToolRegistry()
    r.register(_RaisingTool())
    result = await r.execute(ToolCall(id="call_3", name="raiser", arguments={}))
    assert result.is_error is True
    assert result.tool_call_id == "call_3"
    assert result.content == "boom"


@pytest.mark.asyncio
async def test_execute_missing_required_argument_reports_as_error_not_500() -> None:
    """EchoTool.run does no schema validation — a missing key raises KeyError.
    Verifies the catch path handles bad-argument tool calls the same way as
    downstream tool failures: is_error=True, no propagation.
    """
    r = ToolRegistry()
    r.register(EchoTool())
    result = await r.execute(ToolCall(id="call_4", name="echo", arguments={}))
    assert result.is_error is True
    assert result.tool_call_id == "call_4"


# --- build_tool_registry ----------------------------------------------------


def test_build_tool_registry_registers_echo_by_default() -> None:
    registry = build_tool_registry(_base())
    assert isinstance(registry, ToolRegistry)
    assert registry.get("echo") is not None
    assert [s["name"] for s in registry.specs()] == ["echo"]


# --- lifespan wiring: db_app fixture pins a built registry ------------------


def test_db_app_pins_tool_registry_on_state(db_app) -> None:  # type: ignore[no-untyped-def]
    """Parity with chat_provider / embedding_provider / memory_extractor —
    the fixture manually pins app.state.tool_registry because tests skip the
    lifespan. Confirms the wire-up and the shape a route dep would receive.
    """
    registry = db_app.state.tool_registry
    assert isinstance(registry, ToolRegistry)
    assert registry.get("echo") is not None
