"""Agent definitions + startup registry builder.

Mirror of `app/ai/tools/__init__.py` shape: `_built_in_agents()` names the
baseline set in one place; `build_agent_registry(settings)` pins them onto
a fresh registry at startup. Nothing consumes this registry yet — 6f is the
contract-and-registry slice; 6g wires it into `/chat` + `/chat/stream`.

The default "assistant" agent now carries a GROUNDING system prompt
(anti-confabulation guardrails): answer questions about the user's own data only
from tool results / context, cite sources, admit uncertainty, and never invent
metrics about its own processing. This deliberately ends the earlier
"byte-for-byte compatible / no persona injected" posture — grounding on the
common chat path is worth the behavior change.

Distinct personas / tool subsets arrive as later opt-in agents; they do not
belong in this slice.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.ai.agents.registry import AgentRegistry
from app.ai.agents.runner import DEFAULT_AGENT_NAME, AgentRunner
from app.ai.tools import READ_ONLY_TOOL_NAMES
from app.application.ports.agents import AgentDefinition
from app.infrastructure.config import Settings


def _built_in_agents(*, workflow_names: Iterable[str]) -> list[AgentDefinition]:
    """Baseline agent set — defined in exactly one place.

    7d — permissions by classification. The tool sets are DERIVED, not
    hand-listed, so they stay correct as tools/workflows grow:
      - "assistant" (default): the READ-ONLY tools only. It moved OFF
        tool_names=None (which now means "everything incl. side effects") so a
        plain chat can never fire a side-effecting workflow without opt-in.
      - "operator": read-only tools PLUS every workflow name — the ONLY agent
        that can take external actions. Selecting it in the picker IS the
        user's consent, so its description reads like a consent prompt.
      - "recall" (6h): a deliberately narrow read persona (search only).
    """
    read_only = sorted(READ_ONLY_TOOL_NAMES)
    workflows = sorted(workflow_names)
    return [
        AgentDefinition(
            name="assistant",
            description=(
                "General-purpose assistant — answers questions and searches your "
                "memories. Read-only: never changes anything in external systems."
            ),
            # Grounding guardrails (anti-confabulation). This agent is the default
            # for every plain chat, so these rules govern the common path.
            system_prompt=(
                "You are Neo, a helpful assistant.\n\n"
                "GROUNDING. When answering questions about the user's own documents, "
                "uploaded files, or saved data, use ONLY what the `search_documents` "
                "and `search_memory` tools return, or content already present in this "
                "conversation. If such a question is not already covered, search first. "
                "If the search returns nothing relevant, say \"I don't have that "
                "information\" — do NOT answer from general knowledge about the user's "
                "own documents, files, or organization. (General-knowledge questions "
                "unrelated to the user's data — definitions, how-tos, world facts — you "
                "may answer normally.)\n\n"
                "CITING SOURCES. When you use a document excerpt, cite the filename and "
                "the page or section exactly as the tool result gives them, including "
                'any "(OCR)" marker.\n\n'
                "ADMITTING UNCERTAINTY. If you don't have the information, say so plainly "
                "rather than guessing.\n\n"
                "NO INVENTED METRICS. You have no visibility into system internals, "
                "processing statistics, timings, confidence scores, page counts, or chunk "
                "counts. Never report metrics, percentages, or numbers about your own "
                "processing or about a document unless they appear verbatim in a tool "
                "result. If asked for such data, say you don't have access to it."
            ),
            tool_names=read_only,
        ),
        AgentDefinition(
            name="recall",
            description="Answers from what you've told Neo before.",
            system_prompt=(
                "You are Neo's recall specialist. Before answering, search the "
                "user's saved memories and ground your answer in what you find. "
                "If nothing relevant is stored, say so plainly rather than guessing."
            ),
            tool_names=["search_memory"],
        ),
        AgentDefinition(
            name="operator",
            description=(
                "Takes actions in your connected systems — can create tasks and "
                "run workflows that change external tools, not just answer. Choose "
                "this when you want Neo to DO things on your behalf."
            ),
            system_prompt=(
                "You are Neo in operator mode. Alongside answering, you can take "
                "real actions in the user's connected systems by running workflows "
                "(for example, creating a task). Run a workflow only when the user "
                "clearly wants that action taken; if the request is ambiguous, ask "
                "first. Prefer read-only tools when only information is needed."
            ),
            tool_names=read_only + workflows,
        ),
    ]


def agent_for_request(
    agent: AgentDefinition,
    *,
    builtin_workflow_names: frozenset[str],
    request_workflow_names: frozenset[str],
) -> AgentDefinition:
    """Expand a workflow-capable agent's allow-list with the PER-REQUEST
    workflow names (built-in + this tenant's rows), so 7f-2's per-request specs
    and per-request permissions stay in lockstep (7d built operator's list once
    at startup — it flagged this itself).

    An agent is "workflow-capable" iff it already permits the built-in
    workflows — only `operator` does. Read-only agents (assistant, recall) are
    returned UNCHANGED, so 7d's safety boundary holds for tenant rows too:
    tenant data can never escalate a read-only agent into taking actions.
    """
    if agent.tool_names is None:
        return agent
    allowed = set(agent.tool_names)
    # `builtin_workflow_names` non-empty guards the vacuous-subset case: with no
    # built-in workflows, `<= allowed` would be true for every agent.
    if builtin_workflow_names and builtin_workflow_names <= allowed:
        return agent.model_copy(update={"tool_names": sorted(allowed | request_workflow_names)})
    return agent


def build_agent_registry(settings: Settings, *, workflow_names: Iterable[str]) -> AgentRegistry:
    """Startup registry — built once, pinned on `app.state.agent_registry`.

    `workflow_names` (the current workflow registry's names) is REQUIRED: the
    "operator" agent's permissions derive from it, so the caller MUST pass the
    live set — forgetting is a TypeError, not a silently powerless operator.
    """
    del settings  # unused; kept for parity with build_tool_registry / build_chat_provider
    names = set(workflow_names)
    # Defense-in-depth (7b's merge already blocks a workflow named like a tool):
    # a workflow colliding with a read-only name would make operator's allow-list
    # ambiguous. Refuse to build.
    overlap = sorted(READ_ONLY_TOOL_NAMES & names)
    if overlap:
        raise RuntimeError(f"workflow name(s) {overlap} collide with read-only tool names")
    registry = AgentRegistry()
    for agent in _built_in_agents(workflow_names=names):
        registry.register(agent)
    return registry


__all__ = [
    "DEFAULT_AGENT_NAME",
    "AgentRegistry",
    "AgentRunner",
    "agent_for_request",
    "build_agent_registry",
]
