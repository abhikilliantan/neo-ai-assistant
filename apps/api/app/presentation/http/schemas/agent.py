"""Response schema for GET /api/v1/agents.

Whitelist-shaped: explicitly enumerates ONLY the fields safe to expose.
Handler constructs `AgentOut(name=..., description=...)` field-by-field
rather than `model_validate(agent_def)`, so even if `AgentDefinition`
grows a new internal field tomorrow, it structurally cannot leak here.

Withheld on purpose:
  - `system_prompt` — internal prompt engineering. Leaking invites prompt
    injection / jailbreak crafting and lets clients clone personas verbatim.
  - `tool_names` — internal policy. Exposing lets clients enumerate the
    tool surface per agent and guess-and-check for restricted tools.

Same discipline as 5e-1's MemoryOut excluding the raw embedding.
"""

from __future__ import annotations

from pydantic import BaseModel


class AgentOut(BaseModel):
    name: str
    description: str
