"""Real n8n webhook workflow client (Phase 7c) — the first Phase 7 code that
touches the network.

Implements the `WorkflowClient` port (`async run(*, name, arguments) ->
WorkflowRun`) against n8n webhooks. CI/test default stays `MockWorkflowClient`;
this client is only wired when WORKFLOW_CLIENT=n8n, and it is tested with an
injected `httpx.MockTransport` — never a live URL.

name -> URL: CONVENTION (7c). `base_url + "/webhook/" + name`, resolved in the
single `_url_for` method. The port stays framework-free and URL-free (7a's
decision); the only infra knob is `n8n_base_url`. 7f (tenant-defined workflows
as DB rows) will REPLACE this: each row carries its own arbitrary URL, so
`_url_for` becomes "read the row's URL" — and that URL is tenant-supplied, so
it MUST be validated/allowlisted first (SSRF surface). Kept to one method so
that migration is one edit.

NO RETRIES. Webhooks are side-effecting and generally NOT idempotent — a retry
of `create_task` silently creates two tasks. A timeout is the worst case: the
workflow may have ALREADY run, so re-sending could double-fire. There is
deliberately no retry here; do not add one casually. (A connect-only retry was
considered and rejected: httpx does not cleanly guarantee "failed before any
bytes were sent" across keep-alive connection reuse, so it is not provably
side-effect-free.)

SECURITY. The auth token lives ONLY as an `Authorization` header on the pooled
client — it is never formatted into a URL, a log line, an exception, or any
returned string. On EVERY failure path this client returns a curated STATUS
MARKER (never the raw n8n response body): `tool.execute.failed` logs
`error=str(e)` where `str(e)` is exactly this output (WorkflowTool raises
`RuntimeError(run.output)` on ok=False), so the output must be log-safe. The
raw body is discarded — unaudited n8n error bodies can carry customer data, and
truncating them would reduce volume, not sensitivity. The status is enough for
the model to recover (4xx → bad input, don't blind-retry; 5xx → backend/
transient). On SUCCESS the output IS the (serialized) body — that goes to the
model as ephemeral tool_result and is never logged.

Lifecycle: ONE long-lived pooled `httpx.AsyncClient`, reused across calls to
amortize TLS/connect on the latency path, closed via `close()` in the lifespan.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Mapping
from typing import Any

import httpx

from app.ai.workflows.urlguard import (
    Resolver,
    UrlNotAllowedError,
    system_resolver,
    validate_workflow_url,
)
from app.application.ports.workflows import WorkflowRun


def _serialize(response: httpx.Response) -> str:
    """2xx body -> string. JSON is re-dumped with sorted keys for determinism;
    anything else passes through as text.
    """
    try:
        payload = response.json()
    except ValueError:
        return response.text
    return json.dumps(payload, sort_keys=True)


class N8nWorkflowClient:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        base_url: str,
        timeout_seconds: float,
        resolve: Resolver = system_resolver,
        allowlist: Iterable[str] = (),
        url_overrides: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        # 7f-1 SSRF guard inputs. `resolve` is injectable so tests stay offline;
        # `allowlist` (empty by default) narrows reachable hosts when a
        # security-conscious deployment sets N8N_ALLOWED_HOSTS.
        self._resolve = resolve
        self._allowlist = tuple(allowlist)
        # 7f-2: per-request name -> URL map for TENANT workflows (their webhook
        # lives on a DB row, not the built-in convention). Built-in names aren't
        # in the map and fall through to the convention below.
        self._url_overrides = dict(url_overrides or {})

    def with_url_overrides(self, url_overrides: Mapping[str, str]) -> N8nWorkflowClient:
        """Return a REQUEST-SCOPED copy that resolves the given tenant workflow
        names to their row URLs, SHARING this client's pooled httpx transport
        (no new connection pool). The copy is discarded after the request and
        must not be closed — only the long-lived original owns `close()`.
        """
        return N8nWorkflowClient(
            client=self._client,
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
            resolve=self._resolve,
            allowlist=self._allowlist,
            url_overrides=url_overrides,
        )

    def _url_for(self, name: str) -> str:
        # 7f-2: tenant workflows use their row URL; built-ins keep the 7c
        # convention (base_url + /webhook/<name>).
        override = self._url_overrides.get(name)
        return override if override is not None else f"{self._base_url}/webhook/{name}"

    async def run(self, *, name: str, arguments: dict[str, Any]) -> WorkflowRun:
        url = self._url_for(name)
        # 7f-1: validate the target BEFORE any outbound call. The guard resolves
        # + range-checks every IP (getaddrinfo is blocking → run it off the
        # loop). A rejected URL is a normal failure, never a raise (same 7c
        # posture), and the marker leaks NO host, IP, or reason — telling an
        # attacker WHY it was blocked would help them map the internal network.
        try:
            await asyncio.to_thread(
                validate_workflow_url,
                url,
                resolve=self._resolve,
                allowlist=self._allowlist,
            )
        except UrlNotAllowedError:
            return WorkflowRun(
                ok=False,
                output=f"workflow {name!r} was blocked by the outbound security policy",
            )
        try:
            response = await self._client.post(url, json=arguments)
        except httpx.TimeoutException:
            # NO RETRY (see module docstring): a timed-out webhook may already
            # have run. Curated marker only — no URL, token, or exception text.
            return WorkflowRun(
                ok=False,
                output=f"workflow {name!r} timed out after {self._timeout_seconds}s",
            )
        except httpx.RequestError:
            # Connect/network error. Still one attempt only. Curated marker.
            return WorkflowRun(
                ok=False,
                output=f"workflow {name!r} could not reach the workflow backend",
            )
        if not response.is_success:
            # Non-2xx -> ok=False with a STATUS MARKER. The raw body is
            # DISCARDED: it is unaudited (customer data, stack traces) and this
            # string is what tool.execute.failed logs. Status is enough for the
            # model to recover.
            return WorkflowRun(
                ok=False,
                output=f"workflow {name!r} failed with HTTP {response.status_code}",
            )
        return WorkflowRun(ok=True, output=_serialize(response))

    async def close(self) -> None:
        await self._client.aclose()
