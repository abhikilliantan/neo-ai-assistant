"""Adapter: expose a WorkflowDefinition as a Tool (Phase 7b).

WORKFLOWS ARE TOOLS. This wraps ONE WorkflowDefinition + the WorkflowClient so
a workflow enters the model-facing tool list and runs through the EXISTING
tool-use loop, tool registry, per-agent filtering, and SSE tool frames — no
parallel execution path.

`name` / `description` / `input_schema` are read straight off the definition,
verbatim: 7a chose Anthropic's tool-input-schema shape precisely so nothing
needs reshaping here.

Error mapping (7a flag #2). The client can BOTH return `ok=False` AND raise
(network / timeout in 7c). We deliberately add NO try/except — `ToolRegistry.
execute` already wraps `run()` in a broad `except Exception` that turns any
raise into `ToolResult(is_error=True, content=str(e))`. So there is exactly
ONE error path:
  - client raises          → propagates → registry catch → is_error=True.
  - `run()` returns ok=False → we RAISE with `run.output` as the message → the
    SAME registry catch → is_error=True, and the model reads `run.output` as
    the failure text.
Routing ok=False through a raise (rather than returning the text as a normal
result) is what makes the failure reach the model as an ERROR it should
recover from, not a success it should trust. Only `ok=True` returns
`run.output` as a normal (is_error=False) result.

No logging here, and `arguments` are never placed anywhere but the client
call — the chip/ frame layer carries name+ok only (7a flag #4).
"""

from __future__ import annotations

from typing import Any

from app.application.ports.workflows import WorkflowClient, WorkflowDefinition


class WorkflowTool:
    def __init__(self, *, definition: WorkflowDefinition, client: WorkflowClient) -> None:
        self._definition = definition
        self._client = client

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def description(self) -> str:
        return self._definition.description

    @property
    def input_schema(self) -> dict[str, Any]:
        return self._definition.input_schema

    async def run(self, arguments: dict[str, Any]) -> str:
        run = await self._client.run(name=self._definition.name, arguments=arguments)
        if not run.ok:
            # Raise so ToolRegistry.execute's existing catch maps this to
            # ToolResult(is_error=True). `run.output` is the backend's failure
            # description and becomes the is_error content the model reads.
            # No arguments are included in the message.
            raise RuntimeError(run.output)
        return run.output
