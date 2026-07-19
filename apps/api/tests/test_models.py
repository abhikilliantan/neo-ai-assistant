"""Smoke test: identity/tenancy/rbac models register on Base.metadata."""

from __future__ import annotations

from app.infrastructure.db import (
    Base,
    models,  # noqa: F401  (populates metadata)
)


def test_all_expected_tables_registered() -> None:
    expected = {
        "users",
        "sessions",
        "organizations",
        "memberships",
        "api_keys",
        "roles",
        "permissions",
        "role_permissions",
    }
    got = set(Base.metadata.tables.keys())
    missing = expected - got
    assert not missing, f"missing tables in metadata: {missing}"
