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
   extractable chars-per-page is below `NEO_PDF_MIN_CHARS_PER_PAGE`, reject with a
   clear "OCR isn't supported" message rather than SILENTLY emitting an empty
   document. This DELIBERATELY differs from DOCX's empty-but-valid rule: a PDF
   with no text layer is almost always a scan, and a silent empty doc is the
   exact failure we are avoiding.
"""

from __future__ import annotations

import io
import os
import time

from app.ai.parsing.protocol import ChildParseError

_DEFAULT_MIN_CHARS_PER_PAGE = 10  # ADR 0003 OQ3; scanned pages measure 0, real text pages hundreds+

_ENCRYPTED_MSG = "This PDF is password-protected or encrypted, which is not supported."
_CORRUPT_MSG = "This file is not a readable PDF (it may be corrupt or truncated)."
_SCANNED_MSG = "No extractable text — if this is a scanned document, OCR isn't supported yet."


def _min_chars_per_page() -> int:
    raw = os.environ.get("NEO_PDF_MIN_CHARS_PER_PAGE")
    return int(raw) if raw and raw.isdigit() else _DEFAULT_MIN_CHARS_PER_PAGE


def parse_pdf(data: bytes) -> list[dict[str, object]]:
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
    # below the floor -> reject, never a silent empty document.
    if total_chars < n_pages * _min_chars_per_page():
        raise ChildParseError(_SCANNED_MSG, error_class="parse_error")

    return blocks
