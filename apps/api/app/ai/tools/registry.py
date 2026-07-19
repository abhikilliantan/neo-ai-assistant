"""In-memory tool registry with best-effort execute.

Design contract for `execute`: NEVER raises. Two failure modes both collapse
into `ToolResult(is_error=True, ...)` so the tool-use loop stays intact:
  - unknown tool name — the model asked for something not registered.
  - tool.run raised — some tool-internal problem (bad args, downstream 500).

Both cases carry a message the model can read to recover on the next turn.
Errors are logged in the same structured shape used by 5c's memory.write and
5d's memory.retrieval log lines.
"""

from __future__ import annotations

from typing import Any

from app.application.ports.tools import Tool, ToolCall, ToolResult
from app.infrastructure.logging import get_logger


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[dict[str, Any]]:
        """Provider-ready spec list. Shape matches Anthropic's tool-use format
        so a provider adapter can pass this straight through.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def execute(self, call: ToolCall) -> ToolResult:
        log = get_logger("tool.execute")
        tool = self._tools.get(call.name)
        if tool is None:
            log.warning(
                "tool.execute.unknown",
                tool=call.name,
                tool_call_id=call.id,
            )
            return ToolResult(
                tool_call_id=call.id,
                content=f"unknown tool: {call.name}",
                is_error=True,
            )
        try:
            content = await tool.run(call.arguments)
        except Exception as e:
            log.warning(
                "tool.execute.failed",
                tool=call.name,
                tool_call_id=call.id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return ToolResult(tool_call_id=call.id, content=str(e), is_error=True)
        return ToolResult(tool_call_id=call.id, content=content, is_error=False)
