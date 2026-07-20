"""Workflow-execution port + value objects.

Framework-free VOs + a Protocol, following the chat / embeddings / extractor /
tools / agents pattern. Nothing here references FastAPI or SQLAlchemy — a
WorkflowDefinition is plain data the domain layer hands to whichever client
adapter can run it (MockWorkflowClient now; an n8n webhook client in 7c).

Phase 7 direction is locked: WORKFLOWS ARE TOOLS. Neo calls an n8n workflow
mid-conversation the same way it calls search_memory. So the shapes here are
chosen to compose with the existing Tool seam in 7b with zero glue:

`input_schema` is Anthropic's tool-input-schema shape VERBATIM (the same
decision as 6a's tool spec). Because `WorkflowDefinition` already carries
`{name, description, input_schema}` — exactly a tool spec — 7b's
workflows-as-tools adapter builds the model-facing spec from a definition
without reshaping a single field.

7a is the CONTRACT + REGISTRY + MOCK slice only. Nothing is wired to /chat or
/chat/stream here; 7b does the wiring.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel


class WorkflowDefinition(BaseModel):
    """A named, declarative workflow the model can invoke as a tool.

    `input_schema` is a raw JSON Schema dict in Anthropic tool-use shape, not
    a Pydantic model — that's what the model expects on the wire, and it is
    passed through to the provider VERBATIM in 7b. Keeping it as a dict means
    the port stays neutral to the one convention the API standardized on first
    (a provider that wants `parameters` instead reshapes on its own edge).
    """

    name: str
    description: str
    input_schema: dict[str, Any]


class WorkflowRun(BaseModel):
    """Result of running a workflow, fed back to the model as tool_result.

    `output` is a STRING, not a dict: it becomes `tool_result` content, which
    is text on the wire. If a workflow returns JSON, the CLIENT serializes it
    to a string (7c's n8n adapter does this) — the port never leaks a dict the
    provider layer would have to stringify anyway.

    `ok` is a semantic flag, not a transport signal — it mirrors
    `ToolResult.is_error` (inverted): the workflow ran (or was rejected by the
    backend), and this is what the caller reads. 7b maps `ok=False` onto
    `ToolResult(is_error=True)` so the model knows to recover.
    """

    ok: bool
    output: str


class WorkflowClient(Protocol):
    """Runs a workflow by name with the model-supplied arguments.

    Deliberately minimal and framework-free — the mock satisfies it with no
    network, and 7c's n8n webhook client satisfies the same signature.
    """

    async def run(self, *, name: str, arguments: dict[str, Any]) -> WorkflowRun: ...
