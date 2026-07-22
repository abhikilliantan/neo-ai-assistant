"""Domain exceptions for auth. Mapped to HTTP in core/exceptions.py."""

from __future__ import annotations


class AuthError(Exception):
    """Base class for auth-domain failures."""


class AuthenticationError(AuthError):
    """Bad credentials, invalid/expired/wrong-type token, missing/revoked session.

    Deliberately generic so callers can't distinguish among failure modes
    (prevents user enumeration via login).
    """


class EmailAlreadyRegisteredError(AuthError):
    """Registration attempt with an email that already exists."""


class RegistrationClosedError(AuthError):
    """Public registration is gated off (R6). Raised by POST /register when
    settings.registration_enabled is False; mapped to 403."""
