"""Real parser for plain text (text/plain) and Markdown (text/markdown) — 8f-1.

Replaces the mock for these two formats only. PDF/DOCX remain unimplemented.

FIDELITY IS THE CONTRACT. `ParsedDocument.full_text` is defined as the blocks'
texts concatenated with no separators, and every citation offset indexes into
THAT string. So the blocks produced here TILE the decoded file gap-free and
without overlap: `"".join(b.text for b in blocks)` equals the decoded content
byte-for-byte (character-for-character). Nothing is normalized, stripped, or
line-ending-rewritten. A test asserts the round-trip rather than trusting it.

ENCODING. Try utf-8-sig, then utf-8. utf-8-sig skips a leading BOM if present
and otherwise decodes as plain utf-8. On failure we RAISE DocumentDecodeError
(→ 422) — we never fall back to a lossy codec, because a rejected upload beats
silently corrupted text the user can't see is wrong. A stripped BOM is an
encoding artifact, not content; everything after it is preserved exactly.

PARAGRAPH RULE (deterministic — implemented exactly as written):
  - A line is the text between '\n' terminators (we split ONLY on '\n', so a
    '\r' in a CRLF file stays part of the line's content and of full_text).
  - A line is BLANK if it is empty or contains only whitespace (space, tab,
    '\r', form-feed, …) — i.e. `line.strip() == ""`.
  - A PARAGRAPH is a maximal run of one or more consecutive non-blank lines.
    One or more consecutive blank lines act as a SINGLE paragraph separator.
  - Blocks tile the file: block i runs from paragraph i's first character to
    the first character of paragraph i+1 (the last block runs to end-of-file),
    so each separator's blank lines are absorbed into the PRECEDING block and
    any leading blank lines are absorbed into the FIRST block. Consequences:
    leading and trailing blank lines produce NO separate empty blocks, blank
    lines remain present in full_text, and paragraph detection never shifts an
    offset (boundaries are only ever paragraph starts).
  - Degenerate: a file with no non-blank lines but non-empty content yields a
    SINGLE block covering it (fidelity wins over block purity); a truly empty
    file (b"") yields zero blocks and full_text == "".

PAGES. `page` is always None — plain text and Markdown have no pages, and
DocumentPosition.render() falls back to character offsets.

SECTIONS (differ by format, deliberately):
  - text/markdown: `section` is the nearest preceding ATX heading (`#`..`######`
    followed by a space), taken at the block's FIRST line (so a heading that
    opens a block labels that block). Headings with empty title text do not set
    a section. A block before any heading has section=None.
  - text/plain: `section` is ALWAYS None. We NEVER infer headings from short
    lines, capitalization, or trailing colons — plain text carries no heading
    semantics, and inferring it produces confident, wrong citations.
"""

from __future__ import annotations

import re

from app.application.ports.documents import ParsedBlock, ParsedDocument
from app.shared.exceptions.documents import DocumentDecodeError, DocumentTooLargeError

_MARKDOWN = "text/markdown"

# ATX heading: 0-3 leading spaces, 1-6 '#', then a space+title or end-of-line.
# "#no-space" and 7+ '#' are NOT headings (CommonMark). Group 1 is the raw title.
_ATX = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(.*))?$")
# A trailing ATX closing sequence ("# Title ##") — only stripped when the '#'
# run is preceded by whitespace, so a title like "C#" keeps its '#'.
_ATX_CLOSE = re.compile(r"(?:^|[ \t])#+[ \t]*$")


def _atx_title(line: str) -> str | None:
    """The heading title if `line` is an ATX heading, else None. Returns "" for
    a title-less heading (e.g. "##"); the caller ignores empty titles."""
    m = _ATX.match(line)
    if m is None:
        return None
    title = (m.group(1) or "").rstrip()
    title = _ATX_CLOSE.sub("", title).rstrip()
    return title


def _decode(data: bytes) -> str:
    for codec in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(codec)
        except UnicodeDecodeError:
            continue
    raise DocumentDecodeError("document is not valid UTF-8 text")


def _iter_lines(text: str) -> list[tuple[int, int]]:
    """(start, content_end) for each line, splitting only on '\\n'. content_end
    excludes the '\\n'. A trailing '\\n' yields a final empty line."""
    lines: list[tuple[int, int]] = []
    start = 0
    n = len(text)
    while start <= n:
        nl = text.find("\n", start)
        if nl == -1:
            lines.append((start, n))
            break
        lines.append((start, nl))
        start = nl + 1
    return lines


class TextDocumentParser:
    """Parses text/plain and text/markdown per the module docstring."""

    def __init__(self, *, max_bytes: int) -> None:
        self._max_bytes = max_bytes

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument:
        if len(data) > self._max_bytes:
            raise DocumentTooLargeError(
                f"document exceeds max_bytes ({len(data)} > {self._max_bytes})"
            )
        full_text = _decode(data)
        if not full_text:
            return ParsedDocument(content_type=content_type, blocks=[])

        is_markdown = content_type.split(";")[0].strip().lower() == _MARKDOWN

        # One pass: find each paragraph's start offset + the section in effect
        # at its first line (headings update the running section as we go).
        para_starts: list[int] = []
        para_sections: list[str | None] = []
        current_section: str | None = None
        in_para = False
        for start, end in _iter_lines(full_text):
            line = full_text[start:end]
            if is_markdown:
                title = _atx_title(line)
                if title:  # non-empty title sets the section
                    current_section = title
            if line.strip() == "":
                in_para = False
            elif not in_para:
                para_starts.append(start)
                para_sections.append(current_section)
                in_para = True

        if not para_starts:
            # No non-blank lines but non-empty content — keep the bytes so
            # full_text fidelity holds.
            return ParsedDocument(
                content_type=content_type,
                blocks=[ParsedBlock(text=full_text, page=None, section=None)],
            )

        # Tile: block i spans [start_i, start_{i+1}); first block pinned to 0
        # (absorb leading blanks), last runs to end (absorb trailing blanks).
        starts = [0, *para_starts[1:]]
        ends = [*starts[1:], len(full_text)]
        blocks = [
            ParsedBlock(text=full_text[s:e], page=None, section=sec)
            for s, e, sec in zip(starts, ends, para_sections, strict=True)
        ]
        return ParsedDocument(content_type=content_type, blocks=blocks)
