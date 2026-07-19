"""Email normalization — strip + lowercase.

Callers hitting the `lower(email)` unique index on users must go through this
first so writes and lookups compare consistently.
"""

from __future__ import annotations


def normalize_email(raw: str) -> str:
    return raw.strip().lower()
