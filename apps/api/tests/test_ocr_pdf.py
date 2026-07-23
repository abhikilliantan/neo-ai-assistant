"""ADR 0004 slice 1 — real OCR through the isolation harness (Linux + tesseract).

Runs the actual rasterize→Tesseract path in the parse child, so — like
test_pdf_parser / test_parse_harness — it needs the Linux subprocess harness AND
the tesseract binary. Skipped on the macOS host and on any Linux without tesseract
(so CI without the binary skips cleanly); it runs in the api container.

Scanned-PDF fixtures are generated with Pillow (text → image → image-only PDF),
which is a genuine scan for extraction purposes: zero text layer.
"""

from __future__ import annotations

import io
import shutil
import sys

import pytest

from app.ai.documents.block_aware import BlockAwareChunker
from app.ai.documents.pdf import PDF_CONTENT_TYPE
from app.ai.parsing.harness import parse_in_subprocess
from app.application.ports.documents import ParsedDocument
from app.shared.exceptions.documents import DocumentParseError

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or shutil.which("tesseract") is None,
    reason="OCR needs the Linux harness + the tesseract binary (runs in the api container)",
)


# --- scanned-PDF fixtures (Pillow: text → image → image-only PDF) --------------


def _text_image(lines: list[str], *, width: int = 1400, font_size: int = 44):  # type: ignore[no-untyped-def]
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default(size=font_size)
    line_h = font_size + 20
    height = max(200, 40 * 2 + line_h * len(lines))
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = 40
    for line in lines:
        draw.text((40, y), line, fill="black", font=font)
        y += line_h
    return img


def _blank_image(*, width: int = 1400, height: int = 400):  # type: ignore[no-untyped-def]
    from PIL import Image

    return Image.new("RGB", (width, height), "white")  # no text layer → unreadable


def _scanned_pdf(page_images: list) -> bytes:  # type: ignore[no-untyped-def]
    buf = io.BytesIO()
    first, *rest = page_images
    first.save(buf, format="PDF", save_all=True, append_images=rest, resolution=200.0)
    return buf.getvalue()


async def _ocr(
    data: bytes, *, enabled: bool = True, max_pages: int = 15, min_conf: float = 60.0
) -> ParsedDocument:
    env: dict[str, str] = {}
    if enabled:
        env = {
            "NEO_OCR_ENABLED": "1",
            "NEO_OCR_MAX_PAGES": str(max_pages),
            "NEO_OCR_MIN_CONFIDENCE": str(min_conf),
        }
    return await parse_in_subprocess(
        parser="pdf",
        data=data,
        content_type=PDF_CONTENT_TYPE,
        timeout_seconds=90.0,
        child_env=env,
    )


# --- the OCR path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_scanned_pdf_is_ocred_with_pages_confidence_and_ocr_citation() -> None:
    pdf = _scanned_pdf(
        [
            _text_image(["Annual leave entitlement is", "26 days per calendar year."]),
            _text_image(["Compassionate leave of up to", "five days at full pay."]),
        ]
    )
    doc = await _ocr(pdf)

    assert doc.extraction_method == "ocr"
    assert [b.page for b in doc.blocks] == [1, 2]  # real 1-based page numbers, in order
    assert all(b.section is None for b in doc.blocks)  # PDF encodes no reliable sections
    assert all(b.confidence is not None and b.confidence >= 60.0 for b in doc.blocks)
    # OCR actually recovered the text (allow for minor OCR noise).
    full = doc.full_text.lower()
    assert "leave" in full and "days" in full
    # Offset round-trip holds on the OCR-reconstructed text.
    pos = 0
    for b in doc.blocks:
        assert doc.full_text[pos : pos + len(b.text)] == b.text
        pos += len(b.text)

    # A chunk of this OCR doc cites "(OCR)".
    chunks = BlockAwareChunker(chunk_size=10_000, overlap=0).chunk(document_id="d", document=doc)
    assert chunks and chunks[0].position.render().endswith("(OCR)")
    assert chunks[0].ocr_confidence is not None


@pytest.mark.asyncio
async def test_over_page_cap_rejected_honestly() -> None:
    pdf = _scanned_pdf([_text_image([f"page {i}"]) for i in range(1, 17)])  # 16 pages
    with pytest.raises(DocumentParseError) as ei:
        await _ocr(pdf, max_pages=15)
    assert "too large to OCR" in str(ei.value)


@pytest.mark.asyncio
async def test_all_unreadable_scan_rejected_no_usable_text() -> None:
    pdf = _scanned_pdf([_blank_image(), _blank_image()])  # no text on any page
    with pytest.raises(DocumentParseError):
        await _ocr(pdf)


@pytest.mark.asyncio
async def test_mixed_scan_drops_bad_page_keeps_good_pages() -> None:
    pdf = _scanned_pdf(
        [
            _text_image(["Working hours are", "nine to five thirty."]),
            _blank_image(),  # unreadable → dropped, must NOT fail the upload
            _text_image(["Remote work is available", "to all employees."]),
        ]
    )
    doc = await _ocr(pdf)
    # The blank middle page is dropped; the two good pages survive with real numbers.
    assert [b.page for b in doc.blocks] == [1, 3]
    assert doc.extraction_method == "ocr"


@pytest.mark.asyncio
async def test_ocr_disabled_scanned_pdf_still_rejects() -> None:
    # Default behaviour preserved: with OCR off, a scan rejects as before.
    pdf = _scanned_pdf([_text_image(["Annual leave is 26 days."])])
    with pytest.raises(DocumentParseError) as ei:
        await _ocr(pdf, enabled=False)
    assert "scanned" in str(ei.value).lower()
