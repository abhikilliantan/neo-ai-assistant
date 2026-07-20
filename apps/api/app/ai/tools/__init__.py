"""Tool adapters + registry builders (startup + per-request + streaming).

Three builders because tools split into three registry lifetimes:
  - **Stateless baseline** (built once at startup, safe to share across all
    requests): EchoTool. Pinned onto `app.state.tool_registry` by main.py.
  - **Request-scoped** (need per-caller state — a bound tenant session,
    user_id): built fresh inside the /chat handler via
    `build_request_tool_registry`. Non-streaming path — the /chat handler
    already holds a tenant session for the whole request, so search_memory
    binds to it directly.
  - **Streaming request-scoped**: built inside /chat/stream. The stream
    path deliberately does NOT hold a DB session across the LLM response,
    so search_memory receives a `MemoryRepoFactory` that opens a SHORT
    tenant session per tool call (matching the 5d retrieval discipline).
    `build_streaming_request_tool_registry` is the entry point.

The builders share `_stateless_tools()` so the baseline set is defined in
exactly one place and can never drift across registry variants.

Why per-request rather than mutating the startup registry: the singleton is
shared by every concurrent request. Mutating it with a caller-bound tool
would race — request A's search_memory could bind to request B's user_id
between the register + execute steps. A per-request registry is the natural
scope for anything holding session or identity state.
"""

from __future__ import annotations

from uuid import UUID

from app.ai.tools.echo import EchoTool
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.search_memory import MemoryRepoFactory, SearchMemoryTool
from app.ai.tools.workflow import WorkflowTool
from app.ai.workflows.registry import WorkflowRegistry
from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.repositories import MemoryRepositoryPort
from app.application.ports.tools import Tool
from app.application.ports.workflows import WorkflowClient
from app.infrastructure.config import Settings


def _stateless_tools() -> list[Tool]:
    """Tools with no per-caller state. Safe to share process-wide."""
    return [EchoTool()]


# 7d: the SINGLE source of truth for which tools are READ-ONLY (no external
# side effect). Built-in agents derive their allow-lists from this set plus the
# workflow registry (workflows are the side-effecting set by construction), so:
#   - a new READ-ONLY tool must be named here, or `_assert_all_tools_classified`
#     raises at build time — it can never silently fail to reach the read agents;
#   - a new WORKFLOW reaches ONLY the workflow-capable agent (operator), never
#     the default read-only agent, with no edit here.
# Keep this in lockstep with what the request builders register below.
READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset({"echo", "search_memory"})


def _assert_all_tools_classified(
    registry: ToolRegistry, workflow_registry: WorkflowRegistry
) -> None:
    """Fail loudly if a registered tool is neither classified read-only nor a
    workflow (7d). 7d agents derive their permissions from this split, so an
    unclassified tool would silently reach the wrong agents — refuse to build.
    """
    classified = READ_ONLY_TOOL_NAMES | set(workflow_registry.list_names())
    unknown = sorted({spec["name"] for spec in registry.specs()} - classified)
    if unknown:
        raise RuntimeError(
            f"unclassified tool(s) {unknown}: add to READ_ONLY_TOOL_NAMES "
            "(app/ai/tools) or register as a workflow. 7d built-in agents derive "
            "their allow-lists from this classification."
        )


def _merge_workflow_tools(
    registry: ToolRegistry,
    workflow_registry: WorkflowRegistry,
    workflow_client: WorkflowClient,
) -> None:
    """Merge workflow definitions into `registry` as WorkflowTools (7b).

    COLLISION CHECK (7a flag #1 — the important one). `ToolRegistry.register`
    OVERWRITES silently, so a workflow whose name already exists as a tool
    (e.g. a workflow named `search_memory`) would silently reroute the model.
    We refuse: a name collision is a BUILD-TIME `ValueError`, raised here —
    inside the per-request registry build, which every request runs BEFORE the
    provider call — so it can never surface mid-conversation, and it fires
    deterministically on the first request in any environment (incl. CI).

    Chosen over namespace prefixes (`workflow__create_task`): prefixes leak
    implementation structure into the prompt the model reads and degrade its
    tool choice — tool names should read like capabilities, not plumbing.

    Note: the per-request builder is the ONLY place tools and workflows fully
    coexist (search_memory is added per request, not at startup), so it is the
    only complete surface for this check.
    """
    for definition in workflow_registry.definitions():
        if registry.get(definition.name) is not None:
            raise ValueError(f"workflow name collides with an existing tool: {definition.name!r}")
        registry.register(WorkflowTool(definition=definition, client=workflow_client))


def build_tool_registry(settings: Settings) -> ToolRegistry:
    """Startup registry — stateless baseline only. Pinned onto app.state."""
    del settings  # unused; kept for signature parity with 3a/5a/5c/5d
    registry = ToolRegistry()
    for tool in _stateless_tools():
        registry.register(tool)
    return registry


def build_request_tool_registry(
    *,
    settings: Settings,
    memory_repo: MemoryRepositoryPort,
    embedding_provider: EmbeddingProvider,
    organization_id: UUID,
    user_id: UUID,
) -> ToolRegistry:
    """Per-request registry (non-streaming /chat): baseline + tools bound to
    the caller's already-open tenant session.

    Called from /chat with the current request's tenant-scoped MemoryRepository,
    the embedding provider, and the resolved (org, user). Never mutates the
    startup registry — a fresh instance every time.
    """
    del settings  # unused for 6c; future TOOLS_* toggles slot in without churn
    registry = ToolRegistry()
    for tool in _stateless_tools():
        registry.register(tool)
    registry.register(
        SearchMemoryTool(
            memory_repo=memory_repo,
            embedding_provider=embedding_provider,
            organization_id=organization_id,
            user_id=user_id,
        )
    )
    return registry


def build_streaming_request_tool_registry(
    *,
    settings: Settings,
    memory_repo_factory: MemoryRepoFactory,
    embedding_provider: EmbeddingProvider,
    organization_id: UUID,
    user_id: UUID,
    workflow_registry: WorkflowRegistry,
    workflow_client: WorkflowClient,
) -> ToolRegistry:
    """Per-request registry for BOTH /chat and /chat/stream: baseline + tools
    bound to a SHORT-per-call session factory rather than a live request
    session, plus workflows-as-tools (7b).

    Both endpoints avoid holding a DB connection across the LLM response.
    search_memory therefore receives a factory that opens a fresh tenant
    session per invocation (set GUC → search → close), so tool-driven DB
    access remains RLS-scoped without pinning the pool.

    Workflows (7b): when `settings.workflows_enabled` is true, every registered
    WorkflowDefinition is merged in as a WorkflowTool via `_merge_workflow_
    tools` (with its build-time collision check). When false, NO workflow specs
    are added — the tool set is echo + search_memory only. The outer
    `tools_enabled` switch is applied by the caller (both endpoints skip this
    builder entirely when tools_enabled is false), so the two switches compose:
    tools_enabled=false → no specs at all; workflows_enabled=false → tools but
    no workflows.
    """
    registry = ToolRegistry()
    for tool in _stateless_tools():
        registry.register(tool)
    registry.register(
        SearchMemoryTool(
            memory_repo_factory=memory_repo_factory,
            embedding_provider=embedding_provider,
            organization_id=organization_id,
            user_id=user_id,
        )
    )
    if settings.workflows_enabled:
        _merge_workflow_tools(registry, workflow_registry, workflow_client)
    # 7d: every tool that reaches the model must be classified (read-only or
    # workflow) so the built-in agents' permissions stay correct as tools grow.
    _assert_all_tools_classified(registry, workflow_registry)
    return registry


__all__ = [
    "READ_ONLY_TOOL_NAMES",
    "EchoTool",
    "MemoryRepoFactory",
    "SearchMemoryTool",
    "ToolRegistry",
    "WorkflowTool",
    "build_request_tool_registry",
    "build_streaming_request_tool_registry",
    "build_tool_registry",
]
