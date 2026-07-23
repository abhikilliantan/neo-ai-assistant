"""Subprocess parse-isolation harness — parent side (ADR 0003 slice 1).

Runs a parser in a FRESH, hard-killable child process so a hung or bomb-triggered
parse can neither block the event loop nor exhaust the worker's memory — the exact
failure the inline `asyncio.wait_for` path cannot prevent (`ports/documents.py:129`).

- The parent pipes the document BYTES to the child's stdin (never a filesystem
  path → stays storage-backend-agnostic per ADR 0002).
- Resource limits (RLIMIT_AS = memory cap; RLIMIT_CPU) are applied IN the child
  via `preexec_fn` before exec.
- The wall-clock timeout is enforced by the parent (`communicate(timeout=…)`); on
  expiry the child's whole process group is SIGKILL'd. The blocking wait runs in a
  worker thread (`asyncio.to_thread`) so the event loop is never blocked — and the
  kill is OS-level, so a hung child can never wedge the parent regardless.
- The parent builds `full_text` = join of the returned block texts, so the offset
  round-trip invariant (`full_text[start:end] == block.text`) holds parent-side by
  construction — the child never sends offsets.

POSIX/Linux only (RLIMIT_*); the ADR documents macOS host as unsupported for real
parsing. `child_env`/`on_spawn` are internal test seams.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import resource
import signal
import subprocess
import sys
from collections.abc import Callable

from app.application.ports.documents import ParsedBlock, ParsedDocument
from app.shared.exceptions.documents import (
    DocumentParseError,
    DocumentParseTimeoutError,
    DocumentTooLargeError,
    UnsupportedContentTypeError,
)

_CHILD_MODULE = "app.ai.parsing.child"
DEFAULT_MAX_MEMORY_BYTES = 1_073_741_824  # 1 GiB (ADR 0003, resolved Open Question 1)
DEFAULT_TIMEOUT_SECONDS = 30.0

# Child-reported error_class → domain exception (→ HTTP status via the handlers).
_ERROR_CLASS_MAP: dict[str, type[DocumentParseError]] = {
    "parse_error": DocumentParseError,
    "too_large": DocumentTooLargeError,
    "unsupported": UnsupportedContentTypeError,
}


def _child_preexec(max_memory_bytes: int, cpu_seconds: int) -> Callable[[], None]:
    def _apply() -> None:  # runs in the child after fork, before exec
        resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))

    return _apply


async def parse_in_subprocess(
    *,
    parser: str,
    data: bytes,
    content_type: str,
    max_memory_bytes: int = DEFAULT_MAX_MEMORY_BYTES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    child_env: dict[str, str] | None = None,
    on_spawn: Callable[[int], None] | None = None,
) -> ParsedDocument:
    """Parse `data` in a fresh child process and return a `ParsedDocument`. Never
    blocks the event loop and never propagates a raw crash — every failure maps to
    a domain exception."""
    return await asyncio.to_thread(
        _run_child,
        parser,
        data,
        content_type,
        max_memory_bytes,
        timeout_seconds,
        child_env,
        on_spawn,
    )


def _run_child(
    parser: str,
    data: bytes,
    content_type: str,
    max_memory_bytes: int,
    timeout_seconds: float,
    child_env: dict[str, str] | None,
    on_spawn: Callable[[int], None] | None,
) -> ParsedDocument:
    cpu_seconds = int(timeout_seconds) + 2  # CPU cap a hair above the wall-clock budget
    env = os.environ.copy()
    if child_env:
        env.update(child_env)

    proc = subprocess.Popen(  # noqa: S603 - fixed argv, our own child module
        [sys.executable, "-m", _CHILD_MODULE, parser],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_child_preexec(max_memory_bytes, cpu_seconds),
        start_new_session=True,  # own process group → kill the whole tree
        env=env,
    )
    if on_spawn is not None:
        on_spawn(proc.pid)

    try:
        out, _err = proc.communicate(input=data, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        raise DocumentParseTimeoutError("document parsing timed out") from None

    if proc.returncode != 0:
        # Nonzero exit or signal-kill (RLIMIT SIGKILL/SIGXCPU, os._exit, MemoryError
        # crash) → a clean structured error, never a raw 500.
        raise DocumentParseError("document parsing failed")

    return _build_document(out, content_type)


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    try:
        proc.communicate(timeout=5)  # reap; the child is dead, returns promptly
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()


def _build_document(out: bytes, content_type: str) -> ParsedDocument:
    try:
        payload = json.loads(out or b"null")
    except ValueError as e:
        raise DocumentParseError("document parser returned no valid result") from e
    if not isinstance(payload, dict):
        raise DocumentParseError("document parser returned a malformed result")
    if "error_class" in payload:
        exc = _ERROR_CLASS_MAP.get(str(payload["error_class"]), DocumentParseError)
        raise exc(str(payload.get("message") or "document parse failed"))
    blocks_raw = payload.get("blocks")
    if not isinstance(blocks_raw, list):
        raise DocumentParseError("document parser returned no blocks")
    blocks = [
        ParsedBlock(
            text=str(b["text"]),
            page=b.get("page"),
            section=b.get("section"),
            confidence=b.get("confidence"),
        )
        for b in blocks_raw
    ]
    extraction_method = str(payload.get("extraction_method") or "text")
    return ParsedDocument(
        content_type=content_type, blocks=blocks, extraction_method=extraction_method
    )
