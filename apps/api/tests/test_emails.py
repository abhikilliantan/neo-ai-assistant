"""Email normalization: strip + lowercase."""

from __future__ import annotations

from app.infrastructure.security import normalize_email


def test_lowercases_and_strips() -> None:
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"


def test_idempotent() -> None:
    x = normalize_email("bob@example.com")
    assert normalize_email(x) == x
