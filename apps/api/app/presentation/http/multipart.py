"""Streaming multipart upload reader for the document endpoint (8c).

⚠️ SECURITY: this is where untrusted files enter. Two jobs, both done BEFORE the
whole body is ever in memory as a single blob:

  1. Enforce the size limit WHILE streaming. We read `request.stream()` chunk by
     chunk and abort the instant the cumulative bytes exceed `max_bytes` — a
     naive `await request.body()` / FastAPI `UploadFile` would receive the entire
     upload first (a trivial memory DoS). The limit is applied to the raw request
     body, which is ≥ the file content, so the file is guaranteed ≤ max_bytes.

  2. Only THEN parse the bounded (≤ max_bytes) body with python-multipart's
     parse_form. Parsing a bounded in-memory buffer cannot blow up memory.

The filename arrives as attacker-controlled bytes and is sanitized separately by
`sanitize_filename` (no path traversal, no control chars, bounded length).
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Protocol

from python_multipart import parse_form
from python_multipart.multipart import File

from app.shared.exceptions.common import BadRequestError
from app.shared.exceptions.documents import DocumentTooLargeError

_MAX_FILENAME_LEN = 255
_FALLBACK_FILENAME = "upload"


@dataclass(frozen=True)
class UploadedFile:
    filename: str  # already sanitized
    content_type: str  # the part's declared type (attacker-controlled; allowlist downstream)
    data: bytes


class _StreamRequest(Protocol):
    """The slice of Starlette's Request we depend on — kept narrow so the reader
    is unit-testable with a fake. A real Request satisfies it structurally."""

    @property
    def headers(self) -> Mapping[str, str]: ...
    def stream(self) -> AsyncIterator[bytes]: ...


def sanitize_filename(raw: str) -> str:
    """Make an untrusted filename safe to store and later display.

    - basename only: strips any directory components (defeats ../../ and absolute
      paths) by splitting on BOTH separators before taking the last segment.
    - drops non-printable / control characters.
    - collapses surrounding whitespace and bounds length.
    - falls back to a fixed name if nothing usable remains (never returns "",
      ".", or "..").
    """
    # Normalize both separators, then take the final path segment.
    base = raw.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(ch for ch in base if ch.isprintable() and ch not in {"\t", "\n", "\r"})
    cleaned = cleaned.strip().strip("\x00")[:_MAX_FILENAME_LEN]
    if not cleaned or cleaned in {".", ".."}:
        return _FALLBACK_FILENAME
    return cleaned


async def read_upload(request: _StreamRequest, *, max_bytes: int) -> UploadedFile:
    """Stream-read + size-guard + parse a single-file multipart upload.

    Raises DocumentTooLargeError (→413) if the body exceeds max_bytes, or
    BadRequestError (→400) if it isn't multipart or carries no file part.
    """
    content_type_header = request.headers.get("content-type") or ""
    if not content_type_header.lower().startswith("multipart/form-data"):
        raise BadRequestError("expected a multipart/form-data upload")

    # (1) Size-guarded streaming read. Abort the moment we exceed the limit —
    # BEFORE pulling the next chunk, so we never buffer the whole oversized body.
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise DocumentTooLargeError("upload exceeds the configured size limit")

    # (2) Parse the bounded body. parse_form over ≤ max_bytes in memory is safe.
    files: list[File] = []
    parse_form(
        {"Content-Type": content_type_header.encode("latin-1")},
        io.BytesIO(bytes(buffer)),
        on_field=None,
        on_file=files.append,
    )
    file_parts = [f for f in files if f.file_name is not None]
    if not file_parts:
        raise BadRequestError("multipart upload contained no file part")

    part = file_parts[0]
    part.file_object.seek(0)
    data = part.file_object.read()
    part.close()

    raw_name = part.file_name
    filename = raw_name.decode("utf-8", "replace") if isinstance(raw_name, bytes) else str(raw_name)
    return UploadedFile(
        filename=sanitize_filename(filename),
        content_type=part.content_type or "application/octet-stream",
        data=data,
    )
