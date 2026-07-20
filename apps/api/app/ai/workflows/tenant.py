"""Per-request resolution of tenant-defined workflows (Phase 7f-2).

The request-scoped workflow set = built-in workflows + this tenant's enabled,
non-deleted rows. Built-ins keep working exactly as today for every tenant.

⚠️ SECURITY GATE (locked): tenant workflow URLs resolve against a NON-EMPTY
admin allowlist. If `settings.n8n_allowed_hosts` is empty, tenant workflows are
DISABLED ENTIRELY (fail closed) — built-ins unaffected. Reason: 7f-1's guard
accepts DNS rebinding as a residual, fully open in deny-by-range mode; tolerable
for code-owned URLs, NOT for tenant-supplied ones.

⚠️ A BAD TENANT ROW MUST NOT BREAK CHAT. Unlike 7b's build-time ValueError for
code-owned collisions (a developer bug → fail loud), a tenant row is DATA and
degrades gracefully: a row that collides with a built-in name, has a URL failing
the allowlist/SSRF guard, or is malformed is SKIPPED with a warning (naming the
row + a reason CATEGORY, never a resolved IP), and the remaining workflows still
serve. We pre-dedupe here so the downstream registry the tool builder sees is
always collision-free — the builder's raise never fires on tenant data.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import text

from app.ai.tools import READ_ONLY_TOOL_NAMES
from app.ai.workflows.registry import WorkflowRegistry
from app.ai.workflows.urlguard import Resolver, UrlNotAllowedError, validate_workflow_url
from app.application.ports.workflows import WorkflowDefinition
from app.infrastructure.config import Settings
from app.infrastructure.db import Database
from app.infrastructure.db.repositories import WorkflowRepository
from app.infrastructure.logging import get_logger


async def resolve_request_workflows(
    *,
    db: Database,
    tenant_id: UUID,
    builtin_registry: WorkflowRegistry,
    settings: Settings,
    resolve: Resolver,
) -> tuple[WorkflowRegistry, dict[str, str]]:
    """Return (per-request WorkflowRegistry, tenant name→URL overrides).

    The registry is always seeded with built-ins. Tenant rows are added ONLY
    when workflows are enabled AND the allowlist is non-empty (fail closed).
    """
    registry = WorkflowRegistry()
    for definition in builtin_registry.definitions():
        registry.register(definition)
    url_overrides: dict[str, str] = {}

    # Kill switch + fail-closed gate: no tenant rows unless BOTH hold. When
    # workflows are disabled the tool builder drops all workflows anyway; when
    # the allowlist is empty, tenant workflows are disabled entirely.
    allowlist = settings.n8n_allowed_hosts_list
    if not settings.workflows_enabled or not allowlist:
        return registry, url_overrides

    async with db.sessionmaker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)").bindparams(t=str(tenant_id))
        )
        rows = await WorkflowRepository(session).list_enabled_for_org(tenant_id)

    log = get_logger("workflow.row")
    # Reserved = every built-in tool AND workflow name. A tenant row colliding
    # with any of these would silently reroute the model → skip it.
    reserved = set(READ_ONLY_TOOL_NAMES) | set(registry.list_names())

    for row in rows:
        if row.name in reserved:
            log.warning(
                "workflow.row.skipped", row_id=str(row.id), name=row.name, reason="name_collision"
            )
            continue

        try:
            definition = WorkflowDefinition(
                name=row.name,
                description=row.description,
                input_schema=row.input_schema,
            )
        except Exception:  # any malformed row is skipped, never fatal to chat
            log.warning(
                "workflow.row.skipped", row_id=str(row.id), name=row.name, reason="malformed"
            )
            continue

        # Defense in depth: validate the URL against the SSRF guard + allowlist
        # on EVERY request (rows can be edited out-of-band, the allowlist can
        # change, DNS moves). Blocking getaddrinfo → run it off the loop.
        try:
            await asyncio.to_thread(
                validate_workflow_url,
                row.webhook_url,
                resolve=resolve,
                allowlist=allowlist,
            )
        except UrlNotAllowedError:
            log.warning(
                "workflow.row.skipped", row_id=str(row.id), name=row.name, reason="url_blocked"
            )
            continue

        registry.register(definition)  # collision-free by construction (reserved check)
        reserved.add(row.name)  # a later row with the same name is a dup → skip
        url_overrides[row.name] = row.webhook_url

    return registry, url_overrides
