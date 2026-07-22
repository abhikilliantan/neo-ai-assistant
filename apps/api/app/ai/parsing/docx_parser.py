"""Real DOCX parser — runs INSIDE the isolation child (ADR 0003 slice 1, DOCX).

Because it runs in the child spawned by `parse_in_subprocess`, every DOCX parse
inherits the 30 s wall-clock timeout and the 1 GiB RLIMIT_AS from the harness.
On top of that, this module enforces the DOCX-specific defenses in the child:

1. DECOMPRESSED-SIZE CAP (zip-bomb defense): sum the members' uncompressed sizes
   from the ZIP central directory (metadata only, no decompression) and abort if
   over `NEO_DOCX_MAX_DECOMPRESSED` (200 MiB default). RLIMIT_AS is the backstop
   for a ZIP that lies about its sizes.
2. XXE / ENTITY-EXPANSION DEFENSE: every XML/rels member is validated with
   defusedxml (`forbid_dtd`, `forbid_entities`, `forbid_external` — defusedxml's
   defaults) BEFORE python-docx opens the file. A DTD, an entity definition, or an
   external reference raises and the document is rejected — so entity expansion is
   disabled regardless of how the XML is later read. (python-docx's own lxml parser
   additionally uses `resolve_entities=False`, verified for python-docx 1.2, as
   defense-in-depth.)

Extraction: one block per non-empty paragraph; `page = None` (DOCX paginates at
render time, not in the file); `section` = the nearest preceding heading taken
from the EXPLICIT built-in heading style (`Heading1`..`Heading9`) — never font
size or other formatting heuristics. Offsets are computed parent-side by the
harness (`full_text = "".join(block.text)`), so the round-trip invariant holds.

Pure parser dependencies (python-docx, defusedxml, stdlib zipfile) — no app/DB.
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from typing import Any

from app.ai.parsing.protocol import ChildParseError

_DEFAULT_MAX_DECOMPRESSED = 200 * 1024 * 1024  # 200 MiB (ADR 0003 resolved OQ2)
_HEADING_STYLE_ID = re.compile(r"^Heading[1-9]$")  # built-in "Heading1".."Heading9"


def _max_decompressed() -> int:
    raw = os.environ.get("NEO_DOCX_MAX_DECOMPRESSED")
    return int(raw) if raw and raw.isdigit() else _DEFAULT_MAX_DECOMPRESSED


def _heading_if_heading(paragraph: Any) -> str | None:
    # EXPLICIT heading style only (style_id is locale-independent) — never font size.
    style_id = getattr(getattr(paragraph, "style", None), "style_id", None) or ""
    return paragraph.text if _HEADING_STYLE_ID.match(style_id) else None


def parse_docx(data: bytes) -> list[dict[str, object]]:
    # 1. Open the ZIP + decompressed-size cap (metadata only).
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ChildParseError(
            "not a valid Word document (corrupt or not a .docx)", error_class="parse_error"
        ) from e
    total_uncompressed = sum(info.file_size for info in zf.infolist())
    if total_uncompressed > _max_decompressed():
        raise ChildParseError(
            f"document decompresses to {total_uncompressed} bytes, over the limit",
            error_class="too_large",
        )

    # 2. Validate every XML member with defusedxml BEFORE python-docx parses.
    from defusedxml.common import DefusedXmlException
    from defusedxml.ElementTree import ParseError, fromstring

    for info in zf.infolist():
        if info.filename.endswith((".xml", ".rels")):
            raw = zf.read(info)  # bounded by the cap above + RLIMIT_AS
            try:
                fromstring(raw)  # defusedxml defaults forbid DTD/entities/external refs
            except DefusedXmlException as e:
                raise ChildParseError(
                    "document XML uses a forbidden DTD/entity", error_class="parse_error"
                ) from e
            except ParseError as e:
                raise ChildParseError(
                    "document contains malformed XML", error_class="parse_error"
                ) from e

    # 3. Extract paragraphs via python-docx (parser also has resolve_entities=False).
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    try:
        document = Document(io.BytesIO(data))
    except PackageNotFoundError as e:
        raise ChildParseError(
            "not a valid Word document (it may be corrupt or password-protected)",
            error_class="parse_error",
        ) from e

    blocks: list[dict[str, object]] = []
    current_section: str | None = None
    for para in document.paragraphs:
        heading = _heading_if_heading(para)
        if heading is not None:
            current_section = heading
        text = para.text
        if text == "":
            continue  # skip empty paragraphs → an empty-but-valid doc yields 0 blocks
        blocks.append({"text": text + "\n", "page": None, "section": current_section})
    return blocks
