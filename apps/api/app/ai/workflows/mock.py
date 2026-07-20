"""Deterministic mock workflow client. Zero external calls; the CI/test
default, same posture as MockProvider / MockEmbeddingProvider / EchoTool.

`run` never touches the network and never sleeps. It returns `ok=True` with an
echo-shaped output derived from the workflow name + arguments so tests can
assert on the exact string. Arguments are serialized with `sort_keys=True` so
the output is stable regardless of dict ordering.
"""

from __future__ import annotations

import json
from typing import Any

from app.application.ports.workflows import WorkflowRun


class MockWorkflowClient:
    async def run(self, *, name: str, arguments: dict[str, Any]) -> WorkflowRun:
        encoded = json.dumps(arguments, sort_keys=True)
        return WorkflowRun(ok=True, output=f"[mock-workflow:{name}] {encoded}")
