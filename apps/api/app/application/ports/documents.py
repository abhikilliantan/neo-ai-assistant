"""Document-intelligence ports + value objects (Phase 8a).

Framework-free Pydantic VOs + Protocols, following the chat / embeddings /
tools / workflows pattern. Nothing here references FastAPI, SQLAlchemy, or any
file-parsing library — these are the contracts the domain hands to whichever
parser/chunker adapter can satisfy them (MockDocumentParser now; a real
PDF/DOCX parser in 8f).

⚠️ CITATION IS THE CONSTRAINT. Document Q&A is only trustworthy if an answer can
say WHICH document and WHICH passage it came from. Provenance is therefore
designed INTO the VOs from creation: a `DocumentChunk` carries document identity
+ ordinal + a `DocumentPosition`, so a chunk is citable in isolation. Retrofit
provenance later would mean re-parsing and re-embedding every document.

PROVENANCE MODEL (honest across formats):
  - `char_start`/`char_end` are the UNIVERSAL, MANDATORY anchor — a half-open
    `[start, end)` interval into the document's global extracted text (the
    ordered concatenation of block texts). Every format has character offsets
    and they are exact; this is what a UI highlights.
  - `page_start`/`page_end` are a RANGE, non-None ONLY for genuinely paginated
    formats (PDF). Equal within one page; `2..3` for a chunk spanning a page
    boundary — cited as "pp. 2-3", NEVER a fabricated single page.
  - `section` is a human label (heading/paragraph/sheet) when the source block
    provides one — a hint, not a precise range.

  What is UNAVAILABLE per format is represented as None, not faked:
    PDF   → page ✅ (real), section maybe
    DOCX  → page ❌ (Word paginates at render time, not in the file); section ✅
    TXT/MD→ page ❌, section ❌ — character offsets only
    XLSX  → page ❌; section = sheet + cell range

WHAT IS NOT UNIFIED: the parser does not force every format into "pages", does
not invent section titles, and does not reconstruct layout/columns/tables into
a canonical structure. It extracts text in ordered blocks tagged with whatever
positional truth the format actually carries.

8a is CONTRACTS + MOCK + IN-MEMORY CHUNKER only. Nothing is wired to a route; no
DB (8b) and no real parsing (8f).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class ParsedBlock(BaseModel):
    """One positional unit of a parsed document, in reading order.

    A block is the finest positional unit the FORMAT provides — a PDF page, a
    DOCX paragraph, a spreadsheet sheet. For formats with no intrinsic structure
    (txt/md) the parser emits blocks with `page=None, section=None`; position is
    then carried solely by the character offsets the chunker computes.
    """

    text: str
    page: int | None = None  # 1-based page for paginated formats (PDF); None otherwise
    section: str | None = None  # human label (heading/paragraph/sheet); None if the format has none


class ParsedDocument(BaseModel):
    """A parsed document: content type + ordered blocks. The document's global
    extracted text is the blocks concatenated in order — character offsets are
    measured against THAT string, so they are exact and gap-free.
    """

    content_type: str
    blocks: list[ParsedBlock]

    @property
    def full_text(self) -> str:
        """Global extracted text — blocks joined in order, no invented
        separators. Character offsets in a `DocumentPosition` index into this.
        """
        return "".join(block.text for block in self.blocks)


class DocumentPosition(BaseModel):
    """Where a passage lives, rendered honestly per format. See the module
    docstring for the model. `char_start`/`char_end` are mandatory; everything
    else is explicitly nullable rather than faked.
    """

    char_start: int
    char_end: int
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None

    def render(self) -> str:
        """Canonical, honest citation string. Backend truth for 8e's UI to
        mirror. Prefers the strongest real locator: page(s) → section →
        character offsets (never fabricates a page).
        """
        if self.page_start is not None:
            if self.page_end is not None and self.page_end != self.page_start:
                return f"pp. {self.page_start}-{self.page_end}"
            return f"p. {self.page_start}"
        if self.section is not None:
            return f"section {self.section}"
        return f"chars {self.char_start}-{self.char_end}"


class DocumentChunk(BaseModel):
    """A retrievable, embeddable passage that is CITABLE IN ISOLATION.

    `document_id` + `ordinal` + `position` are enough to say where this text
    came from with no other context. `ordinal` is the 0-based index within the
    document (stable order); `position` carries the provenance. Embeddings are
    computed over `text` in a later slice — the chunk shape is fixed now so that
    embedding + citation never need a re-parse.
    """

    document_id: str
    ordinal: int
    text: str
    position: DocumentPosition


class DocumentParser(Protocol):
    """Turn raw file bytes + a content type into a `ParsedDocument`.

    Deliberately a SMALL surface. Implementations SHOULD enforce their
    configured resource limits on UNTRUSTED input (max bytes, page/element
    count) and raise `DocumentParseError` / `DocumentTooLargeError` — the limit
    is part of the contract (see app.shared.exceptions.documents). A wall-clock
    timeout is enforced by the CALLER (8c) via `asyncio.wait_for`, not here — a
    parser cannot reliably self-timeout mid-CPU-work.
    """

    async def parse(self, *, data: bytes, content_type: str) -> ParsedDocument: ...


class Chunker(Protocol):
    """Split a `ParsedDocument` into citable `DocumentChunk`s. Pure CPU, no
    I/O — synchronous on purpose. `document_id` is threaded in so every chunk
    is citable in isolation.
    """

    def chunk(self, *, document_id: str, document: ParsedDocument) -> list[DocumentChunk]: ...
