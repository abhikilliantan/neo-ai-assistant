"""Cross-cutting domain exceptions. Mapped to HTTP in core/exceptions.py."""

from __future__ import annotations


class NotFoundError(Exception):
    """The requested resource does not exist, or is not visible to the caller.

    Because RLS filters cross-tenant rows to nothing, "missing" and
    "belongs to another tenant" collapse to the same 404 — an important
    property (no existence oracle for other tenants' resource IDs).
    """


class BadRequestError(Exception):
    """The request is malformed in a way validation didn't catch (e.g. a
    non-multipart body on an upload route, or a multipart body with no file
    part). Mapped to 400 with the standard envelope — never leaks internals.
    """
