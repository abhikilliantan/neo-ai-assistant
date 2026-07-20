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

from collections.abc import Iterable

from app.ai.agents.registry import AgentRegistry
from app.ai.agents.runner import DEFAULT_AGENT_NAME, AgentRunner
from app.ai.tools import READ_ONLY_TOOL_NAMES
from app.application.ports.agents import AgentDefinition
from app.infrastructure.config import Settings


def _built_in_agents(*, workflow_names: Iterable[str]) -> list[AgentDefinition]:
    """Baseline agent set — defined in exactly one place.

    7d — permissions by classification. The tool sets are DERIVED, not
    hand-listed, so they stay correct as tools/workflows grow:
      - "assistant" (default): the READ-ONLY tools only. It moved OFF
        tool_names=None (which now means "everything incl. side effects") so a
        plain chat can never fire a side-effecting workflow without opt-in.
      - "operator": read-only tools PLUS every workflow name — the ONLY agent
        that can take external actions. Selecting it in the picker IS the
        user's consent, so its description reads like a consent prompt.
      - "recall" (6h): a deliberately narrow read persona (search only).
    """
    read_only = sorted(READ_ONLY_TOOL_NAMES)
    workflows = sorted(workflow_names)
    return [
        AgentDefinition(
            name="assistant",
            description=(
                "General-purpose assistant — answers questions and searches your "
                "memories. Read-only: never changes anything in external systems."
            ),
            system_prompt="",
            tool_names=read_only,
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
        AgentDefinition(
            name="operator",
            description=(
                "Takes actions in your connected systems — can create tasks and "
                "run workflows that change external tools, not just answer. Choose "
                "this when you want Neo to DO things on your behalf."
            ),
            system_prompt=(
                "You are Neo in operator mode. Alongside answering, you can take "
                "real actions in the user's connected systems by running workflows "
                "(for example, creating a task). Run a workflow only when the user "
                "clearly wants that action taken; if the request is ambiguous, ask "
                "first. Prefer read-only tools when only information is needed."
            ),
            tool_names=read_only + workflows,
        ),
    ]


def build_agent_registry(settings: Settings, *, workflow_names: Iterable[str]) -> AgentRegistry:
    """Startup registry — built once, pinned on `app.state.agent_registry`.

    `workflow_names` (the current workflow registry's names) is REQUIRED: the
    "operator" agent's permissions derive from it, so the caller MUST pass the
    live set — forgetting is a TypeError, not a silently powerless operator.
    """
    del settings  # unused; kept for parity with build_tool_registry / build_chat_provider
    names = set(workflow_names)
    # Defense-in-depth (7b's merge already blocks a workflow named like a tool):
    # a workflow colliding with a read-only name would make operator's allow-list
    # ambiguous. Refuse to build.
    overlap = sorted(READ_ONLY_TOOL_NAMES & names)
    if overlap:
        raise RuntimeError(f"workflow name(s) {overlap} collide with read-only tool names")
    registry = AgentRegistry()
    for agent in _built_in_agents(workflow_names=names):
        registry.register(agent)
    return registry


__all__ = [
    "DEFAULT_AGENT_NAME",
    "AgentRegistry",
    "AgentRunner",
    "build_agent_registry",
]
