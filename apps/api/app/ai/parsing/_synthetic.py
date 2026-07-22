"""Synthetic child parsers that EXERCISE the isolation harness (ADR 0003 slice 1).

These are NOT shipped document parsers — they exist to prove the harness's process
controls (timeout kill, memory kill, clean failure mapping, offset round-trip).
They are registered in the child ONLY when `NEO_PARSER_SYNTHETIC=1` (tests set it),
so production never exposes them. Pure stdlib; runs inside the sandboxed child.
"""

from __future__ import annotations

import mmap
import os
import time

from app.ai.parsing.protocol import ChildParseError


def _echo(data: bytes) -> list[dict[str, object]]:
    """Emit two blocks whose texts concatenate EXACTLY to the decoded input, so the
    parent's `full_text = "".join(block.text)` round-trips byte-for-byte."""
    text = data.decode("utf-8", "replace")
    mid = len(text) // 2
    return [
        {"text": text[:mid], "page": 1, "section": "one"},
        {"text": text[mid:], "page": 2, "section": "two"},
    ]


def _hang(data: bytes) -> list[dict[str, object]]:
    """Sleep forever → killed by the parent's WALL-CLOCK timeout (RLIMIT_CPU never
    fires because sleeping burns no CPU). This is the real-timeout proof."""
    del data
    while True:
        time.sleep(3600)


def _oom(data: bytes) -> list[dict[str, object]]:
    """Reserve virtual address space without bound → trips RLIMIT_AS fast (mmap
    reservations count against the address-space cap without committing pages, so
    the kill is near-instant). Confined to the child; the parent survives."""
    del data
    hog: list[mmap.mmap] = []
    while True:
        hog.append(mmap.mmap(-1, 100_000_000))  # 100 MB of address space per iteration


def _boom(data: bytes) -> list[dict[str, object]]:
    """A HANDLED parse failure → structured {error_class} JSON, exit 0."""
    del data
    raise ChildParseError("synthetic handled parse failure", error_class="parse_error")


def _exit(data: bytes) -> list[dict[str, object]]:
    """Abrupt nonzero exit, no output → parent maps to 'parse failed'."""
    del data
    os._exit(7)


SYNTHETIC: dict[str, object] = {
    "echo": _echo,
    "hang": _hang,
    "oom": _oom,
    "boom": _boom,
    "exit": _exit,
}
