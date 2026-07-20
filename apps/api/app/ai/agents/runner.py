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
from app.infrastructure.logging import get_logger

DEFAULT_AGENT_NAME = "assistant"


class AgentRunner:
    def __init__(
        self,
        agent: AgentDefinition,
        *,
        workflow_names: frozenset[str] = frozenset(),
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> None:
        self._agent = agent
        # 7d: names the runner treats as side-effecting for AUDIT purposes.
        # Empty by default so existing (workflow-free) callers are unchanged.
        self._workflow_names = workflow_names
        # 7d: the ACTOR is recorded EXPLICITLY on the audit line — the whole
        # point of the trail is "who told the system to take this action". We do
        # NOT rely on structlog contextvars for it: they don't survive into the
        # /chat/stream response generator's task, and are invisible to
        # capture_logs in tests. Explicit fields are robust on both paths.
        self._user_id = user_id
        self._org_id = org_id

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

        7d: the executor is ALWAYS audit-wrapped (even on the None path) so a
        side-effecting WORKFLOW invocation is logged wherever it happens.
        """
        audited = self._audit_workflow_calls(executor)

        if self._agent.tool_names is None:
            return specs, audited

        allowed = set(self._agent.tool_names)
        filtered = [s for s in specs if s["name"] in allowed]

        async def _wrapped(call: ToolCall) -> ToolResult:
            if call.name not in allowed:
                if call.name in self._workflow_names:
                    # A workflow the model tried to invoke without this agent's
                    # consent-granting selection. The guardrail engaged — audit it.
                    get_logger("workflow.audit").warning(
                        "workflow.blocked",
                        agent=self._agent.name,
                        workflow=call.name,
                        user_id=self._user_id,
                        org_id=self._org_id,
                    )
                return ToolResult(
                    tool_call_id=call.id,
                    content=f"tool not permitted for this agent: {call.name}",
                    is_error=True,
                )
            return await audited(call)

        return filtered, _wrapped

    def _audit_workflow_calls(self, executor: ToolExecutor) -> ToolExecutor:
        """Wrap `executor` to log an INFO audit line for each WORKFLOW (not
        plain tool) invocation. No-op when the agent knows of no workflows, so
        read-only paths are unchanged. NEVER logs arguments (7a flag #4) — the
        user_id / org / request_id are carried by structlog contextvars.
        """
        if not self._workflow_names:
            return executor
        workflow_names = self._workflow_names
        agent_name = self._agent.name
        user_id = self._user_id
        org_id = self._org_id

        async def _audited(call: ToolCall) -> ToolResult:
            result = await executor(call)
            if call.name in workflow_names:
                get_logger("workflow.audit").info(
                    "workflow.invoked",
                    agent=agent_name,
                    workflow=call.name,
                    ok=not result.is_error,
                    user_id=user_id,
                    org_id=org_id,
                )
            return result

        return _audited
