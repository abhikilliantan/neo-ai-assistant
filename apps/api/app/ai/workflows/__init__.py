"""Workflow client + registry builders — config-driven selection.

Mirrors `app/ai/providers/__init__.py` (build_chat_provider) and
`app/ai/agents/__init__.py` (build_agent_registry):

  - `build_workflow_client(settings)` selects the concrete client from
    `settings.workflow_client`. "mock" is the CI/test default; "n8n" (7c)
    returns the real webhook client, failing fast if its config is missing.
  - `build_workflow_registry(settings)` pins the built-in workflow definitions
    onto a fresh registry at startup. `_built_in_workflows()` names the set in
    exactly one place.

Nothing consumes either of these yet — 7a is the contract/registry/mock slice;
7b wires workflows into the tool loop (WORKFLOWS ARE TOOLS).
"""

from __future__ import annotations

import httpx

from app.ai.workflows.mock import MockWorkflowClient
from app.ai.workflows.n8n import N8nWorkflowClient
from app.ai.workflows.registry import WorkflowRegistry
from app.application.ports.workflows import WorkflowClient, WorkflowDefinition
from app.infrastructure.config import Settings


def _built_in_workflows() -> list[WorkflowDefinition]:
    """Baseline workflow set — defined in exactly one place.

    `create_task` is a deliberately-honest PLACEHOLDER so the registry isn't
    empty and 7b has something to call. It is not backed by a real n8n
    workflow yet; real workflows replace/join it once the n8n client (7c)
    exists. `input_schema` is Anthropic tool-input-schema shape verbatim.
    """
    return [
        WorkflowDefinition(
            name="create_task",
            description=(
                "Create a task in the connected task tracker. "
                "(Placeholder demo workflow — not backed by a real n8n "
                "workflow until 7c.)"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title of the task to create.",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "ISO-8601 date the task is due (optional).",
                    },
                },
                "required": ["title"],
            },
        ),
    ]


def build_workflow_client(settings: Settings) -> WorkflowClient:
    """Wire the concrete WorkflowClient based on settings.workflow_client.

    Fail-fast on the unknown branch, same posture as build_chat_provider —
    never silently fall back to the mock, which would mask a config error.
    """
    if settings.workflow_client == "mock":
        return MockWorkflowClient()
    if settings.workflow_client == "n8n":
        # Fail fast on missing config — never silently fall back to mock, which
        # would make a misconfigured prod look healthy. The message names the
        # env vars, NEVER the token value.
        if not settings.n8n_base_url or not settings.n8n_auth_token:
            raise RuntimeError(
                "WORKFLOW_CLIENT=n8n requires N8N_BASE_URL and N8N_AUTH_TOKEN to be set"
            )
        # ONE long-lived pooled client. The token lives ONLY as a default
        # header here — never formatted into a URL, log, or returned string.
        # follow_redirects=False is LOAD-BEARING for the SSRF guard (7f-1): a
        # permitted public URL that 302s to the metadata endpoint would defeat
        # it entirely. httpx defaults to False; we set it explicitly so nobody
        # flips it, and a test asserts it.
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.n8n_timeout_seconds),
            headers={"Authorization": f"Bearer {settings.n8n_auth_token}"},
            follow_redirects=False,
        )
        return N8nWorkflowClient(
            client=http_client,
            base_url=settings.n8n_base_url,
            timeout_seconds=settings.n8n_timeout_seconds,
            allowlist=settings.n8n_allowed_hosts_list,
        )
    raise RuntimeError(f"Unknown WORKFLOW_CLIENT: {settings.workflow_client!r}")


def build_workflow_registry(settings: Settings) -> WorkflowRegistry:
    """Startup registry — built once, pinned on `app.state.workflow_registry`.

    `workflows_enabled` is intentionally NOT consulted here: like
    `tools_enabled` for build_tool_registry, the kill switch is a route-level
    gate (7b), not a registry-contents gate. The registry is always fully
    seeded; 7b withholds the specs/executor when the switch is off.
    """
    del settings  # unused; parity with build_tool_registry / build_agent_registry
    registry = WorkflowRegistry()
    for workflow in _built_in_workflows():
        registry.register(workflow)
    return registry


__all__ = [
    "MockWorkflowClient",
    "N8nWorkflowClient",
    "WorkflowRegistry",
    "build_workflow_client",
    "build_workflow_registry",
]
