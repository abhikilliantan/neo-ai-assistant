"""Block-aware chunker (ADR 0001).

A second `Chunker` behind the same Protocol as `FixedSizeChunker`. Instead of
sliding a fixed character window over the flat `full_text` (which cuts mid-word
and lets one window straddle two sections — the V1 benchmark defects), this
packs whole `ParsedBlock`s in document order, so chunk boundaries land on the
paragraph/section edges the 8f-1 parser already computed.

Implements ADR 0001 exactly:

- Decision 1: greedily pack whole blocks (document order) until adding the next
  block would exceed `chunk_size` (characters), then start a new chunk. Blocks
  tile `full_text` gap-free (8f-1), so a packed run is a contiguous slice and
  offsets stay exact.
- Decision 2: a single block longer than `chunk_size` is split by itself with
  the fixed-window logic (stride = chunk_size - overlap) over that block's own
  char span; those sub-chunks carry the block's page/section.
- Decision 3 + Open Question 5: overlap is a *whole-block carry budget in
  characters* (reuses `overlap`). After a chunk closes, the next chunk is seeded
  with as many complete trailing blocks of the previous chunk as fit within
  `overlap` chars. Hard guard: every chunk always introduces >=1 fresh block, so
  forward progress cannot stall (also enforced by `0 <= overlap < chunk_size`).
- Decision 4 + Open Question 1: a change in a block's `section` value is a
  *preferred* split point — break there rather than pack across, but only once
  the current chunk has reached `_SECTION_BREAK_THRESHOLD` of `chunk_size`
  (below that, pack across to avoid tiny chunks). Not a hard split.
- Decision 5: char_start/char_end from the first/last packed block; page from
  first/last; `section` is the shared section of the FRESH blocks, or None when
  a chunk's fresh content spans more than one section (the overlap-carried block
  contributes text/offsets but not the section label, so a section break does
  not null every following chunk).
- Decision 6: pure and deterministic — greedy, fixed tie-breaking, iterates
  `document.blocks` in order, no clock/RNG.
"""

from __future__ import annotations

from app.application.ports.documents import (
    DocumentChunk,
    DocumentPosition,
    ParsedBlock,
    ParsedDocument,
)

_CHUNKER_ID = "block-aware-1"  # name+version, mirrors embedding_model (ADR 0001 OQ3)


def _mean_confidence(blocks: list[ParsedBlock]) -> float | None:
    """Mean OCR confidence over the blocks that carry one; None if none do (a
    natively-extracted document). ADR 0004."""
    confidences = [b.confidence for b in blocks if b.confidence is not None]
    return sum(confidences) / len(confidences) if confidences else None


class BlockAwareChunker:
    # Resolved Open Question 1: prefer a section break once the chunk is at or
    # past 60% of chunk_size. Hardcoded, NOT a Settings field — a tuning knob;
    # exposing it invites fiddling instead of benchmarking (change + re-run).
    _SECTION_BREAK_THRESHOLD = 0.60

    def __init__(self, *, chunk_size: int, overlap: int) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if not 0 <= overlap < chunk_size:
            # overlap >= chunk_size (the carry budget) could starve forward
            # progress; reject at construction, mirroring FixedSizeChunker.
            raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
        self._chunk_size = chunk_size
        self._overlap = overlap

    @property
    def chunker_id(self) -> str:
        return _CHUNKER_ID

    def chunk(self, *, document_id: str, document: ParsedDocument) -> list[DocumentChunk]:
        full = document.full_text
        if not full:
            return []
        blocks = document.blocks

        # Global char start of each block (blocks tile full_text, so
        # start[i+1] == start[i] + len(blocks[i].text)).
        starts: list[int] = []
        pos = 0
        for blk in blocks:
            starts.append(pos)
            pos += len(blk.text)

        def bstart(i: int) -> int:
            return starts[i]

        def bend(i: int) -> int:
            return starts[i] + len(blocks[i].text)

        # --- Phase 1: partition blocks into units (packed groups / oversized) ---
        # unit is ("pack", [idx, ...]) or ("over", idx). Units cover every block
        # contiguously with no gaps.
        threshold = self._chunk_size * self._SECTION_BREAK_THRESHOLD
        units: list[tuple[str, list[int]]] = []
        i = 0
        n = len(blocks)
        while i < n:
            if len(blocks[i].text) > self._chunk_size:
                units.append(("over", [i]))
                i += 1
                continue
            group = [i]
            cur_len = len(blocks[i].text)
            j = i + 1
            while j < n:
                blen = len(blocks[j].text)
                if blen > self._chunk_size:
                    break  # an oversized block starts its own unit
                if cur_len + blen > self._chunk_size:
                    break  # size cap
                if blocks[j].section != blocks[j - 1].section and cur_len >= threshold:
                    break  # Decision 4: preferred section break past 60%
                group.append(j)
                cur_len += blen
                j += 1
            units.append(("pack", group))
            i = j

        # --- Phase 2: emit chunks with overlap carry + provenance ---
        # ADR 0004: is_ocr is document-level; ocr_confidence is the mean over the
        # blocks a chunk packs (None for natively-extracted docs, whose blocks
        # carry no confidence).
        is_ocr = document.extraction_method == "ocr"
        chunks: list[DocumentChunk] = []
        ordinal = 0
        prev_pack: list[int] | None = None  # trailing blocks eligible to carry
        stride = self._chunk_size - self._overlap
        for kind, payload in units:
            if kind == "over":
                idx = payload[0]
                start = bstart(idx)
                end = bend(idx)
                conf = _mean_confidence([blocks[idx]])
                s = start
                while s < end:
                    e = min(s + self._chunk_size, end)
                    chunks.append(
                        self._make(
                            document_id,
                            ordinal,
                            full,
                            s,
                            e,
                            section=blocks[idx].section,
                            page_start=blocks[idx].page,
                            page_end=blocks[idx].page,
                            is_ocr=is_ocr,
                            ocr_confidence=conf,
                        )
                    )
                    ordinal += 1
                    if e == end:
                        break
                    s += stride
                prev_pack = None  # an oversized block is never carried
                continue

            group = payload
            # Overlap carry: trailing whole blocks of the previous packed group.
            carry: list[int] = []
            if prev_pack is not None:
                budget = self._overlap
                for k in reversed(prev_pack):
                    klen = len(blocks[k].text)
                    if klen <= budget:
                        carry.insert(0, k)
                        budget -= klen
                    else:
                        break
            all_idx = carry + group
            fresh_sections = {blocks[k].section for k in group}
            section = next(iter(fresh_sections)) if len(fresh_sections) == 1 else None
            chunks.append(
                self._make(
                    document_id,
                    ordinal,
                    full,
                    bstart(all_idx[0]),
                    bend(all_idx[-1]),
                    section=section,
                    page_start=blocks[all_idx[0]].page,
                    page_end=blocks[all_idx[-1]].page,
                    is_ocr=is_ocr,
                    ocr_confidence=_mean_confidence([blocks[k] for k in all_idx]),
                )
            )
            ordinal += 1
            prev_pack = group
        return chunks

    @staticmethod
    def _make(
        document_id: str,
        ordinal: int,
        full: str,
        start: int,
        end: int,
        *,
        section: str | None,
        page_start: int | None,
        page_end: int | None,
        is_ocr: bool,
        ocr_confidence: float | None,
    ) -> DocumentChunk:
        return DocumentChunk(
            document_id=document_id,
            ordinal=ordinal,
            text=full[start:end],
            ocr_confidence=ocr_confidence,
            position=DocumentPosition(
                char_start=start,
                char_end=end,
                page_start=page_start,
                page_end=page_end,
                section=section,
                is_ocr=is_ocr,
            ),
        )
