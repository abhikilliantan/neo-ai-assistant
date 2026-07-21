"""Domain exceptions for document parsing (Phase 8a).

Parsing UNTRUSTED uploaded files is a classic attack surface (zip bombs, XXE,
malformed structures that hang or exhaust memory). These exceptions make
resource limits part of the parser contract NOW — before 8f wires real parsers
— so enforcement is cheaper than retrofitting. 8c maps these to HTTP.
"""

from __future__ import annotations


class DocumentParseError(Exception):
    """Base class for document-parsing failures."""


class DocumentTooLargeError(DocumentParseError):
    """The input exceeds a configured resource limit (bytes, pages, elements).

    Raised BEFORE doing expensive work where possible (e.g. a byte-length check
    up front), so an oversized upload is rejected cheaply rather than parsed.
    """


class UnsupportedContentTypeError(DocumentParseError):
    """The parser does not handle this content type."""
