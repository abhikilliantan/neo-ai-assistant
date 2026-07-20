"""Phase 7c — real n8n webhook workflow client.

First Phase 7 slice that touches the network — so EVERY test here injects an
httpx.MockTransport; NONE hits a live URL or requires a running n8n. Covers:

  - 2xx JSON -> ok=True, deterministically serialized (sorted keys).
  - 2xx plain text -> ok=True, text passed through.
  - non-2xx -> ok=False status marker; end-to-end via WorkflowTool + registry
    it reaches the model as is_error=True, and the raw body is NEVER surfaced
    or logged.
  - timeout / transport error -> ok=False marker, is_error=True (never a 500).
  - auth header sent + URL derived by convention.
  - SECURITY: the token never appears in any log record, output, or exception
    on a failing call (the load-bearing test of the slice).
  - build_workflow_client: n8n complete -> N8nWorkflowClient; n8n missing
    config -> RuntimeError at build time; mock -> mock.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import structlog.testing

from app.ai.tools import ToolRegistry, WorkflowTool
from app.ai.workflows import (
    MockWorkflowClient,
    N8nWorkflowClient,
    build_workflow_client,
)
from app.application.ports.tools import ToolCall
from app.application.ports.workflows import WorkflowDefinition
from app.infrastructure.config import Settings

# A distinctive token so "token must never be logged" assertions are meaningful.
TOKEN = "n8n-secret-tok-DO-NOT-LOG-abc123"
BASE = "https://n8n.example.test"


def _offline_resolver(host: str) -> list[str]:
    """7f-1: the client now runs the SSRF guard, which resolves the host. Inject
    an OFFLINE resolver so these tests never touch real DNS — the code-owned
    BASE host resolves to a public IP and sails through the guard, leaving 7c
    behavior unchanged.
    """
    return ["93.184.216.34"]  # public


def _base(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {
        "python_env": "test",
        "database_url": "postgresql+asyncpg://x/x",
        "app_database_url": "postgresql+asyncpg://x/x",
        "redis_url": "redis://x",
        "jwt_secret_key": "test-secret-key-at-least-32-bytes-long-xxxxx",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


def _wf_def(name: str = "create_task") -> WorkflowDefinition:
    return WorkflowDefinition(
        name=name,
        description="Create a task.",
        input_schema={"type": "object", "properties": {}, "required": []},
    )


def _client(handler: Any, *, token: str = TOKEN, timeout: float = 10.0) -> N8nWorkflowClient:
    """N8nWorkflowClient wired to a MockTransport — the auth header is set on
    the injected httpx client exactly as build_workflow_client would.
    """
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(timeout),
    )
    return N8nWorkflowClient(
        client=http, base_url=BASE, timeout_seconds=timeout, resolve=_offline_resolver
    )


# --- happy paths ------------------------------------------------------------


@pytest.mark.asyncio
async def test_2xx_json_serialized_with_sorted_keys() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"z": 1, "a": 2})

    run = await _client(handler).run(name="create_task", arguments={"title": "t"})
    assert run.ok is True
    # Deterministic regardless of the response's key order.
    assert run.output == json.dumps({"a": 2, "z": 1}, sort_keys=True)


@pytest.mark.asyncio
async def test_2xx_plain_text_passed_through() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="plain result")

    run = await _client(handler).run(name="create_task", arguments={})
    assert run.ok is True
    assert run.output == "plain result"


# --- failure paths (end-to-end through the registry catch) ------------------


@pytest.mark.asyncio
async def test_non_2xx_reaches_model_as_is_error_and_body_is_discarded() -> None:
    secret_body = "CUSTOMER RECORD ssn=123-45-6789"

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=secret_body)

    reg = ToolRegistry()
    reg.register(WorkflowTool(definition=_wf_def(), client=_client(handler)))

    with structlog.testing.capture_logs() as logs:
        result = await reg.execute(ToolCall(id="x1", name="create_task", arguments={"title": "t"}))

    # Reaches the model as an error with a status marker only.
    assert result.is_error is True
    assert result.content == "workflow 'create_task' failed with HTTP 500"
    # The unaudited n8n body never reaches the model NOR the logs.
    assert secret_body not in result.content
    assert secret_body not in repr(logs)


@pytest.mark.asyncio
async def test_timeout_reaches_model_as_is_error_not_500() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=req)

    reg = ToolRegistry()
    reg.register(WorkflowTool(definition=_wf_def(), client=_client(handler, timeout=3.5)))

    # registry.execute must convert the failure to a ToolResult — never let it
    # escape as an unhandled 500.
    result = await reg.execute(ToolCall(id="x2", name="create_task", arguments={}))
    assert result.is_error is True
    assert result.content == "workflow 'create_task' timed out after 3.5s"


@pytest.mark.asyncio
async def test_transport_error_becomes_is_error_marker() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=req)

    run = await _client(handler).run(name="create_task", arguments={})
    assert run.ok is False
    assert run.output == "workflow 'create_task' could not reach the workflow backend"


# --- auth header + URL convention -------------------------------------------


@pytest.mark.asyncio
async def test_auth_header_sent_and_url_derived_by_convention() -> None:
    seen: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers.get("authorization")
        seen["url"] = str(req.url)
        seen["body"] = req.content
        return httpx.Response(200, json={"ok": True})

    run = await _client(handler).run(name="create_task", arguments={"title": "hi"})
    assert run.ok is True
    assert seen["auth"] == f"Bearer {TOKEN}"
    assert seen["url"] == "https://n8n.example.test/webhook/create_task"
    assert json.loads(seen["body"]) == {"title": "hi"}


# --- SECURITY: token never leaks (the load-bearing test) --------------------


@pytest.mark.asyncio
async def test_token_never_appears_in_logs_output_or_exception_on_failure() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    reg = ToolRegistry()
    reg.register(WorkflowTool(definition=_wf_def(), client=_client(handler)))

    with structlog.testing.capture_logs() as logs:
        result = await reg.execute(ToolCall(id="x3", name="create_task", arguments={"title": "t"}))

    assert result.is_error is True
    # Token in NONE of: model-facing content, or any captured log record.
    assert TOKEN not in result.content
    assert TOKEN not in repr(logs)

    # And on the timeout path, the returned output is token-free too.
    def timeout_handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("t", request=req)

    run = await _client(timeout_handler).run(name="create_task", arguments={})
    assert TOKEN not in run.output


# --- build_workflow_client wiring -------------------------------------------


def test_build_n8n_with_full_config_returns_n8n_client() -> None:
    client = build_workflow_client(
        _base(
            workflow_client="n8n",
            n8n_base_url="https://n8n.internal",
            n8n_auth_token="tok",
            n8n_timeout_seconds=7.0,
        )
    )
    assert isinstance(client, N8nWorkflowClient)


def test_build_n8n_applies_configured_timeout_and_auth_header() -> None:
    client = build_workflow_client(
        _base(
            workflow_client="n8n",
            n8n_base_url="https://n8n.internal",
            n8n_auth_token=TOKEN,
            n8n_timeout_seconds=3.5,
        )
    )
    assert isinstance(client, N8nWorkflowClient)
    # The hard timeout is actually applied to the pooled httpx client, and the
    # token is wired ONLY as the Authorization header. (Reaching into the
    # private client is test-only.)
    assert client._client.timeout.read == 3.5
    assert client._client.headers["authorization"] == f"Bearer {TOKEN}"


def test_build_n8n_missing_base_url_raises_at_build_time() -> None:
    with pytest.raises(RuntimeError, match="N8N_BASE_URL"):
        build_workflow_client(_base(workflow_client="n8n", n8n_auth_token="tok"))


def test_build_n8n_missing_token_raises_at_build_time() -> None:
    with pytest.raises(RuntimeError, match="N8N_AUTH_TOKEN"):
        build_workflow_client(_base(workflow_client="n8n", n8n_base_url="https://x"))


def test_build_n8n_missing_config_error_is_not_a_silent_mock_fallback() -> None:
    # A misconfigured n8n must NOT quietly become a mock (that would make a
    # broken prod look healthy). It raises instead.
    with pytest.raises(RuntimeError):
        build_workflow_client(_base(workflow_client="n8n"))


def test_build_mock_is_the_default() -> None:
    assert isinstance(build_workflow_client(_base()), MockWorkflowClient)
