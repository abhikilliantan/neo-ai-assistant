"""ADR 0003 slice 2 (PDF) — the real PDF parser running INSIDE the isolation
harness. Extraction correctness (blocks, real 1-based page numbers, a
page-spanning chunk showing a page_start..page_end range, section=None always,
exact offsets) plus the hostile-format rejections (scanned/image-only, encrypted,
corrupt, and the harness wall-clock kill on a hanging parse).

Runs through the real subprocess harness, so — like test_parse_harness /
test_docx_parser — it is Linux-only (RLIMIT_AS/timeout kill; ADR 0003 marks macOS
host unsupported) and is executed in the Linux api container / CI.

PDF fixtures are HAND-ASSEMBLED bytes (pdfminer.six is extract-only and the prod
container has no PDF-writer dep), which also keeps them minimal and adversarial.
"""

from __future__ import annotations

import io
import sys

import pytest

from app.ai.documents.block_aware import BlockAwareChunker
from app.ai.documents.pdf import PDF_CONTENT_TYPE
from app.ai.parsing.harness import parse_in_subprocess
from app.shared.exceptions.documents import DocumentParseError, DocumentParseTimeoutError

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="parse harness (RLIMIT_AS/timeout kill) is Linux-only; ADR 0003 marks macOS unsupported",
)


# --- minimal PDF assembler (correct xref offsets computed at build time) -------


def _assemble(objs: dict[int, bytes], *, root: int = 1, extra_trailer: bytes = b"") -> bytes:
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for num in sorted(objs):
        offsets[num] = out.tell()
        out.write(b"%d 0 obj\n%s\nendobj\n" % (num, objs[num]))
    xref_pos = out.tell()
    size = max(objs) + 1
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % size)
    for num in range(1, size):
        out.write(b"%010d 00000 n \n" % offsets.get(num, 0))
    out.write(
        b"trailer\n<< /Size %d /Root %d 0 R %s>>\nstartxref\n%d\n%%%%EOF\n"
        % (size, root, extra_trailer, xref_pos)
    )
    return out.getvalue()


def _text_pdf(pages: list[list[str]]) -> bytes:
    """A multi-page text PDF using the standard-14 Helvetica font (glyphs map to
    unicode, so pdfminer extracts exact text). One text line per Tj."""
    font_num = 3 + 2 * len(pages)
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        font_num: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids: list[str] = []
    num = 3
    for lines in pages:
        content_num = num + 1
        ops = [b"BT", b"/F1 12 Tf", b"72 720 Td"]
        for ln in lines:
            esc = ln.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)").encode()
            ops += [b"(" + esc + b") Tj", b"0 -16 Td"]
        ops.append(b"ET")
        stream = b"\n".join(ops)
        objs[num] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (font_num, content_num)
        )
        objs[content_num] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        kids.append(f"{num} 0 R")
        num += 2
    objs[2] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        " ".join(kids).encode(),
        len(pages),
    )
    return _assemble(objs)


def _image_only_pdf() -> bytes:
    """A single-page PDF whose only content is a raster image XObject — no text
    layer, the defining property of a scan for extraction (0 extractable chars)."""
    img = bytes(range(16))  # 4x4 DeviceGray raster
    content = b"q 400 0 0 400 100 200 cm /Im0 Do Q"
    return _assemble(
        {
            1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>",
            4: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
            5: b"<< /Type /XObject /Subtype /Image /Width 4 /Height 4 /ColorSpace "
            b"/DeviceGray /BitsPerComponent 8 /Length %d >>\nstream\n%s\nendstream"
            % (len(img), img),
        }
    )


def _encrypted_pdf() -> bytes:
    """A PDF whose trailer carries /Encrypt (Standard handler) with an /O//U that
    the empty password cannot satisfy — pdfminer rejects it on open."""

    def hexstr(b: bytes) -> bytes:
        return b"<" + b.hex().encode() + b">"

    return _assemble(
        {
            1: b"<< /Type /Catalog /Pages 2 0 R >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
            6: b"<< /Filter /Standard /V 2 /R 3 /Length 128 /P -44 /O %s /U %s >>"
            % (hexstr(b"\x11" * 32), hexstr(b"\x22" * 32)),
        },
        extra_trailer=b"/Encrypt 6 0 R /ID [<0011> <0022>] ",
    )


async def _parse(data: bytes, **kw: object):  # type: ignore[no-untyped-def]
    return await parse_in_subprocess(parser="pdf", data=data, content_type=PDF_CONTENT_TYPE, **kw)


# --- extraction: blocks, real page numbers, page-spanning range, section=None --


@pytest.mark.asyncio
async def test_pdf_extracts_blocks_with_real_pages_and_exact_offsets() -> None:
    pdf = _text_pdf(
        [
            ["Page one alpha beta gamma delta.", "Page one second line epsilon."],
            ["Page two opening zeta eta theta.", "Page two closing iota kappa."],
        ]
    )
    doc = await _parse(pdf)

    # section is ALWAYS None for PDF (format honesty).
    assert all(b.section is None for b in doc.blocks)
    # Real 1-based page numbers, in order, spanning both pages.
    pages = [b.page for b in doc.blocks]
    assert pages == sorted(pages)
    assert min(pages) == 1 and max(pages) == 2
    # Offset round-trip / gap-free tiling against the parent-built full_text.
    full = doc.full_text
    pos = 0
    for b in doc.blocks:
        assert full[pos : pos + len(b.text)] == b.text
        pos += len(b.text)
    assert pos == len(full)
    assert "alpha beta gamma" in full and "iota kappa" in full


@pytest.mark.asyncio
async def test_page_spanning_chunk_yields_page_start_end_range() -> None:
    # A chunk_size larger than the whole document packs page-1 and page-2 blocks
    # into ONE chunk → the DocumentPosition must carry page_start=1, page_end=2.
    pdf = _text_pdf([["Page one text body here."], ["Page two text body here."]])
    doc = await _parse(pdf)
    chunks = BlockAwareChunker(chunk_size=10_000, overlap=0).chunk(document_id="d", document=doc)
    assert len(chunks) == 1
    span = chunks[0].position
    assert span.page_start == 1
    assert span.page_end == 2
    assert span.render() == "pp. 1-2"  # honest multi-page citation, never a single fabricated page


# --- hostile-format rejections ------------------------------------------------


@pytest.mark.asyncio
async def test_scanned_image_only_pdf_rejected_with_clear_message() -> None:
    with pytest.raises(DocumentParseError) as ei:
        await _parse(_image_only_pdf())
    assert "OCR isn't supported" in str(ei.value)


@pytest.mark.asyncio
async def test_encrypted_pdf_rejected_with_clear_message() -> None:
    with pytest.raises(DocumentParseError) as ei:
        await _parse(_encrypted_pdf())
    assert "password-protected or encrypted" in str(ei.value)


@pytest.mark.asyncio
async def test_corrupt_pdf_rejected() -> None:
    with pytest.raises(DocumentParseError):
        await _parse(b"%PDF-1.4 this is truncated garbage not a real pdf")


@pytest.mark.asyncio
async def test_hanging_pdf_killed_at_harness_timeout() -> None:
    # Confirm the PDF path inherits the harness wall-clock kill: a parse that hangs
    # is SIGKILL'd at the (here tiny) timeout, surfacing as a timeout error.
    pdf = _text_pdf([["anything"]])
    with pytest.raises(DocumentParseTimeoutError):
        await _parse(pdf, timeout_seconds=1.0, child_env={"NEO_PDF_TEST_HANG": "1"})
