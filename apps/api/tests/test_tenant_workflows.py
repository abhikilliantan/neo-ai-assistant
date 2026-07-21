"""Phase 7f-2 — tenant-defined workflows (READ path), DB-backed against the
REAL migration. Mocks pinned; no real network/DNS (conftest injects an offline
resolver). RLS is proven adversarially through HTTP, not just the repository.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
import structlog.testing
from httpx import ASGITransport, AsyncClient

from app.application.ports.chat import ChatCompletion, ChatStreamEvent, ToolExecutor
from app.application.ports.tools import ToolCall
from app.infrastructure.db.models import Workflow

WF_HOST = "wf.example.test"
ALLOWLIST = WF_HOST  # non-empty → tenant workflows enabled (fail-closed gate open)


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _seed_workflow(
    app_session_factory: Any,
    *,
    tenant_id: UUID,
    name: str,
    webhook_url: str | None = None,
    input_schema: Any = None,
    enabled: bool = True,
    deleted: bool = False,
) -> None:
    s = await app_session_factory(tenant_id)  # sets app.current_tenant GUC
    try:
        wf = Workflow(
            organization_id=tenant_id,
            name=name,
            description=f"{name} does a thing",
            input_schema=input_schema if input_schema is not None else {"type": "object"},
            webhook_url=webhook_url or f"https://{WF_HOST}/hook/{name}",
            enabled=enabled,
        )
        if deleted:
            wf.deleted_at = datetime.now(UTC)
        s.add(wf)
        await s.commit()
    finally:
        await s.close()


def _enable_tenant_workflows(db_app: Any, allowlist: str = ALLOWLIST) -> None:
    db_app.state.settings = db_app.state.settings.model_copy(
        update={"n8n_allowed_hosts": allowlist}
    )


# --- providers --------------------------------------------------------------


class _RecordingProvider:
    """Records the (post-filter) tool specs the endpoint hands the provider."""

    def __init__(self) -> None:
        self.tools_seen: list[list[dict[str, Any]] | None] = []

    async def complete(
        self, *, tools: list[dict[str, Any]] | None = None, **_: object
    ) -> ChatCompletion:
        self.tools_seen.append(tools)
        return ChatCompletion(content="ok", model="rec", usage=None, finish_reason="stop")

    async def stream(
        self, *, tools: list[dict[str, Any]] | None = None, **_: object
    ) -> AsyncIterator[ChatStreamEvent]:
        self.tools_seen.append(tools)
        yield ChatStreamEvent(type="done", model="rec", finish_reason="stop")


class _CallingProvider:
    """Invokes one named tool via the executor and folds the outcome into the
    reply, so a test can see whether the call succeeded or was blocked.
    """

    def __init__(self, tool_name: str) -> None:
        self._tool_name = tool_name

    async def complete(
        self, *, tool_executor: ToolExecutor | None = None, **_: object
    ) -> ChatCompletion:
        assert tool_executor is not None
        result = await tool_executor(ToolCall(id="c", name=self._tool_name, arguments={"x": 1}))
        return ChatCompletion(
            content=f"[ok={not result.is_error}] {result.content}",
            model="scripted",
            usage=None,
            finish_reason="stop",
        )

    async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:  # pragma: no cover
        raise NotImplementedError
        yield


async def _tool_names(
    db_app: Any, *, token: str, path: str = "/api/v1/chat", agent: str | None = "operator"
) -> set[str]:
    spy = _RecordingProvider()
    db_app.state.chat_provider = spy
    payload: dict[str, Any] = {"messages": [{"role": "user", "content": "hi"}]}
    if agent is not None:
        payload["agent"] = agent
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(path, headers={"Authorization": f"Bearer {token}"}, json=payload)
        assert r.status_code == 200, r.text
        if path.endswith("/stream"):
            _ = r.text
    return {s["name"] for s in (spy.tools_seen[-1] or [])}


# --- cross-tenant isolation (the load-bearing one) --------------------------


@pytest.mark.asyncio
async def test_cross_tenant_isolation_via_http(db_app, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    _enable_tenant_workflows(db_app)
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        a = await _register(c, "7f2-iso-a@example.com")
        b = await _register(c, "7f2-iso-b@example.com")
    a_tenant = UUID(a["active_tenant_id"])
    await _seed_workflow(app_session_factory, tenant_id=a_tenant, name="a_secret_wf")

    # A sees it; B does not — RLS at the read layer.
    a_names = await _tool_names(db_app, token=a["access_token"])
    b_names = await _tool_names(db_app, token=b["access_token"])
    assert "a_secret_wf" in a_names
    assert "a_secret_wf" not in b_names

    # B cannot invoke it even by guessing the name — executor blocks it.
    db_app.state.chat_provider = _CallingProvider("a_secret_wf")
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {b['access_token']}"},
            json={"agent": "operator", "messages": [{"role": "user", "content": "run it"}]},
        )
    assert r.status_code == 200, r.text
    assert "[ok=False]" in r.json()["message"]["content"]


# --- enabled row visible + callable on BOTH endpoints -----------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/chat", "/api/v1/chat/stream"])
async def test_enabled_row_appears_in_specs_both_endpoints(
    db_app, app_session_factory, path
) -> None:  # type: ignore[no-untyped-def]
    _enable_tenant_workflows(db_app)
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, f"7f2-vis-{len(path)}@example.com")
    await _seed_workflow(
        app_session_factory, tenant_id=UUID(reg["active_tenant_id"]), name="send_alert"
    )
    names = await _tool_names(db_app, token=reg["access_token"], path=path)
    assert "send_alert" in names
    assert {"echo", "search_memory", "create_task"} <= names  # built-ins still present


@pytest.mark.asyncio
async def test_enabled_row_is_callable_by_operator(db_app, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    _enable_tenant_workflows(db_app)
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "7f2-call@example.com")
    await _seed_workflow(
        app_session_factory, tenant_id=UUID(reg["active_tenant_id"]), name="ship_it"
    )

    db_app.state.chat_provider = _CallingProvider("ship_it")
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {reg['access_token']}"},
            json={"agent": "operator", "messages": [{"role": "user", "content": "go"}]},
        )
    assert r.status_code == 200, r.text
    # Mock workflow client returns ok → executor result is_error False.
    assert "[ok=True]" in r.json()["message"]["content"]


# --- disabled / soft-deleted absent -----------------------------------------


@pytest.mark.asyncio
async def test_disabled_and_soft_deleted_rows_are_absent(db_app, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    _enable_tenant_workflows(db_app)
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "7f2-off@example.com")
    tenant = UUID(reg["active_tenant_id"])
    await _seed_workflow(app_session_factory, tenant_id=tenant, name="disabled_wf", enabled=False)
    await _seed_workflow(app_session_factory, tenant_id=tenant, name="deleted_wf", deleted=True)
    await _seed_workflow(app_session_factory, tenant_id=tenant, name="live_wf")

    names = await _tool_names(db_app, token=reg["access_token"])
    assert "live_wf" in names
    assert "disabled_wf" not in names
    assert "deleted_wf" not in names


# --- bad-row resilience: skip + warn, others still work, chat 200 -----------


@pytest.mark.asyncio
async def test_bad_rows_are_skipped_with_warning_chat_still_serves(
    db_app, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    _enable_tenant_workflows(db_app)
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "7f2-bad@example.com")
    tenant = UUID(reg["active_tenant_id"])
    # (a) name collides with a built-in workflow
    await _seed_workflow(app_session_factory, tenant_id=tenant, name="create_task")
    # (b) URL host not on the allowlist
    await _seed_workflow(
        app_session_factory, tenant_id=tenant, name="exfil", webhook_url="https://evil.example/hook"
    )
    # (c) malformed input_schema (a list, not an object)
    await _seed_workflow(
        app_session_factory, tenant_id=tenant, name="malformed", input_schema=["nope"]
    )
    # a good one survives
    await _seed_workflow(app_session_factory, tenant_id=tenant, name="good_wf")

    with structlog.testing.capture_logs() as logs:
        names = await _tool_names(db_app, token=reg["access_token"])

    assert "good_wf" in names  # other workflows keep working
    assert "exfil" not in names
    assert "malformed" not in names
    # built-in create_task still present (the colliding tenant row was dropped,
    # not the built-in), and chat returned 200 (asserted inside _tool_names).
    assert "create_task" in names

    skips = [e for e in logs if e.get("event") == "workflow.row.skipped"]
    reasons = {e["reason"] for e in skips}
    assert reasons == {"name_collision", "url_blocked", "malformed"}
    assert all("name" in e and "row_id" in e for e in skips)  # names the row


# --- fail-closed: empty allowlist disables tenant workflows -----------------


@pytest.mark.asyncio
async def test_empty_allowlist_disables_tenant_workflows_builtins_unaffected(
    db_app, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    # NOTE: db_app default n8n_allowed_hosts is "" — fail closed.
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "7f2-failclosed@example.com")
    await _seed_workflow(
        app_session_factory, tenant_id=UUID(reg["active_tenant_id"]), name="tenant_wf"
    )

    names = await _tool_names(db_app, token=reg["access_token"])
    assert "tenant_wf" not in names  # disabled entirely
    assert "create_task" in names  # built-in unaffected


# --- permission boundary: operator gets them, default agent never -----------


@pytest.mark.asyncio
async def test_default_agent_never_gets_tenant_workflows(db_app, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    _enable_tenant_workflows(db_app)
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "7f2-perm@example.com")
    await _seed_workflow(
        app_session_factory, tenant_id=UUID(reg["active_tenant_id"]), name="tenant_action"
    )

    operator_names = await _tool_names(db_app, token=reg["access_token"], agent="operator")
    default_names = await _tool_names(db_app, token=reg["access_token"], agent=None)

    assert "tenant_action" in operator_names  # per-request permission granted
    assert "tenant_action" not in default_names  # 7d boundary holds for tenant data
    assert default_names == {
        "echo",
        "search_memory",
        "search_documents",
    }  # read-only, no workflows at all
