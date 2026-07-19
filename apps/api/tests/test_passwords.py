"""Password hashing round-trip + failure modes."""

from __future__ import annotations

from app.infrastructure.security import hash_password, verify_password


def test_hash_verify_roundtrip() -> None:
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True


def test_wrong_password_returns_false() -> None:
    h = hash_password("secret")
    assert verify_password("not-the-secret", h) is False


def test_malformed_hash_returns_false_no_raise() -> None:
    assert verify_password("anything", "not-a-hash") is False
    assert verify_password("anything", "") is False


def test_hash_output_is_argon2id() -> None:
    assert hash_password("x").startswith("$argon2id$")
