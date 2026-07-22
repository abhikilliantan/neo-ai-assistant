"""Minimal parse child entry point (ADR 0003 slice 1).

Runs under `python -m app.ai.parsing.child <parser>`: imports only stdlib + the
parser registry, NOT the app, DB, or event loop (see `app.ai.parsing.__init__`).
Reads the document bytes from stdin, writes a JSON result to stdout, exit 0 —
even for a handled parse failure. A hang/OOM/abrupt-exit is left to the parent's
OS-level controls (timeout kill, RLIMIT); this entry point never tries to be
clever about them.
"""

from __future__ import annotations

import json
import os
import sys

from app.ai.parsing.protocol import ChildParseError


def _registry() -> dict[str, object]:
    reg: dict[str, object] = {}
    # Real parsers (DOCX, PDF) register here as later slices land — none yet.
    # Synthetic harness-exercisers are registered ONLY under the test flag, so
    # production never exposes them.
    if os.environ.get("NEO_PARSER_SYNTHETIC") == "1":
        from app.ai.parsing._synthetic import SYNTHETIC

        reg.update(SYNTHETIC)
    return reg


def _emit(obj: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    data = sys.stdin.buffer.read()
    parser = _registry().get(name)
    if parser is None:
        _emit({"error_class": "unsupported", "message": f"no parser named {name!r}"})
        return 0
    try:
        blocks = parser(data)  # type: ignore[operator]  # may hang / os._exit / allocate / raise
    except ChildParseError as e:
        _emit({"error_class": e.error_class, "message": str(e)})
        return 0
    _emit({"blocks": blocks})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
