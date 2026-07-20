"""Agent definitions + startup registry builder.

Mirror of `app/ai/tools/__init__.py` shape: `_built_in_agents()` names the
baseline set in one place; `build_agent_registry(settings)` pins them onto
a fresh registry at startup. Nothing consumes this registry yet — 6f is the
contract-and-registry slice; 6g wires it into `/chat` + `/chat/stream`.

The default "assistant" agent is deliberately shaped so 6g's wire-up stays
byte-for-byte compatible with today's behavior:
  - `system_prompt=""` → no persona system message injected.
  - `tool_names=None` → the agent offers EVERY registered tool.

Distinct personas / tool subsets arrive as later opt-in agents; they do not
belong in this slice.
"""

from __future__ import annotations

from app.ai.agents.registry import AgentRegistry
from app.application.ports.agents import AgentDefinition
from app.infrastructure.config import Settings


def _built_in_agents() -> list[AgentDefinition]:
    """Baseline agent set — defined in exactly one place."""
    return [
        AgentDefinition(
            name="assistant",
            description="General-purpose Neo assistant.",
            system_prompt="",
            tool_names=None,
        ),
    ]


def build_agent_registry(settings: Settings) -> AgentRegistry:
    """Startup registry — built once, pinned on `app.state.agent_registry`."""
    del settings  # unused; kept for parity with build_tool_registry / build_chat_provider
    registry = AgentRegistry()
    for agent in _built_in_agents():
        registry.register(agent)
    return registry


__all__ = [
    "AgentRegistry",
    "build_agent_registry",
]
