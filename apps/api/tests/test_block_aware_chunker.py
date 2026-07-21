"""ADR 0001 — BlockAwareChunker unit tests.

The load-bearing invariant is the same as the parser's: offsets are exact and
gap-free. Here that means every chunk's text equals `full_text[start:end]` and
the chunks together cover the whole document — proven, not trusted. Overlap,
oversized-block fallback, section handling, the 60% section-break threshold,
determinism, and the edge cases from ADR Decision 10 each get a case.
"""

from __future__ import annotations

import pytest

from app.ai.documents.block_aware import BlockAwareChunker
from app.ai.documents.chunker import FixedSizeChunker
from app.application.ports.documents import ParsedBlock, ParsedDocument


def _doc(*blocks: ParsedBlock, content_type: str = "text/plain") -> ParsedDocument:
    return ParsedDocument(content_type=content_type, blocks=list(blocks))


def _assert_offsets_and_coverage(chunks, full: str) -> None:
    """Every chunk text == full[start:end]; union of ranges covers [0, len)."""
    covered = [False] * len(full)
    for c in chunks:
        s, e = c.position.char_start, c.position.char_end
        assert full[s:e] == c.text  # offset round-trip
        for k in range(s, e):
            covered[k] = True
    assert all(covered), "chunks must cover every character of full_text"
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))  # 0..n-1


# --- packing + offset exactness ---------------------------------------------


def test_packs_whole_blocks_and_offsets_round_trip() -> None:
    doc = _doc(
        ParsedBlock(text="A" * 400),
        ParsedBlock(text="B" * 400),
        ParsedBlock(text="C" * 400),
    )
    chunks = BlockAwareChunker(chunk_size=1000, overlap=0).chunk(document_id="d", document=doc)
    _assert_offsets_and_coverage(chunks, doc.full_text)
    # 400+400=800 fits; +400 exceeds 1000 → [A+B], [C]. Boundaries on block edges.
    assert [(c.position.char_start, c.position.char_end) for c in chunks] == [(0, 800), (800, 1200)]
    assert chunks[0].text == "A" * 400 + "B" * 400


def test_block_exactly_chunk_size_is_its_own_chunk() -> None:
    doc = _doc(ParsedBlock(text="A" * 100), ParsedBlock(text="B" * 100))
    chunks = BlockAwareChunker(chunk_size=100, overlap=0).chunk(document_id="d", document=doc)
    _assert_offsets_and_coverage(chunks, doc.full_text)
    assert [(c.position.char_start, c.position.char_end) for c in chunks] == [(0, 100), (100, 200)]


# --- overlap: whole-block carry ---------------------------------------------


def test_overlap_carries_whole_trailing_block_within_budget() -> None:
    doc = _doc(
        ParsedBlock(text="A" * 400),
        ParsedBlock(text="B" * 400),
        ParsedBlock(text="C" * 400),
    )
    # chunk0 = A+B [0,800). Budget 450 carries whole block B (400<=450) but not A.
    chunks = BlockAwareChunker(chunk_size=1000, overlap=450).chunk(document_id="d", document=doc)
    _assert_offsets_and_coverage(chunks, doc.full_text)
    assert chunks[1].position.char_start == 400  # carried block B precedes fresh C
    assert chunks[1].text == "B" * 400 + "C" * 400


# --- oversized block: fixed-window fallback within that block ----------------


def test_oversized_block_falls_back_to_fixed_window() -> None:
    doc = _doc(ParsedBlock(text="X" * 250, section="S"))
    chunks = BlockAwareChunker(chunk_size=100, overlap=20).chunk(document_id="d", document=doc)
    _assert_offsets_and_coverage(chunks, doc.full_text)
    # stride 80 → [0,100),[80,180),[160,250)
    assert [(c.position.char_start, c.position.char_end) for c in chunks] == [
        (0, 100),
        (80, 180),
        (160, 250),
    ]
    assert all(c.position.section == "S" for c in chunks)  # sub-chunks keep the block's section


def test_oversized_block_between_packed_groups() -> None:
    doc = _doc(
        ParsedBlock(text="Y" * 50),
        ParsedBlock(text="X" * 250),
        ParsedBlock(text="Z" * 30),
    )
    chunks = BlockAwareChunker(chunk_size=100, overlap=20).chunk(document_id="d", document=doc)
    _assert_offsets_and_coverage(chunks, doc.full_text)
    # Y is its own chunk; X windows into 3; Z its own chunk (no carry across the
    # oversized block).
    assert chunks[0].text == "Y" * 50
    assert chunks[-1].text == "Z" * 30


# --- section handling (Markdown) --------------------------------------------


def test_section_break_preferred_past_threshold() -> None:
    # 70 chars in S1 (>= 60% of 100) then S2 → break at the section boundary.
    doc = _doc(
        ParsedBlock(text="A" * 70, section="S1"),
        ParsedBlock(text="B" * 20, section="S2"),
    )
    chunks = BlockAwareChunker(chunk_size=100, overlap=0).chunk(document_id="d", document=doc)
    _assert_offsets_and_coverage(chunks, doc.full_text)
    assert [c.position.section for c in chunks] == ["S1", "S2"]


def test_section_change_below_threshold_packs_across_and_nulls_section() -> None:
    # Only 50 chars (< 60% of 100) before the section change → pack across; a
    # chunk whose fresh blocks span two sections reports section=None (Decision 5).
    doc = _doc(
        ParsedBlock(text="A" * 50, section="S1"),
        ParsedBlock(text="B" * 20, section="S2"),
    )
    chunks = BlockAwareChunker(chunk_size=100, overlap=0).chunk(document_id="d", document=doc)
    _assert_offsets_and_coverage(chunks, doc.full_text)
    assert len(chunks) == 1
    assert chunks[0].position.section is None


def test_single_section_chunk_keeps_its_section() -> None:
    doc = _doc(
        ParsedBlock(text="head", section="S1"),
        ParsedBlock(text="body" * 5, section="S1"),
    )
    chunks = BlockAwareChunker(chunk_size=1000, overlap=0).chunk(document_id="d", document=doc)
    assert len(chunks) == 1
    assert chunks[0].position.section == "S1"


# --- pages (first/last block) -----------------------------------------------


def test_page_start_end_from_first_and_last_block() -> None:
    doc = _doc(
        ParsedBlock(text="p1", page=1),
        ParsedBlock(text="p2", page=2),
    )
    chunks = BlockAwareChunker(chunk_size=1000, overlap=0).chunk(document_id="d", document=doc)
    assert (chunks[0].position.page_start, chunks[0].position.page_end) == (1, 2)


# --- determinism ------------------------------------------------------------


def test_deterministic() -> None:
    doc = _doc(*(ParsedBlock(text=chr(65 + i) * 137, section=f"S{i % 3}") for i in range(10)))
    c = BlockAwareChunker(chunk_size=500, overlap=100)
    a = c.chunk(document_id="d", document=doc)
    b = c.chunk(document_id="d", document=doc)
    assert [(x.ordinal, x.text, x.position.model_dump()) for x in a] == [
        (x.ordinal, x.text, x.position.model_dump()) for x in b
    ]


# --- edge cases -------------------------------------------------------------


def test_empty_document_yields_no_chunks() -> None:
    assert (
        BlockAwareChunker(chunk_size=100, overlap=0).chunk(document_id="d", document=_doc()) == []
    )


def test_single_small_block() -> None:
    doc = _doc(ParsedBlock(text="hi", section="S"))
    chunks = BlockAwareChunker(chunk_size=1000, overlap=0).chunk(document_id="d", document=doc)
    assert len(chunks) == 1
    assert chunks[0].text == "hi"
    assert (chunks[0].position.char_start, chunks[0].position.char_end) == (0, 2)


def test_construction_rejects_bad_overlap() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        BlockAwareChunker(chunk_size=0, overlap=0)
    with pytest.raises(ValueError, match="overlap"):
        BlockAwareChunker(chunk_size=100, overlap=100)


# --- provenance id ----------------------------------------------------------


def test_chunker_ids() -> None:
    assert BlockAwareChunker(chunk_size=100, overlap=0).chunker_id == "block-aware-1"
    assert FixedSizeChunker(chunk_size=100, overlap=0).chunker_id == "fixed-1"
