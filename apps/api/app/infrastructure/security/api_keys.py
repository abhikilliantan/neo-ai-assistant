"""API-key secret generation + hashing.

A raw key looks like ``neo_sk_<43-url-safe-chars>``. We store only:
  - ``key_prefix`` — the readable first 15 chars (``neo_sk_`` + 8 token chars),
    for display AND O(1) lookup at auth time.
  - ``key_hash`` — SHA-256 hex of the FULL raw key. The plaintext is shown ONCE
    at creation and never persisted. Mirrors ``sessions.refresh_token_hash``
    (tokens.py): the secret is already high-entropy, so SHA-256 as a lookup key
    is sufficient — no KDF (argon2) needed, unlike passwords.

Never log or store ``raw``. Verify with ``verify_api_key`` (constant-time).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

KEY_PREFIX = "neo_sk_"
# len("neo_sk_") + 8 token chars = 15; fits ApiKey.key_prefix String(16).
_PREFIX_LEN = len(KEY_PREFIX) + 8

# Scopes the system can actually enforce today. Read-only to start; extend as
# write surfaces land. create_api_key rejects anything outside this set so we
# never mint a key carrying a scope nothing checks.
SUPPORTED_SCOPES: frozenset[str] = frozenset({"read"})
DEFAULT_SCOPES: tuple[str, ...] = ("read",)


@dataclass(frozen=True, slots=True)
class GeneratedApiKey:
    raw: str  # full plaintext — return to caller ONCE, never persist
    key_prefix: str  # stored for display + lookup
    key_hash: str  # stored; SHA-256 hex of raw


def hash_api_key(raw: str) -> str:
    """SHA-256 hex of the raw key — the deterministic lookup/verify hash."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def prefix_of(raw: str) -> str:
    return raw[:_PREFIX_LEN]


def generate_api_key() -> GeneratedApiKey:
    """Mint a new key. `secrets.token_urlsafe(32)` = 256 bits of entropy."""
    raw = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return GeneratedApiKey(raw=raw, key_prefix=prefix_of(raw), key_hash=hash_api_key(raw))


def verify_api_key(raw: str, key_hash: str) -> bool:
    """Constant-time compare of SHA-256(raw) against the stored hash."""
    return hmac.compare_digest(hash_api_key(raw), key_hash)
