"""In-memory agent registry — sibling to `ToolRegistry`.

Duplicate-name `register` RAISES (rather than silently overwriting). Agents
are a small, fixed, code-owned set — a second `register("assistant", ...)`
is a copy-paste bug, not an intended override. Fail loudly at startup so
the misconfiguration surfaces on the first request instead of showing up
as the wrong persona at 3am.
"""

from __future__ import annotations

from app.application.ports.agents import AgentDefinition


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}

    def register(self, agent: AgentDefinition) -> None:
        if agent.name in self._agents:
            raise ValueError(f"agent already registered: {agent.name}")
        self._agents[agent.name] = agent

    def get(self, name: str) -> AgentDefinition | None:
        return self._agents.get(name)

    def list_names(self) -> list[str]:
        return list(self._agents.keys())

    def definitions(self) -> list[AgentDefinition]:
        """Full definitions in registration order — sibling of `ToolRegistry.specs`."""
        return list(self._agents.values())
