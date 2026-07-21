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


class DocumentDecodeError(DocumentParseError):
    """The bytes could not be decoded as text (8f-1: tried utf-8-sig then utf-8).

    Deliberately does NOT fall back to a lossy codec: a rejected upload (→ 422,
    inherited from DocumentParseError) beats silently corrupted text the user
    can't tell is wrong. The message never contains byte content.
    """


class DocumentConfigError(Exception):
    """Misconfiguration that would corrupt ingest — raised at BUILD time, loudly.

    The token-cap guard raises this when the configured `chunk_size` (characters)
    could produce a chunk exceeding the embedding model's max input tokens. The
    embedding provider would silently truncate such a chunk at embed time,
    corrupting retrieval invisibly — the worst failure mode here — so we refuse
    to start instead.
    """
