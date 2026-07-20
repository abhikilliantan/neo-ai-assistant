"""Phase 7f-1 — SSRF guard, adversarially tested. ZERO real network / DNS: the
resolver is INJECTED everywhere so every case is deterministic and offline.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.ai.workflows import N8nWorkflowClient, build_workflow_client
from app.ai.workflows.urlguard import (
    UrlNotAllowedError,
    ValidatedTarget,
    system_resolver,
    validate_workflow_url,
)
from app.application.ports.workflows import WorkflowRun
from app.infrastructure.config import Settings

PUBLIC_IP = "93.184.216.34"  # public literal used across the happy-path cases


def _resolver(mapping: dict[str, list[str]]):
    """Offline resolver: hostname -> fixed IP list. Raises on an unmapped host
    so a test can never accidentally trigger a real lookup.
    """

    def resolve(host: str) -> list[str]:
        if host not in mapping:  # pragma: no cover - guards against test mistakes
            raise AssertionError(f"unexpected DNS lookup for {host!r}")
        return mapping[host]

    return resolve


def _never_resolve(host: str) -> list[str]:  # for IP-literal cases (no DNS needed)
    raise AssertionError(f"IP literal must not resolve: {host!r}")  # pragma: no cover


# --- blocked categories (IP literals — no DNS) ------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/webhook",  # loopback v4
        "http://127.9.9.9/webhook",  # loopback /8
        "http://[::1]/webhook",  # loopback v6
        "http://169.254.169.254/latest/meta-data/",  # CLOUD METADATA
        "http://10.0.0.5/webhook",  # RFC1918 10/8
        "http://172.16.0.9/webhook",  # RFC1918 172.16/12
        "http://192.168.1.10/webhook",  # RFC1918 192.168/16
        "http://[fc00::1]/webhook",  # IPv6 ULA
        "http://[fd12:3456::1]/webhook",  # IPv6 ULA
        "http://[fe80::1]/webhook",  # link-local v6
        "http://224.0.0.1/webhook",  # multicast v4
        "http://[ff02::1]/webhook",  # multicast v6
        "http://0.0.0.0/webhook",  # unspecified
        "http://255.255.255.255/webhook",  # broadcast
        "http://[::ffff:127.0.0.1]/webhook",  # IPv4-mapped IPv6 bypass
        "http://user:pass@169.254.169.254/webhook",  # userinfo trick -> metadata
    ],
)
def test_blocked_ip_literals_are_rejected(url: str) -> None:
    with pytest.raises(UrlNotAllowedError):
        validate_workflow_url(url, resolve=_never_resolve, allowed_ports=frozenset({80, 443}))


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "gopher://x/", "ftp://h/f", "data:text/plain,hi"]
)
def test_non_http_schemes_are_rejected(url: str) -> None:
    with pytest.raises(UrlNotAllowedError):
        validate_workflow_url(url, resolve=_never_resolve)


# --- the load-bearing test: address validation, not string matching ---------


def test_public_hostname_resolving_to_private_ip_is_rejected() -> None:
    """A perfectly public NAME that resolves to a private/metadata IP MUST be
    rejected. This proves we validate resolved ADDRESSES, not the host string —
    string-matching "localhost" stops nobody.
    """
    resolve = _resolver({"totally-legit.example": ["169.254.169.254"]})
    with pytest.raises(UrlNotAllowedError):
        validate_workflow_url("https://totally-legit.example/webhook", resolve=resolve)


def test_multi_record_any_disallowed_is_rejected() -> None:
    """[public, private] -> REJECT. Any-disallowed, never majority-rules."""
    resolve = _resolver({"mixed.example": [PUBLIC_IP, "10.0.0.5"]})
    with pytest.raises(UrlNotAllowedError):
        validate_workflow_url("https://mixed.example/webhook", resolve=resolve)


# --- ports ------------------------------------------------------------------


def test_disallowed_port_is_rejected() -> None:
    resolve = _resolver({"public.example": [PUBLIC_IP]})
    with pytest.raises(UrlNotAllowedError):
        validate_workflow_url("http://public.example:8080/webhook", resolve=resolve)


def test_default_ports_pass() -> None:
    resolve = _resolver({"public.example": [PUBLIC_IP]})
    assert validate_workflow_url("https://public.example/webhook", resolve=resolve).port == 443
    assert validate_workflow_url("http://public.example/webhook", resolve=resolve).port == 80


# --- allowlist mode ---------------------------------------------------------


def test_allowlist_blocks_unlisted_public_host() -> None:
    resolve = _resolver({"other.example": [PUBLIC_IP]})
    with pytest.raises(UrlNotAllowedError):
        validate_workflow_url(
            "https://other.example/webhook", resolve=resolve, allowlist=["n8n.example.test"]
        )


def test_allowlist_passes_listed_public_host() -> None:
    resolve = _resolver({"n8n.example.test": [PUBLIC_IP]})
    target = validate_workflow_url(
        "https://n8n.example.test/webhook", resolve=resolve, allowlist=["n8n.example.test"]
    )
    assert isinstance(target, ValidatedTarget)
    assert target.host == "n8n.example.test"
    assert target.addresses == (PUBLIC_IP,)


# --- no regression: the current code-owned URL passes -----------------------


def test_current_code_owned_url_passes() -> None:
    """The 7c convention URL (base + /webhook/<name>) must still pass — this
    slice lands with zero behavioral change for the code-owned URL.
    """
    resolve = _resolver({"n8n.example.test": [PUBLIC_IP]})
    target = validate_workflow_url("https://n8n.example.test/webhook/create_task", resolve=resolve)
    assert target.addresses == (PUBLIC_IP,)


# --- production resolver, exercised OFFLINE (IP literals, no DNS) ------------


def test_system_resolver_on_ip_literals_does_no_dns() -> None:
    # getaddrinfo on a literal returns the literal — no name resolution/network.
    assert system_resolver("127.0.0.1") == ["127.0.0.1"]
    assert system_resolver("::1") == ["::1"]


# --- client integration -----------------------------------------------------


def _client(handler: Any, *, base_url: str, resolve: Any, allowlist: Any = ()) -> N8nWorkflowClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
    return N8nWorkflowClient(
        client=http, base_url=base_url, timeout_seconds=5.0, resolve=resolve, allowlist=allowlist
    )


@pytest.mark.asyncio
async def test_blocked_url_yields_ok_false_marker_without_calling_out() -> None:
    called = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        called["n"] += 1
        return httpx.Response(200, json={"ok": True})

    # base host resolves to the metadata IP → guard must block before any POST.
    resolve = _resolver({"evil.example": ["169.254.169.254"]})
    client = _client(handler, base_url="https://evil.example", resolve=resolve)

    run = await client.run(name="create_task", arguments={"title": "x"})
    assert isinstance(run, WorkflowRun)
    assert run.ok is False
    # The outbound call NEVER happened — blocked pre-flight.
    assert called["n"] == 0
    # Marker is generic: no host, no resolved IP, no reason.
    assert run.output == "workflow 'create_task' was blocked by the outbound security policy"
    assert "169.254" not in run.output
    assert "evil.example" not in run.output


@pytest.mark.asyncio
async def test_allowed_url_still_calls_through() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"created": True})

    resolve = _resolver({"n8n.example.test": [PUBLIC_IP]})
    client = _client(handler, base_url="https://n8n.example.test", resolve=resolve)
    run = await client.run(name="create_task", arguments={"title": "x"})
    assert run.ok is True


def test_build_workflow_client_sets_follow_redirects_false() -> None:
    """A permitted public URL that 302s to the metadata endpoint would defeat
    the guard — redirects must never be followed.
    """
    settings = Settings(
        python_env="test",
        database_url="postgresql+asyncpg://x/x",
        app_database_url="postgresql+asyncpg://x/x",
        redis_url="redis://x",
        jwt_secret_key="test-secret-key-at-least-32-bytes-long-xxxxx",
        workflow_client="n8n",
        n8n_base_url="https://n8n.internal",
        n8n_auth_token="tok",  # test-only placeholder, not a real secret
    )
    client = build_workflow_client(settings)
    assert isinstance(client, N8nWorkflowClient)
    assert client._client.follow_redirects is False
