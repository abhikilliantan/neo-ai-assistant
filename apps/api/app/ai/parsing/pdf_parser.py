"""Real PDF parser — runs INSIDE the isolation child (ADR 0003 slice 2, PDF).

PDF is the HOSTILE format: every input is treated as adversarial. Because this
runs in the child spawned by `parse_in_subprocess`, every PDF parse inherits the
30 s wall-clock timeout and the 1 GiB RLIMIT_AS from the harness automatically —
a decompression bomb or pathological object graph is bounded by the OS, not by
this code trying to out-clever it.

Extraction (pdfminer.six — MIT, pure-Python, headless, no network; ADR 0003
resolved Open Question 7): one block per text container, tagged with the REAL
1-based page number. `section = None` ALWAYS — a PDF does not reliably encode
sections, and the format-honesty rule forbids inventing them. Offsets are
computed parent-side by the harness (`full_text = "".join(block.text)`).

PDF-specific rejections, all in the child, all BEFORE returning any blocks (never
a partial extraction presented as complete):

1. ENCRYPTED / password-protected → rejected before extraction. Detected two
   ways: pdfminer raises PDFPasswordIncorrect/PDFEncryptionError while opening an
   encrypted doc whose empty password fails, AND `document.encryption` is set for
   any /Encrypt-carrying trailer. 1.0 does not accept passwords (ADR ruling).
2. CORRUPT / truncated → PDFSyntaxError (on open or mid-iteration) → parse_error.
3. SCANNED / image-only → resolved Open Question 3. If the document's average
   extractable chars-per-page is below `NEO_PDF_MIN_CHARS_PER_PAGE`, it is not a
   native-text PDF. ADR 0004: when OCR is enabled (`NEO_OCR_ENABLED`) and the page
   count is within `NEO_OCR_MAX_PAGES`, the scan is OCR'd (see `ocr.py`) instead of
   rejected; otherwise the historical reject stands (default: OCR off), never a
   SILENT empty document. This differs from DOCX's empty-but-valid rule: a PDF with
   no text layer is almost always a scan.
"""

from __future__ import annotations

import io
import os
import time

from app.ai.parsing.protocol import ChildParseError

_DEFAULT_MIN_CHARS_PER_PAGE = 10  # ADR 0003 OQ3; scanned pages measure 0, real text pages hundreds+
_DEFAULT_OCR_MAX_PAGES = 15  # ADR 0004 OQ a
_DEFAULT_OCR_MIN_CONFIDENCE = 60.0  # ADR 0004 OQ d (calibrated)

_ENCRYPTED_MSG = "This PDF is password-protected or encrypted, which is not supported."
_CORRUPT_MSG = "This file is not a readable PDF (it may be corrupt or truncated)."
_SCANNED_MSG = "No extractable text — if this is a scanned document, OCR isn't supported yet."
_UNREADABLE_MSG = (
    "This looks like a scanned document, but no readable text could be extracted from it."
)
_OCR_PAGE_TOO_LARGE_MSG = "A page of this scan is too large to process."


def _min_chars_per_page() -> int:
    raw = os.environ.get("NEO_PDF_MIN_CHARS_PER_PAGE")
    return int(raw) if raw and raw.isdigit() else _DEFAULT_MIN_CHARS_PER_PAGE


def _ocr_enabled() -> bool:
    return os.environ.get("NEO_OCR_ENABLED") == "1"


def _ocr_max_pages() -> int:
    raw = os.environ.get("NEO_OCR_MAX_PAGES")
    return int(raw) if raw and raw.isdigit() else _DEFAULT_OCR_MAX_PAGES


def _ocr_min_confidence() -> float:
    raw = os.environ.get("NEO_OCR_MIN_CONFIDENCE")
    try:
        return float(raw) if raw else _DEFAULT_OCR_MIN_CONFIDENCE
    except ValueError:
        return _DEFAULT_OCR_MIN_CONFIDENCE


def _ocr_scanned(data: bytes, n_pages: int) -> dict[str, object]:
    """ADR 0004 slice 1: OCR a scanned PDF. Page cap is enforced BEFORE any
    rasterisation (over-cap → honest reject; large scans are slice-2/async). A
    document whose pages all fall below the confidence floor (no usable text) is
    rejected as unreadable — the same outcome as the historical scanned reject,
    reached after attempting OCR."""
    if n_pages > _ocr_max_pages():
        raise ChildParseError(
            f"scan too large to OCR yet (max {_ocr_max_pages()} pages)",
            error_class="parse_error",
        )
    from app.ai.parsing.ocr import OcrPageTooLargeError, ocr_pdf

    try:
        blocks = ocr_pdf(data, min_confidence=_ocr_min_confidence())
    except OcrPageTooLargeError as e:
        raise ChildParseError(_OCR_PAGE_TOO_LARGE_MSG, error_class="parse_error") from e
    if not blocks:
        raise ChildParseError(_UNREADABLE_MSG, error_class="parse_error")
    return {"blocks": blocks, "extraction_method": "ocr"}


def parse_pdf(data: bytes) -> list[dict[str, object]] | dict[str, object]:
    # ponytail: test-only seam (env never set in prod) proving the PDF path
    # inherits the harness wall-clock kill — sleeps so the parent's communicate()
    # timeout fires and SIGKILLs the group.
    if os.environ.get("NEO_PDF_TEST_HANG") == "1":
        while True:
            time.sleep(1)

    from pdfminer.converter import PDFPageAggregator
    from pdfminer.layout import LAParams, LTTextContainer
    from pdfminer.pdfdocument import PDFDocument, PDFEncryptionError, PDFPasswordIncorrect
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser, PDFSyntaxError

    # 1. Open + encryption/corruption gate — BEFORE any extraction.
    try:
        document = PDFDocument(PDFParser(io.BytesIO(data)))
    except (PDFPasswordIncorrect, PDFEncryptionError) as e:
        raise ChildParseError(_ENCRYPTED_MSG, error_class="parse_error") from e
    except PDFSyntaxError as e:
        raise ChildParseError(_CORRUPT_MSG, error_class="parse_error") from e
    if document.encryption is not None:  # /Encrypt present but opened w/ empty pw → still reject
        raise ChildParseError(_ENCRYPTED_MSG, error_class="parse_error")

    # 2. Extract per page. A container -> a block, tagged with the real 1-based
    # page number; section is always None (PDF encodes no reliable sections).
    rsrcmgr = PDFResourceManager()
    device = PDFPageAggregator(rsrcmgr, laparams=LAParams())
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    blocks: list[dict[str, object]] = []
    total_chars = 0
    n_pages = 0
    try:
        for page_number, page in enumerate(PDFPage.create_pages(document), start=1):
            n_pages = page_number
            interpreter.process_page(page)
            for element in device.get_result():
                if not isinstance(element, LTTextContainer):
                    continue
                raw = element.get_text()
                if not raw.strip():
                    continue
                total_chars += len(raw.strip())
                text = raw if raw.endswith("\n") else raw + "\n"
                blocks.append({"text": text, "page": page_number, "section": None})
    except PDFSyntaxError as e:
        # Truncated/corrupt discovered mid-iteration — reject the whole document
        # rather than return the pages parsed so far (no partial-as-complete).
        raise ChildParseError(_CORRUPT_MSG, error_class="parse_error") from e

    if n_pages == 0:
        raise ChildParseError(_CORRUPT_MSG, error_class="parse_error")

    # 3. Scanned/image-only detection (OQ3): average extractable chars-per-page
    # below the floor -> not a native-text PDF.
    if total_chars < n_pages * _min_chars_per_page():
        # ADR 0004: OCR the scan instead of rejecting, when enabled and within the
        # page cap. Otherwise keep the historical reject (default: OCR off).
        if _ocr_enabled():
            return _ocr_scanned(data, n_pages)
        raise ChildParseError(_SCANNED_MSG, error_class="parse_error")

    return blocks
