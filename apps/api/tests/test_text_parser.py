"""Phase 8f-1 — real parser for text/plain + text/markdown.

The load-bearing property is FIDELITY: `"".join(block.text)` == the decoded file
exactly, and every block's text round-trips against full_text at its offset. The
places offset drift hides — doubled blank-line separators and trailing blank
lines — get explicit coverage, as does the deliberate txt-vs-md section split.
"""

from __future__ import annotations

import pytest

from app.ai.documents.text import TextDocumentParser
from app.application.ports.documents import ParsedDocument
from app.shared.exceptions.documents import DocumentDecodeError, DocumentTooLargeError

_TXT = "text/plain"
_MD = "text/markdown"


def _parser() -> TextDocumentParser:
    return TextDocumentParser(max_bytes=1_000_000)


def _assert_tiling(doc: ParsedDocument, decoded: str) -> None:
    """full_text == decoded, and blocks tile it gap-free with exact offsets."""
    assert doc.full_text == decoded  # join(block.text) == the file, exactly
    pos = 0
    for block in doc.blocks:
        assert doc.full_text[pos : pos + len(block.text)] == block.text
        pos += len(block.text)
    assert pos == len(decoded)  # no gaps, no overlap, nothing dropped


# --- fidelity / offset round-trip -------------------------------------------


@pytest.mark.asyncio
async def test_offsets_round_trip_against_full_text() -> None:
    decoded = "First paragraph line one.\nline two.\n\nSecond paragraph.\n"
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_TXT)
    _assert_tiling(doc, decoded)
    assert len(doc.blocks) == 2
    assert doc.blocks[1].text == "Second paragraph.\n"  # last block absorbs trailing \n


@pytest.mark.asyncio
async def test_crlf_line_endings_are_preserved_not_rewritten() -> None:
    decoded = "alpha\r\nbeta\r\n\r\ngamma"  # CRLF must survive verbatim
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_TXT)
    _assert_tiling(doc, decoded)
    assert "\r\n" in doc.full_text


# --- encoding: BOM + failure ------------------------------------------------


@pytest.mark.asyncio
async def test_utf8_without_bom() -> None:
    decoded = "héllo — utf8 ✓\n"
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_TXT)
    _assert_tiling(doc, decoded)


@pytest.mark.asyncio
async def test_utf8_with_bom_is_stripped_and_body_preserved() -> None:
    decoded = "héllo — utf8 ✓\n"
    with_bom = b"\xef\xbb\xbf" + decoded.encode("utf-8")
    doc = await _parser().parse(data=with_bom, content_type=_TXT)
    # BOM (an encoding artifact) is gone; everything after it is exact.
    assert doc.full_text == decoded
    assert not doc.full_text.startswith("﻿")
    _assert_tiling(doc, decoded)


@pytest.mark.asyncio
async def test_invalid_utf8_raises_decode_error_not_lossy_fallback() -> None:
    # 0xFF is never valid UTF-8; must reject (→ 422 via DocumentParseError base).
    with pytest.raises(DocumentDecodeError):
        await _parser().parse(data=b"ok then \xff\xfe bad", content_type=_TXT)


# --- paragraph boundaries: separators + trailing blanks ---------------------


@pytest.mark.asyncio
async def test_consecutive_blank_lines_are_a_single_separator() -> None:
    decoded = "A\n\n\n\nB"  # 3 blank lines between → still one boundary
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_TXT)
    _assert_tiling(doc, decoded)
    assert len(doc.blocks) == 2
    assert doc.blocks[0].text == "A\n\n\n\n"  # separator absorbed into block 0
    assert doc.blocks[1].text == "B"


@pytest.mark.asyncio
async def test_leading_and_trailing_blank_lines_produce_no_empty_blocks() -> None:
    decoded = "\n\nonly paragraph\n\n\n"
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_TXT)
    _assert_tiling(doc, decoded)
    assert len(doc.blocks) == 1  # leading + trailing blanks fold into the block
    assert doc.blocks[0].text == decoded
    assert all(b.text.strip() != "" for b in doc.blocks)  # no blank/empty blocks


@pytest.mark.asyncio
async def test_whitespace_only_lines_count_as_blank() -> None:
    decoded = "para one\n   \t \npara two\n"  # middle line is whitespace-only
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_TXT)
    _assert_tiling(doc, decoded)
    assert len(doc.blocks) == 2


# --- empty file -------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_file_yields_no_blocks_and_empty_full_text() -> None:
    doc = await _parser().parse(data=b"", content_type=_TXT)
    assert doc.blocks == []
    assert doc.full_text == ""


# --- markdown sections ------------------------------------------------------


@pytest.mark.asyncio
async def test_markdown_section_is_nearest_preceding_atx_heading() -> None:
    decoded = (
        "intro before any heading\n"
        "\n"
        "# Chapter One\n"
        "\n"
        "body under chapter one\n"
        "\n"
        "## Sub A\n"
        "\n"
        "body under sub a\n"
    )
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_MD)
    _assert_tiling(doc, decoded)
    by_text = {b.text.strip(): b.section for b in doc.blocks}
    assert by_text["intro before any heading"] is None  # before any heading
    assert by_text["# Chapter One"] == "Chapter One"  # heading labels its own block
    assert by_text["body under chapter one"] == "Chapter One"
    assert by_text["## Sub A"] == "Sub A"
    assert by_text["body under sub a"] == "Sub A"


@pytest.mark.asyncio
async def test_markdown_non_heading_hashes_do_not_set_section() -> None:
    # "#no-space" is not an ATX heading; "C#" keeps its trailing '#'.
    decoded = "#notaheading still body\n\n## Real ##\n\nunder real\n"
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_MD)
    _assert_tiling(doc, decoded)
    by_text = {b.text.strip(): b.section for b in doc.blocks}
    assert by_text["#notaheading still body"] is None
    assert by_text["under real"] == "Real"  # closing '##' stripped


# --- plain text: NEVER infers sections --------------------------------------


@pytest.mark.asyncio
async def test_plain_text_never_infers_sections() -> None:
    # Lines that look like headings/titles in prose must NOT become sections.
    decoded = "# Looks Like Markdown\n\nSHOUTING TITLE\n\nTrailing colon:\n\nactual body\n"
    doc = await _parser().parse(data=decoded.encode("utf-8"), content_type=_TXT)
    _assert_tiling(doc, decoded)
    assert all(b.section is None for b in doc.blocks)  # plain text has no headings


# --- max_bytes guard (contract parity with the mock) ------------------------


@pytest.mark.asyncio
async def test_enforces_max_bytes() -> None:
    parser = TextDocumentParser(max_bytes=4)
    with pytest.raises(DocumentTooLargeError):
        await parser.parse(data=b"way too many bytes", content_type=_TXT)
