"""Fixed-size (character) chunker with overlap (Phase 8a).

ONE implementation behind the `Chunker` Protocol. Fixed-size + overlap is
provider-agnostic, deterministic (reproducible embeddings + testable), and the
cheapest strategy to get right; sentence/structure-aware chunking is a future
strategy swap behind the same Protocol. It deliberately does NOT align chunks to
block boundaries — a chunk MAY span pages/sections, and `DocumentPosition`
records the true span (`pp. 2-3`) rather than a fabricated single locator.

`chunk_size`/`overlap` are in CHARACTERS. The real limit is the embedding
model's max TOKENS (≈ 4 chars/token) — keep `chunk_size` well under the model's
token cap. A token-aware chunker is the refinement, not this slice.
"""

from __future__ import annotations

from bisect import bisect_right

from app.application.ports.documents import (
    DocumentChunk,
    DocumentPosition,
    ParsedDocument,
)


class FixedSizeChunker:
    def __init__(self, *, chunk_size: int, overlap: int) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if not 0 <= overlap < chunk_size:
            # overlap >= chunk_size would make the stride <= 0 → no forward
            # progress. Reject at construction, not mid-loop.
            raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
        self._chunk_size = chunk_size
        self._overlap = overlap

    @property
    def chunker_id(self) -> str:
        # name+version, persisted per row for provenance (ADR 0001 Decision 8).
        return "fixed-1"

    def chunk(self, *, document_id: str, document: ParsedDocument) -> list[DocumentChunk]:
        full = document.full_text
        if not full:
            return []

        # ADR 0004: the fixed window ignores block boundaries, so per-chunk OCR
        # confidence is approximated by the document-level mean (fixed is the
        # legacy chunker; block_aware is the default and computes per-chunk).
        is_ocr = document.extraction_method == "ocr"
        _confs = [b.confidence for b in document.blocks if b.confidence is not None]
        doc_confidence = sum(_confs) / len(_confs) if _confs else None

        # Precompute each block's END offset in the global text, so a global
        # char offset maps back to its block (page/section) in O(log n).
        block_ends: list[int] = []
        running = 0
        for block in document.blocks:
            running += len(block.text)
            block_ends.append(running)

        def block_index_at(offset: int) -> int:
            # First block whose end offset is strictly greater than `offset`,
            # i.e. the block containing the character at `offset`.
            return min(bisect_right(block_ends, offset), len(document.blocks) - 1)

        stride = self._chunk_size - self._overlap
        chunks: list[DocumentChunk] = []
        ordinal = 0
        start = 0
        n = len(full)
        while start < n:
            end = min(start + self._chunk_size, n)
            first = document.blocks[block_index_at(start)]
            # The LAST character of the chunk is at end-1 (end is exclusive);
            # its block determines page_end for a boundary-spanning chunk.
            last = document.blocks[block_index_at(end - 1)]
            chunks.append(
                DocumentChunk(
                    document_id=document_id,
                    ordinal=ordinal,
                    text=full[start:end],
                    ocr_confidence=doc_confidence,
                    position=DocumentPosition(
                        char_start=start,
                        char_end=end,
                        page_start=first.page,
                        page_end=last.page,
                        # Section is a best-effort hint → take the first block's.
                        section=first.section,
                        is_ocr=is_ocr,
                    ),
                )
            )
            ordinal += 1
            if end == n:
                break
            start += stride
        return chunks
