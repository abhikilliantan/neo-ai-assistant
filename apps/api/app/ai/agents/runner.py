"""AgentRunner — thin per-request seam that applies an AgentDefinition to
the inputs of a single provider call.

Scope is deliberately narrow:
  - `prepare_messages`: prepend the agent's persona system message.
  - `filter_tools`: restrict the provider's tool set to the agent's subset.

Nothing else. The runner does NOT own the tool-use loop (that stays inside
the provider), does NOT do persistence (Txn A/B/C stay in the endpoint), and
does NOT do retrieval (5d stays in the endpoint). It is the smallest seam
6h/6i can grow orchestration from without turning into a god-object.

Byte-compat contract for the default `assistant` agent
(`system_prompt=""`, `tool_names=None`):
  - `prepare_messages` returns the input list object unchanged (no allocation).
  - `filter_tools` returns `(specs, executor)` unchanged.
Together these keep `/chat` + `/chat/stream` output identical to today.
"""

from __future__ import annotations

from typing import Any

from app.application.ports.agents import AgentDefinition
from app.application.ports.chat import ChatMessage, ToolExecutor
from app.application.ports.tools import ToolCall, ToolResult

DEFAULT_AGENT_NAME = "assistant"


class AgentRunner:
    def __init__(self, agent: AgentDefinition) -> None:
        self._agent = agent

    def prepare_messages(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Prepend the persona system message when non-empty; else return
        `messages` unchanged. The persona goes FIRST — ahead of the 5d memory
        context system message the endpoint already prepended — so wire order
        is [persona, memory, ...user/assistant]. Anthropic joins system
        messages into a single top-level `system=` on the wire, so relative
        order among system messages is a payload-shape detail, not a semantic
        one, but keeping persona first matches how humans read the prompt.
        """
        if not self._agent.system_prompt:
            return messages
        return [
            ChatMessage(role="system", content=self._agent.system_prompt),
            *messages,
        ]

    def filter_tools(
        self,
        specs: list[dict[str, Any]],
        executor: ToolExecutor,
    ) -> tuple[list[dict[str, Any]], ToolExecutor]:
        """Restrict `specs` + wrap `executor` to enforce the agent's subset.

        `tool_names is None` → return `(specs, executor)` unchanged (default
        agent path — byte-compat). Otherwise: filter specs down to allowed
        names, and wrap the executor so a call to a non-allowed tool returns
        `is_error=True` with a readable message (the tool-use loop keeps
        going; the model recovers on the next turn).

        Empty allow-list is a valid answer meaning "conversational persona,
        no tools": `filtered=[]` — the endpoint's `if specs:` gate then flips
        `tools=None`. Provider-agnostic: operates on the spec list + the
        execute callable, so it behaves identically for the non-streaming
        bound registry and the streaming factory registry.
        """
        if self._agent.tool_names is None:
            return specs, executor

        allowed = set(self._agent.tool_names)
        filtered = [s for s in specs if s["name"] in allowed]

        async def _wrapped(call: ToolCall) -> ToolResult:
            if call.name not in allowed:
                return ToolResult(
                    tool_call_id=call.id,
                    content=f"tool not permitted for this agent: {call.name}",
                    is_error=True,
                )
            return await executor(call)

        return filtered, _wrapped
