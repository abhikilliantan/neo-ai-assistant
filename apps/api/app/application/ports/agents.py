"""Agent-definition port + value objects.

Framework-free VO, following the chat / embeddings / extractor / tools pattern.
Nothing in this file references FastAPI or SQLAlchemy — an AgentDefinition is
plain data the domain layer will hand to whichever orchestration surface
consumes it in 6g.

Declarative on purpose: 6f introduces the CONTRACT + REGISTRY only. The
"run this agent" service (given messages → run the tool-use loop with the
agent's system prompt + tool subset) is deferred to 6g. Keeping the VO
purely data means 6g can extract an AgentService without churning the
registry or the built-in definitions.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    """A named, declarative persona + tool contract for a Neo agent.

    Semantics of `tool_names`:
      - `None` (default): the agent has access to EVERY tool the registry
        offers at call time. This is what the current `/chat` + `/chat/stream`
        code does implicitly, so the default "assistant" agent must use this
        value to keep 6g's wire-up byte-for-byte compatible with today's
        behavior.
      - `[]`: an explicit empty subset — the agent has NO tools. Useful for
        a strictly-conversational persona.
      - `["a", "b"]`: exactly that subset. 6g will resolve the names against
        the tool registry at run time (unknown names are the agent author's
        bug — 6f does not resolve or validate them; the VO is pure data).

    `system_prompt` defaults to `""` so the default "assistant" agent
    injects NO persona system message. This is what today's `/chat` path
    does, and it's the precondition for 6g's wire-up being non-breaking.
    Distinct personas set a non-empty prompt.
    """

    name: str
    description: str
    system_prompt: str = ""
    tool_names: list[str] | None = Field(default=None)
