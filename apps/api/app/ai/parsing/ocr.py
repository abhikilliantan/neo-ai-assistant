"""Local OCR for scanned PDFs (ADR 0004 slice 1) — runs INSIDE the parse child.

Rasterize each PDF page with pypdfium2 at a FIXED, code-controlled DPI (never
influenced by the PDF), then OCR with Tesseract. Both are local and need no
network — the only combination consistent with Neo's data-control positioning
(Decision A). Security is pre-allocation (Decision C): the caller enforces the
page cap; here, the per-page pixel ceiling is checked via pypdfium2's dimension
pre-read BEFORE the bitmap is allocated, with the harness `RLIMIT_AS` as the
backstop if the ceiling is mis-set.

Confidence & page-skip (OQ d): a page whose mean per-word Tesseract confidence is
below `min_confidence`, or that yields no words, has its text DROPPED (no block
emitted). The caller rejects the whole document only if NO page survives.

Heavy deps (pypdfium2, pytesseract, PIL) are imported lazily so a non-OCR parse
never loads them.
"""

from __future__ import annotations

from typing import Any

# Fixed, code-controlled render settings (ADR 0004 Decision C) — never attacker-
# influenced. 200 DPI balances OCR accuracy against memory/time.
_OCR_DPI = 200
_OCR_SCALE = _OCR_DPI / 72.0  # pypdfium2 renders in points→pixels at this scale
# Per-page bitmap ceiling (~40 MP): a US-Letter page at 200 DPI is ~3.7 MP, so
# this is generous for real pages and lethal to a huge-MediaBox render bomb.
_OCR_MAX_PIXELS = 40_000_000


class OcrPageTooLargeError(Exception):
    """A page's rasterized bitmap would exceed the per-page pixel ceiling. Raised
    BEFORE allocation (dimension pre-read), so the bomb never renders."""


def ocr_pdf(data: bytes, *, min_confidence: float) -> list[dict[str, object]]:
    """OCR every page of `data`, returning one block per page that yields usable
    text at/above `min_confidence`. Below-floor / empty pages are skipped. Blocks
    carry the real 1-based page number, `section=None`, and the page's mean
    confidence. Raises `OcrPageTooLargeError` if any page exceeds the pixel cap.
    """
    import pypdfium2 as pdfium

    blocks: list[dict[str, object]] = []
    pdf = pdfium.PdfDocument(data)
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            # Pre-allocation dimension check: refuse before rendering.
            width_pt, height_pt = page.get_size()
            pixels = int(width_pt * _OCR_SCALE) * int(height_pt * _OCR_SCALE)
            if pixels > _OCR_MAX_PIXELS:
                raise OcrPageTooLargeError(
                    f"page {index + 1} would render to {pixels} px, over the cap"
                )
            bitmap = page.render(scale=_OCR_SCALE)
            image = bitmap.to_pil()
            try:
                text, confidence = _ocr_image(image)
            finally:
                image.close()
                bitmap.close()
            if not text or confidence < min_confidence:
                continue  # drop the page — do not fail the whole document
            blocks.append(
                {"text": text + "\n", "page": index + 1, "section": None, "confidence": confidence}
            )
    finally:
        pdf.close()
    return blocks


def _ocr_image(image: Any) -> tuple[str, float]:
    """OCR a single page image → (reconstructed text, mean per-word confidence).

    Uses one `image_to_data` pass (not a second `image_to_string`) so text and
    confidence come from the same recognition. Words are regrouped into their
    original lines so `full_text` reads naturally; confidence is the mean over
    recognised words (conf < 0 / empty tokens are Tesseract's non-text markers).
    """
    import pytesseract

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    lines: dict[tuple[int, int, int], list[str]] = {}
    confidences: list[float] = []
    for i in range(len(data["text"])):
        token = data["text"][i].strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not token or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(token)
        confidences.append(conf)
    if not confidences:
        return "", 0.0
    text = "\n".join(" ".join(words) for _key, words in sorted(lines.items()))
    return text, sum(confidences) / len(confidences)
