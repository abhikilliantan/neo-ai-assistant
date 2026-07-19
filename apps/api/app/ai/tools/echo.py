"""Deterministic mock tool. Zero external calls; suitable for tests + local
dev before real tools land. The CI/test default.

`run` deliberately does no schema validation — a missing `text` key raises
KeyError, which the registry catches and returns as a is_error=True result.
That path is exercised by tests.
"""

from __future__ import annotations

from typing import Any


class EchoTool:
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echo back the provided text."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    async def run(self, arguments: dict[str, Any]) -> str:
        return str(arguments["text"])
