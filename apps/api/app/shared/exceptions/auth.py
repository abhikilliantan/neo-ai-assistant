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


class InsufficientScopeError(AuthError):
    """A valid principal lacks the scope the endpoint requires. Mapped to 403.

    Distinct from AuthenticationError (401): the caller IS authenticated, just
    not authorized for this action.
    """

    def __init__(self, required_scope: str) -> None:
        self.required_scope = required_scope
        super().__init__(f"missing required scope: {required_scope}")
