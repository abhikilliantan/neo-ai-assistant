"""ADR 0004 slice 1 — OCR provenance plumbing (hermetic, no tesseract binary).

Proves the VO/chunker/render path carries OCR provenance end-to-end without
needing the OCR binary: extraction_method flows to is_ocr, per-word confidence
aggregates to per-chunk ocr_confidence, and render() marks OCR citations "(OCR)"
while native-text citations are untouched.
"""

from __future__ import annotations

from app.ai.documents.block_aware import BlockAwareChunker
from app.ai.documents.chunker import FixedSizeChunker
from app.application.ports.documents import DocumentPosition, ParsedBlock, ParsedDocument


def _ocr_doc() -> ParsedDocument:
    return ParsedDocument(
        content_type="application/pdf",
        extraction_method="ocr",
        blocks=[
            ParsedBlock(text="alpha beta gamma\n", page=1, section=None, confidence=90.0),
            ParsedBlock(text="delta epsilon zeta\n", page=2, section=None, confidence=80.0),
        ],
    )


def _text_doc() -> ParsedDocument:
    return ParsedDocument(
        content_type="application/pdf",
        blocks=[ParsedBlock(text="alpha beta\n", page=1, section=None)],
    )


def test_render_appends_ocr_marker_only_when_ocr() -> None:
    one_page = DocumentPosition(char_start=0, char_end=3, page_start=2, is_ocr=True)
    assert one_page.render() == "p. 2 (OCR)"
    span = DocumentPosition(char_start=0, char_end=3, page_start=2, page_end=3, is_ocr=True)
    assert span.render() == "pp. 2-3 (OCR)"
    # Native text — unchanged, no marker.
    assert DocumentPosition(char_start=0, char_end=3, page_start=2).render() == "p. 2"
    assert DocumentPosition(char_start=0, char_end=3, section="X").render() == "section X"


def test_block_aware_aggregates_confidence_and_marks_ocr() -> None:
    chunks = BlockAwareChunker(chunk_size=10_000, overlap=0).chunk(
        document_id="d", document=_ocr_doc()
    )
    assert len(chunks) == 1  # both blocks pack into one chunk
    chunk = chunks[0]
    assert chunk.ocr_confidence == 85.0  # mean(90, 80)
    assert chunk.position.is_ocr is True
    assert chunk.position.render().endswith("(OCR)")


def test_fixed_chunker_marks_ocr_and_carries_doc_confidence() -> None:
    chunks = FixedSizeChunker(chunk_size=10_000, overlap=0).chunk(
        document_id="d", document=_ocr_doc()
    )
    assert chunks[0].ocr_confidence == 85.0
    assert chunks[0].position.is_ocr is True


def test_text_document_has_no_ocr_marker_or_confidence() -> None:
    for chunker in (
        BlockAwareChunker(chunk_size=10_000, overlap=0),
        FixedSizeChunker(chunk_size=10_000, overlap=0),
    ):
        chunks = chunker.chunk(document_id="d", document=_text_doc())
        assert chunks[0].ocr_confidence is None
        assert chunks[0].position.is_ocr is False
        assert "(OCR)" not in chunks[0].position.render()


def test_parsed_document_extraction_method_defaults_to_text() -> None:
    assert _text_doc().extraction_method == "text"
