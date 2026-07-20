"""SSRF guard for outbound workflow URLs (Phase 7f-1).

Built BEFORE the attack surface exists: today every workflow URL is code-owned,
so this lands with zero behavioral risk. In 7f-2 workflow URLs become
TENANT-SUPPLIED database rows — at which point an unguarded outbound client is a
server-side request forgery primitive (a tenant could point a workflow at
http://169.254.169.254/ for cloud-metadata credentials, at our own API to
bypass auth from inside the trust boundary, or at any private-network host).

`validate_workflow_url` is PURE and SYNCHRONOUS: security logic should be
trivial to reason about and exhaustively testable. The DNS resolver is INJECTED
so tests are deterministic and offline — no test ever performs a real lookup.

⚠️ DNS-REBINDING — DELIBERATE, DOCUMENTED RESIDUAL RISK (not silence).
We resolve and validate the host's IPs here, but the caller (N8nWorkflowClient)
then connects by HOSTNAME, which httpx re-resolves. Between our check-resolve
and httpx's connect-resolve, an attacker-controlled authoritative DNS with a
tiny TTL could answer public on the check and private on the connect (a TOCTOU
gap). We ACCEPT this residual for now rather than pin the connection to the
validated IP, because pinning while preserving correct TLS SNI + certificate
verification needs a custom httpx transport, and getting that subtly wrong would
DISABLE cert verification — a worse outcome than the narrow rebinding window.
It is mitigated by: (1) follow_redirects=False on the client (kills the
redirect-to-metadata variant), and (2) the host allowlist (an attacker's
rebinding domain must itself be allowlisted). Full IP-pinning is deferred to its
own slice with a purpose-built transport.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

# hostname -> list of resolved IP strings (both A and AAAA). Injected so tests
# stay offline; production uses `system_resolver`.
Resolver = Callable[[str], list[str]]

_IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_ALLOWED_PORTS = frozenset({80, 443})
_DEFAULT_PORT_FOR_SCHEME = {"http": 80, "https": 443}
_V4_BROADCAST = ipaddress.IPv4Address("255.255.255.255")


class UrlNotAllowedError(Exception):
    """A URL failed the SSRF policy.

    The message is DEVELOPER-facing only (logs/tests). It is NEVER surfaced to
    the model or the client response — N8nWorkflowClient maps this to a generic,
    detail-free marker so an attacker learns neither WHY it was blocked nor what
    resolved to what (which would help them map the internal network).
    """


@dataclass(frozen=True)
class ValidatedTarget:
    scheme: str
    host: str
    port: int
    addresses: tuple[str, ...]  # every resolved IP, each already validated


def _as_ip(value: str) -> _IpAddress | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _is_blocked_ip(ip: _IpAddress) -> bool:
    """True if `ip` is anything other than a globally-routable public address.

    Explicit category checks (auditable intent) PLUS `not is_global` as a
    backstop for anything the named categories miss across Python versions.
    """
    # IPv4-mapped IPv6 (::ffff:127.0.0.1) is a classic bypass — collapse it to
    # its embedded IPv4 and judge that.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_loopback  # 127.0.0.0/8, ::1
        or ip.is_link_local  # 169.254.0.0/16 (cloud metadata!) + fe80::/10
        or ip.is_private  # RFC1918 (10/8, 172.16/12, 192.168/16), fc00::/7 ULA, ...
        or ip.is_multicast  # 224.0.0.0/4, ff00::/8
        or ip.is_reserved
        or ip.is_unspecified  # 0.0.0.0, ::
        or (isinstance(ip, ipaddress.IPv4Address) and ip == _V4_BROADCAST)
        or not ip.is_global  # backstop
    )


def system_resolver(hostname: str) -> list[str]:
    """Production resolver — every A and AAAA record for `hostname`. NEVER used
    in tests (they inject a fake resolver so nothing touches DNS).
    """
    infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    # sockaddr[0] is the address string for both AF_INET and AF_INET6.
    return list({str(info[4][0]) for info in infos})


def validate_workflow_url(
    raw_url: str,
    *,
    resolve: Resolver,
    allowlist: Iterable[str] = (),
    allowed_ports: Iterable[int] = _DEFAULT_ALLOWED_PORTS,
) -> ValidatedTarget:
    """Return a ValidatedTarget for `raw_url`, or raise UrlNotAllowedError.

    Order: scheme → host present → port → allowlist → resolve-and-validate IPs.
    The allowlist (when non-empty) is authoritative on the HOST, but IP-range
    checks ALWAYS run too (defense in depth). Rejects if ANY resolved IP is
    disallowed — never majority-rules.
    """
    parts = urlsplit(raw_url)

    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UrlNotAllowedError(f"scheme not allowed: {scheme!r}")

    host = parts.hostname
    if not host:
        raise UrlNotAllowedError("missing host")
    host = host.lower()

    try:
        port = parts.port if parts.port is not None else _DEFAULT_PORT_FOR_SCHEME[scheme]
    except ValueError as e:  # urlsplit lazily rejects a malformed port
        raise UrlNotAllowedError("invalid port") from e
    if port not in frozenset(allowed_ports):
        raise UrlNotAllowedError(f"port not allowed: {port}")

    allow = frozenset(h.strip().lower() for h in allowlist if h.strip())
    if allow and host not in allow:  # exact match only — no subdomain wildcards
        raise UrlNotAllowedError("host not in allowlist")

    # Resolve to IPs and validate every one. A literal IP in the URL is judged
    # directly (no DNS). String-matching the host is NOT enough — a public name
    # can resolve to 127.0.0.1 or 169.254.169.254.
    literal = _as_ip(host)
    candidates = [host] if literal is not None else resolve(host)
    if not candidates:
        raise UrlNotAllowedError("host did not resolve")

    addresses: list[str] = []
    for candidate in candidates:
        ip = _as_ip(candidate)
        if ip is None:
            raise UrlNotAllowedError("resolver returned a non-IP value")
        if _is_blocked_ip(ip):
            # Dev-facing message only; the client never echoes this.
            raise UrlNotAllowedError("resolved to a disallowed address")
        addresses.append(str(ip))

    return ValidatedTarget(scheme=scheme, host=host, port=port, addresses=tuple(addresses))
