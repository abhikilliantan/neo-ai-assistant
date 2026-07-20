"""In-memory workflow registry — sibling to `AgentRegistry` / `ToolRegistry`.

Duplicate-name `register` RAISES (AgentRegistry's semantic, NOT ToolRegistry's
overwrite). Two reasons workflows land on "raise":

  1. Like agents, workflow definitions are a small, fixed, code-owned set
     registered ONCE at startup. A second `register("create_task", ...)` is a
     copy-paste bug, not an intended override. (ToolRegistry overwrites only
     because it is rebuilt per-request, re-registering the same stateless set
     every time — last-wins is harmless there. This registry is built once.)

  2. Load-bearing for 7b, where WORKFLOWS ARE TOOLS: the workflow name IS the
     tool name the model calls. A silent overwrite would route the model's
     `create_task` call to a different definition than intended — a
     correctness landmine. Fail loudly at startup instead.
"""

from __future__ import annotations

from app.application.ports.workflows import WorkflowDefinition


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, workflow: WorkflowDefinition) -> None:
        if workflow.name in self._workflows:
            raise ValueError(f"workflow already registered: {workflow.name}")
        self._workflows[workflow.name] = workflow

    def get(self, name: str) -> WorkflowDefinition | None:
        return self._workflows.get(name)

    def list_names(self) -> list[str]:
        return list(self._workflows.keys())

    def definitions(self) -> list[WorkflowDefinition]:
        """Full definitions in registration order — sibling of
        `AgentRegistry.definitions` / `ToolRegistry.specs`. Because a
        WorkflowDefinition already carries `{name, description, input_schema}`,
        7b's workflows-as-tools adapter builds tool specs straight from this.
        """
        return list(self._workflows.values())
