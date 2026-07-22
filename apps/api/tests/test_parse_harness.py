"""ADR 0003 slice 1, commit 1 — the subprocess parse-isolation harness.

Proves the PROCESS CONTROLS with synthetic children (no real DOCX/PDF code): a
hung parse is killed at the wall-clock timeout, an unbounded allocation is killed
by RLIMIT_AS, a handled failure and an abrupt exit map to structured errors, the
echo child round-trips bytes with exact offsets, and concurrent parses don't
interfere. The load-bearing kills (timeout, RLIMIT_AS) are Linux-only — the ADR
documents macOS host as unsupported for real parsing — so this whole module is
skipped off Linux and executed in the Linux api container.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest

from app.ai.parsing.harness import parse_in_subprocess
from app.shared.exceptions.documents import (
    DocumentParseError,
    DocumentParseTimeoutError,
)

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="RLIMIT_AS/timeout kill are Linux-only; ADR 0003 marks macOS host unsupported",
)

_SYN = {"NEO_PARSER_SYNTHETIC": "1"}  # register the synthetic exercisers in the child
_CT = "application/octet-stream"


# --- echo: bytes → blocks, offsets exact against full_text -------------------


@pytest.mark.asyncio
async def test_echo_round_trips_bytes_with_exact_offsets() -> None:
    data = "héllo wörld — original bytes\nsecond line ✓".encode()
    doc = await parse_in_subprocess(parser="echo", data=data, content_type=_CT, child_env=_SYN)

    full = doc.full_text
    assert full == data.decode()  # echo's blocks concatenate to the input exactly
    # Offset round-trip / gap-free tiling: full_text[start:end] == block.text.
    pos = 0
    for b in doc.blocks:
        assert full[pos : pos + len(b.text)] == b.text
        pos += len(b.text)
    assert pos == len(full)
    # page/section survive the JSON boundary.
    assert [(b.page, b.section) for b in doc.blocks] == [(1, "one"), (2, "two")]


# --- hang: killed at the wall-clock timeout (THE real-timeout proof) ----------


@pytest.mark.asyncio
async def test_hang_is_killed_at_timeout_without_blocking_the_loop() -> None:
    timeout = 1.5
    pids: list[int] = []
    ticks: list[float] = []

    async def hanger() -> None:
        with pytest.raises(DocumentParseTimeoutError):
            await parse_in_subprocess(
                parser="hang",
                data=b"x",
                content_type=_CT,
                timeout_seconds=timeout,
                child_env=_SYN,
                on_spawn=pids.append,
            )

    async def ticker() -> None:
        # If the event loop were blocked by the hang, these ticks would bunch up at
        # the end; instead they spread evenly and finish before the hang times out.
        for _ in range(10):
            await asyncio.sleep(0.1)
            ticks.append(time.monotonic())

    start = time.monotonic()
    await asyncio.gather(hanger(), ticker())
    elapsed = time.monotonic() - start

    assert len(ticks) == 10  # the loop kept running during the hang
    assert ticks[-1] - start < timeout  # ticker finished (~1.0s) BEFORE the 1.5s timeout
    assert timeout <= elapsed < timeout + 4  # killed at ~timeout, not forever
    # No child left running: the process group was SIGKILL'd and reaped.
    with pytest.raises(ProcessLookupError):
        os.kill(pids[-1], 0)


# --- oom: killed by RLIMIT_AS, parent survives -------------------------------


@pytest.mark.asyncio
async def test_oom_is_killed_by_rlimit_and_parent_survives() -> None:
    with pytest.raises(DocumentParseError) as ei:
        await parse_in_subprocess(
            parser="oom",
            data=b"x",
            content_type=_CT,
            max_memory_bytes=700 * 1024 * 1024,  # child starts, alloc loop exhausts it fast
            timeout_seconds=15.0,  # generous, so it's the memory cap that fires, not the timer
            child_env=_SYN,
        )
    assert not isinstance(ei.value, DocumentParseTimeoutError)  # a memory kill, not a timeout
    # The parent survived: a fresh parse still works.
    doc = await parse_in_subprocess(parser="echo", data=b"ok", content_type=_CT, child_env=_SYN)
    assert doc.full_text == "ok"


# --- handled failure + abrupt exit → structured errors -----------------------


@pytest.mark.asyncio
async def test_boom_maps_handled_failure_to_structured_error() -> None:
    with pytest.raises(DocumentParseError) as ei:
        await parse_in_subprocess(parser="boom", data=b"x", content_type=_CT, child_env=_SYN)
    assert not isinstance(ei.value, DocumentParseTimeoutError)
    assert "synthetic handled parse failure" in str(ei.value)  # child message surfaced


@pytest.mark.asyncio
async def test_nonzero_exit_maps_to_structured_parse_failure() -> None:
    with pytest.raises(DocumentParseError) as ei:
        await parse_in_subprocess(parser="exit", data=b"x", content_type=_CT, child_env=_SYN)
    assert not isinstance(ei.value, DocumentParseTimeoutError)


# --- concurrency: spawn-per-parse, no shared state ---------------------------


@pytest.mark.asyncio
async def test_concurrent_parses_do_not_interfere() -> None:
    inputs = [f"document-number-{i}".encode() for i in range(8)]
    docs = await asyncio.gather(
        *[
            parse_in_subprocess(parser="echo", data=d, content_type=_CT, child_env=_SYN)
            for d in inputs
        ]
    )
    for d_in, doc in zip(inputs, docs, strict=True):
        assert doc.full_text == d_in.decode()  # each got exactly its own input
