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
from app.ai.agents.runner import DEFAULT_AGENT_NAME, AgentRunner
from app.application.ports.agents import AgentDefinition
from app.infrastructure.config import Settings


def _built_in_agents() -> list[AgentDefinition]:
    """Baseline agent set — defined in exactly one place.

    "recall" (6h): the first non-default persona. Exercises both persona
    injection (non-empty system_prompt) and tool-subset filtering
    (tool_names=["search_memory"] excludes echo). Demoable end-to-end on the
    real stack — search-then-answer grounded in the user's stored memories.
    """
    return [
        AgentDefinition(
            name="assistant",
            description="General-purpose Neo assistant.",
            system_prompt="",
            tool_names=None,
        ),
        AgentDefinition(
            name="recall",
            description="Answers from what you've told Neo before.",
            system_prompt=(
                "You are Neo's recall specialist. Before answering, search the "
                "user's saved memories and ground your answer in what you find. "
                "If nothing relevant is stored, say so plainly rather than guessing."
            ),
            tool_names=["search_memory"],
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
    "DEFAULT_AGENT_NAME",
    "AgentRegistry",
    "AgentRunner",
    "build_agent_registry",
]
