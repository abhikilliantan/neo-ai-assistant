"""Argon2id password hashing.

Uses argon2-cffi's PasswordHasher() defaults (OWASP-recommended minima):
argon2id, time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=4,
hash_len=32, salt_len=16. Tune later via PasswordHasher(time_cost=..., ...)
if we outgrow defaults.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time verify. Returns False on mismatch or malformed hash; never raises."""
    # InvalidHashError inherits from ValueError, not Argon2Error — catch both.
    try:
        return _hasher.verify(hashed, plain)
    except (Argon2Error, InvalidHashError):
        return False
