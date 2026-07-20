"""Tool-use port + value objects.

Framework-free VOs + a Protocol, following the chat / embeddings / extractor
pattern. Nothing in this file references FastAPI or SQLAlchemy — the spec is
what the domain layer will hand to whichever provider adapter can consume it.

Spec shape rationale: `{name, description, input_schema}` is Anthropic's
tool-use payload verbatim. Keeping the port shape identical means 6b's
provider adapter passes `registry.specs()` through without reshaping, and
a future provider (OpenAI, Gemini) that uses `parameters` instead of
`input_schema` reshapes on its own edge — the port stays neutral to the one
convention the API standardized on first.

`input_schema` is a raw JSON Schema dict, not a Pydantic model, because that's
what the model expects on the wire and because validating arguments is a
tool-internal concern — different tools want different depth of validation.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel


class ToolCall(BaseModel):
    """A model's request to invoke a tool.

    `id` is opaque — assigned by the provider (e.g. Anthropic's `toolu_...`).
    The registry echoes it back on the ToolResult so the model can correlate.
    """

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result fed back to the model in the next turn.

    `is_error` is a semantic flag, not a transport error — the tool ran (or
    couldn't be found), and this is what the model should read. Providers
    typically map `is_error=True` to a distinct `tool_result` variant so the
    model knows to recover rather than trust the content.
    """

    tool_call_id: str
    content: str
    is_error: bool = False


class ToolInvocation(BaseModel):
    """A tool the provider ran during the CURRENT turn — surfaced live to
    the UI so the user can see "Neo used X". This is view-layer signal only:
    NEVER persisted onto message rows, NEVER reloaded with history.

    Fields are deliberately minimal — `name` (a stable identifier the UI
    turns into a human label like "Searched your memories") and `ok`
    (`not result.is_error`). Arguments are NOT included: a search query
    string can carry sensitive user text, and the label is enough to tell
    the story. Add richer fields only when a concrete UI need appears.
    """

    name: str
    ok: bool


class Tool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def input_schema(self) -> dict[str, Any]: ...

    async def run(self, arguments: dict[str, Any]) -> str: ...
