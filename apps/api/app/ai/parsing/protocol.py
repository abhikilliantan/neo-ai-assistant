"""Child/parent parse protocol (ADR 0003). Pure stdlib — safe in the minimal child.

The child returns JSON on stdout (never pickle — untrusted-deserialization is an
RCE vector): success `{"blocks": [{"text","page","section"}], ...}`, or a HANDLED
failure `{"error_class","message"}` with exit 0. `ChildParseError` is how a child
parser signals a handled failure instead of crashing.
"""

from __future__ import annotations


class ChildParseError(Exception):
    """A parse failure the child HANDLES and reports as structured JSON
    ({error_class, message}, exit 0), rather than crashing. `error_class` is
    mapped by the parent to a domain exception → HTTP status."""

    def __init__(self, message: str, *, error_class: str = "parse_error") -> None:
        super().__init__(message)
        self.error_class = error_class
