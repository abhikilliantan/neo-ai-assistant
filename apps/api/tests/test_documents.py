"""Phase 8a — document intelligence foundation: parser + chunker ports, mock
parser, config. No route, no DB, no real file libraries.

Citation is the constraint, so the load-bearing tests prove: a chunk is citable
in ISOLATION, and provenance is correct for a chunk that SPANS a page/section
boundary (the case most likely to produce a wrong citation).
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from app.ai.documents import (
    BlockAwareChunker,
    ContentTypeDocumentParser,
    FixedSizeChunker,
    MockDocumentParser,
    build_chunker,
    build_document_parser,
)
from app.application.ports.documents import (
    DocumentChunk,
    DocumentPosition,
    ParsedBlock,
    ParsedDocument,
)
from app.infrastructure.config import Settings
from app.main import create_app
from app.shared.exceptions.documents import DocumentTooLargeError


def _base(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {
        "python_env": "test",
        "database_url": "postgresql+asyncpg://x/x",
        "app_database_url": "postgresql+asyncpg://x/x",
        "redis_url": "redis://x",
        "jwt_secret_key": "test-secret-key-at-least-32-bytes-long-xxxxx",
        # Hermetic default: ignore any DOCUMENT_NATIVE_PARSERS in the dev's .env so
        # per-format enablement tests assert against a known-empty baseline. Opt-in
        # tests override this explicitly.
        "document_native_parsers": "",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


def _doc(*blocks: ParsedBlock, content_type: str = "text/plain") -> ParsedDocument:
    return ParsedDocument(content_type=content_type, blocks=list(blocks))


# --- VO shapes + provenance rendering ---------------------------------------


def test_position_renders_honestly_per_format() -> None:
    # PDF within one page.
    assert DocumentPosition(char_start=0, char_end=10, page_start=3, page_end=3).render() == "p. 3"
    # PDF spanning a page boundary → a range, never a single fabricated page.
    assert (
        DocumentPosition(char_start=0, char_end=10, page_start=2, page_end=3).render() == "pp. 2-3"
    )
    # No page but a structural label (DOCX paragraph / XLSX sheet).
    assert (
        DocumentPosition(char_start=0, char_end=10, section="Introduction").render()
        == "section Introduction"
    )
    # Plain text: no page, no section → character offsets ONLY (never faked).
    assert DocumentPosition(char_start=100, char_end=250).render() == "chars 100-250"


def test_chunk_is_citable_in_isolation() -> None:
    """Given ONE chunk and no other context, we can say where it came from."""
    chunk = DocumentChunk(
        document_id="doc-abc",
        ordinal=4,
        text="the answer is 42",
        position=DocumentPosition(char_start=800, char_end=816, page_start=7, page_end=7),
    )
    # Document identity + position are both present on the chunk alone.
    assert chunk.document_id == "doc-abc"
    assert chunk.position.render() == "p. 7"
    assert (chunk.position.char_start, chunk.position.char_end) == (800, 816)


def test_parsed_document_full_text_is_blocks_concatenated() -> None:
    doc = _doc(ParsedBlock(text="AAA"), ParsedBlock(text="BBB"), ParsedBlock(text="CC"))
    assert doc.full_text == "AAABBBCC"  # no invented separators; offsets index into this


# --- mock parser: deterministic, multi-page / multi-section -----------------


@pytest.mark.asyncio
async def test_mock_parser_pdf_is_multi_page_deterministic() -> None:
    parser = MockDocumentParser(max_bytes=1_000_000)
    a = await parser.parse(data=b"anything", content_type="application/pdf")
    b = await parser.parse(data=b"different bytes", content_type="application/pdf")

    assert len(a.blocks) >= 3  # realistic structure, not one flat blob
    assert [blk.page for blk in a.blocks] == [1, 2, 3]  # real page numbers
    assert all(blk.section is None for blk in a.blocks)  # PDF: page, not section
    assert a.model_dump() == b.model_dump()  # deterministic (ignores byte content)


@pytest.mark.asyncio
async def test_mock_parser_non_pdf_is_multi_section_no_pages() -> None:
    parser = MockDocumentParser(max_bytes=1_000_000)
    doc = await parser.parse(data=b"hello", content_type="text/plain")
    assert len(doc.blocks) >= 3
    assert all(blk.page is None for blk in doc.blocks)  # no fabricated pages
    assert [blk.section for blk in doc.blocks] == ["Section 1", "Section 2", "Section 3"]


@pytest.mark.asyncio
async def test_mock_parser_empty_input_yields_empty_document() -> None:
    parser = MockDocumentParser(max_bytes=1_000_000)
    doc = await parser.parse(data=b"", content_type="text/plain")
    assert doc.blocks == []
    assert doc.full_text == ""


@pytest.mark.asyncio
async def test_mock_parser_enforces_max_bytes() -> None:
    parser = MockDocumentParser(max_bytes=8)
    with pytest.raises(DocumentTooLargeError):
        await parser.parse(data=b"way too many bytes", content_type="application/pdf")


# --- chunker: coverage, overlap, boundary provenance ------------------------


def test_chunks_cover_the_document_without_gaps() -> None:
    doc = _doc(ParsedBlock(text="x" * 250))
    chunks = FixedSizeChunker(chunk_size=100, overlap=20).chunk(document_id="d", document=doc)
    # Every character is covered by at least one chunk; offsets are contiguous.
    assert chunks[0].position.char_start == 0
    assert chunks[-1].position.char_end == 250
    for prev, nxt in pairwise(chunks):
        assert nxt.position.char_start <= prev.position.char_end  # no gap
    # Reconstruct the doc from non-overlapping prefixes → exact original text.
    rebuilt = chunks[0].text
    for prev, nxt in pairwise(chunks):
        rebuilt += nxt.text[prev.position.char_end - nxt.position.char_start :]
    assert rebuilt == doc.full_text
    # Ordinals are 0-based and dense.
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_overlap_is_exactly_as_specified() -> None:
    doc = _doc(ParsedBlock(text="y" * 300))
    chunks = FixedSizeChunker(chunk_size=100, overlap=30).chunk(document_id="d", document=doc)
    # Consecutive chunks share exactly `overlap` characters (stride = 70).
    for prev, nxt in pairwise(chunks):
        if nxt.position.char_end == len(doc.full_text) and len(nxt.text) < 100:
            continue  # last (short) chunk may overlap by more than the stride
        assert nxt.position.char_start == prev.position.char_start + 70
        assert prev.position.char_end - nxt.position.char_start == 30


def test_boundary_spanning_chunk_cites_the_true_page_range() -> None:
    """The case most likely to produce a WRONG citation: a chunk straddling two
    pages must record pp. 2-3, not a single fabricated page.
    """
    doc = _doc(
        ParsedBlock(text="A" * 60, page=1, section=None),
        ParsedBlock(text="B" * 60, page=2, section=None),
        ParsedBlock(text="C" * 60, page=3, section=None),
        content_type="application/pdf",
    )
    # chunk_size 100 with no overlap → chunk 0 = [0,100): pages 1-2; chunk 1 =
    # [100,180): pages 2-3.
    chunks = FixedSizeChunker(chunk_size=100, overlap=0).chunk(document_id="d", document=doc)
    assert (chunks[0].position.page_start, chunks[0].position.page_end) == (1, 2)
    assert chunks[0].position.render() == "pp. 1-2"
    assert (chunks[1].position.page_start, chunks[1].position.page_end) == (2, 3)
    assert chunks[1].position.render() == "pp. 2-3"


def test_boundary_spanning_chunk_takes_first_block_section() -> None:
    doc = _doc(
        ParsedBlock(text="A" * 60, section="Intro"),
        ParsedBlock(text="B" * 60, section="Body"),
    )
    chunks = FixedSizeChunker(chunk_size=100, overlap=0).chunk(document_id="d", document=doc)
    assert chunks[0].position.section == "Intro"  # best-effort hint = first block
    assert chunks[0].position.page_start is None  # no fabricated page


# --- chunker edge cases -----------------------------------------------------


def test_empty_document_yields_no_chunks() -> None:
    assert (
        FixedSizeChunker(chunk_size=100, overlap=10).chunk(document_id="d", document=_doc()) == []
    )


def test_document_smaller_than_one_chunk_is_one_chunk() -> None:
    doc = _doc(ParsedBlock(text="tiny", section="only"))
    chunks = FixedSizeChunker(chunk_size=100, overlap=10).chunk(document_id="d", document=doc)
    assert len(chunks) == 1
    assert chunks[0].text == "tiny"
    assert chunks[0].position.char_start == 0 and chunks[0].position.char_end == 4


def test_single_section_larger_than_one_chunk_splits_but_keeps_provenance() -> None:
    doc = _doc(ParsedBlock(text="z" * 250, page=5, section="Big"))
    chunks = FixedSizeChunker(chunk_size=100, overlap=0).chunk(document_id="d", document=doc)
    assert len(chunks) == 3
    # All split chunks cite the same single page/section they came from.
    for c in chunks:
        assert (c.position.page_start, c.position.page_end) == (5, 5)
        assert c.position.section == "Big"


def test_chunker_rejects_bad_config() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        FixedSizeChunker(chunk_size=0, overlap=0)
    with pytest.raises(ValueError, match="overlap"):
        FixedSizeChunker(chunk_size=100, overlap=100)  # >= chunk_size → no progress


# --- builders ---------------------------------------------------------------


def test_build_document_parser_default_rejects_unsupported_types() -> None:
    # Default "reject": text/md dispatch to the real parser; pdf/docx have NO
    # fallback → 415, never mock-fabricated.
    parser = build_document_parser(_base())
    assert isinstance(parser, ContentTypeDocumentParser)
    assert parser._fallback is None


def test_build_document_parser_mock_fallback_is_opt_in() -> None:
    # "mock" (tests/CI, conftest-pinned) fabricates pdf/docx via the mock.
    parser = build_document_parser(_base(document_parser="mock"))
    assert isinstance(parser, ContentTypeDocumentParser)
    assert isinstance(parser._fallback, MockDocumentParser)


def test_document_max_bytes_default_is_25_mib() -> None:
    # Guards the raised upload cap against a regression back to 10 MB. Checks the
    # CODE default (env-independent), so a stray DOCUMENT_MAX_BYTES can't mask it.
    assert Settings.model_fields["document_max_bytes"].default == 26_214_400  # 25 MiB


def test_native_docx_parser_off_by_default() -> None:
    # ADR 0003 per-format enablement: with document_native_parsers empty (default),
    # NO native parser is wired — DOCX falls through to the fallback (mock in tests,
    # reject in prod). The real subprocess parser is opt-in, never a silent default.
    from app.ai.documents.docx import DOCX_CONTENT_TYPE

    parser = build_document_parser(_base(document_parser="mock"))
    assert isinstance(parser, ContentTypeDocumentParser)
    assert DOCX_CONTENT_TYPE not in parser._native


def test_native_docx_parser_opt_in_per_format() -> None:
    # Listing "docx" wires the real SubprocessDocxParser for the DOCX type ONLY.
    # PDF is NOT enabled (no single global flag) — it stays out of _native.
    from app.ai.documents.docx import DOCX_CONTENT_TYPE, SubprocessDocxParser

    parser = build_document_parser(_base(document_native_parsers="docx"))
    assert isinstance(parser, ContentTypeDocumentParser)
    assert isinstance(parser._native[DOCX_CONTENT_TYPE], SubprocessDocxParser)
    assert "application/pdf" not in parser._native


def test_native_pdf_parser_off_by_default() -> None:
    # Default (empty document_native_parsers): no native PDF parser — PDF falls to
    # the fallback (mock in tests, reject in prod), never a silent real parse.
    from app.ai.documents.pdf import PDF_CONTENT_TYPE

    parser = build_document_parser(_base(document_parser="mock"))
    assert isinstance(parser, ContentTypeDocumentParser)
    assert PDF_CONTENT_TYPE not in parser._native


def test_native_pdf_parser_opt_in_does_not_disturb_other_formats() -> None:
    # Listing "pdf" wires the real SubprocessPdfParser for the PDF type ONLY —
    # enabling PDF must not enable DOCX (per-format, no global flag).
    from app.ai.documents.docx import DOCX_CONTENT_TYPE
    from app.ai.documents.pdf import PDF_CONTENT_TYPE, SubprocessPdfParser

    parser = build_document_parser(_base(document_native_parsers="pdf"))
    assert isinstance(parser, ContentTypeDocumentParser)
    assert isinstance(parser._native[PDF_CONTENT_TYPE], SubprocessPdfParser)
    assert DOCX_CONTENT_TYPE not in parser._native


@pytest.mark.asyncio
async def test_dispatcher_rejects_unsupported_type_with_415_error() -> None:
    from app.shared.exceptions.documents import UnsupportedContentTypeError

    parser = build_document_parser(_base())  # default reject
    with pytest.raises(UnsupportedContentTypeError, match="PDF and Word"):
        await parser.parse(data=b"%PDF-1.7 ...", content_type="application/pdf")


@pytest.mark.asyncio
async def test_dispatcher_still_parses_text_under_reject_default() -> None:
    parser = build_document_parser(_base())  # default reject
    doc = await parser.parse(data=b"hello\n\nworld\n", content_type="text/plain")
    assert doc.full_text == "hello\n\nworld\n"  # real parser, unaffected by reject


def test_build_document_parser_raises_not_implemented_on_real_parser() -> None:
    with pytest.raises(NotImplementedError, match="8f"):
        build_document_parser(_base(document_parser="unstructured"))


def test_build_chunker_returns_configured_fixed_chunker() -> None:
    chunker = build_chunker(
        _base(document_chunker="fixed", document_chunk_size=100, document_chunk_overlap=25)
    )
    assert isinstance(chunker, FixedSizeChunker)
    doc = _doc(ParsedBlock(text="w" * 130))
    chunks = chunker.chunk(document_id="d", document=doc)
    # size 100 / overlap 25 → stride 75 → chunks at [0,100) and [75,130).
    assert [(c.position.char_start, c.position.char_end) for c in chunks] == [(0, 100), (75, 130)]


def test_build_chunker_default_is_block_aware() -> None:
    # ADR 0001 Amendment 1: block_aware is now the default; fixed still selectable.

    assert isinstance(build_chunker(_base()), BlockAwareChunker)  # default flipped
    assert isinstance(build_chunker(_base(document_chunker="fixed")), FixedSizeChunker)


# --- kill switch: inert this slice ------------------------------------------


def test_documents_enabled_defaults_true() -> None:
    assert _base().documents_enabled is True


def test_documents_enabled_false_is_inert_this_slice() -> None:
    """Nothing consumes `documents_enabled` yet — it mirrors tools_enabled /
    workflows_enabled, whose builders also ignore their switch; a route-level
    gate lands in 8c/8d. Flipping it False changes nothing observable: the
    parser dispatcher is still built and the chunker is still built.
    """
    settings = _base(documents_enabled=False)
    assert settings.documents_enabled is False
    assert isinstance(build_document_parser(settings), ContentTypeDocumentParser)
    # ADR 0001 Amendment 1: default chunker is now block_aware.
    assert isinstance(build_chunker(settings), BlockAwareChunker)


# --- lifespan wiring + startup log ------------------------------------------


def test_db_app_pins_parser_and_chunker_on_state(db_app) -> None:  # type: ignore[no-untyped-def]
    # 8f-1: the pinned parser is the content-type dispatcher; its non-text
    # fallback is still the mock (the CI/test default). ADR 0001 Amendment 1:
    # the pinned chunker is now block_aware (the new default).

    assert isinstance(db_app.state.document_parser, ContentTypeDocumentParser)
    assert isinstance(db_app.state.document_parser._fallback, MockDocumentParser)
    assert isinstance(db_app.state.chunker, BlockAwareChunker)


def test_create_app_leaves_document_state_uninitialized_until_lifespan() -> None:
    app = create_app(_base())
    assert not hasattr(app.state, "document_parser")
    assert not hasattr(app.state, "chunker")


@pytest.mark.asyncio
async def test_lifespan_logs_documents_field(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    import app.main as main_mod

    captured: dict[str, object] = {}

    class _CapturingLog:
        def info(self, event: str, **kwargs: object) -> None:
            if event == "startup":
                captured.update(kwargs)

        def warning(self, event: str, **kwargs: object) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(main_mod, "get_logger", lambda _name: _CapturingLog())
    fake_db = SimpleNamespace(dispose=AsyncMock())
    fake_redis = SimpleNamespace(aclose=AsyncMock())
    fake_provider = SimpleNamespace(close=AsyncMock())
    fake_embed = SimpleNamespace(close=AsyncMock())
    monkeypatch.setattr(main_mod, "build_database", lambda _s: fake_db)
    monkeypatch.setattr(main_mod, "build_system_database", lambda _s: fake_db)
    monkeypatch.setattr(main_mod, "build_redis", lambda _s: fake_redis)
    monkeypatch.setattr(main_mod, "build_chat_provider", lambda _s: fake_provider)
    monkeypatch.setattr(main_mod, "build_embedding_provider", lambda _s: fake_embed)
    monkeypatch.setattr(main_mod, "probe_storage_writable", AsyncMock())
    monkeypatch.setattr(main_mod, "build_memory_extractor", lambda _s, _p: MagicMock())
    monkeypatch.setattr(main_mod, "DatabaseHealthCheck", lambda **_kw: MagicMock())
    monkeypatch.setattr(main_mod, "RedisHealthCheck", lambda **_kw: MagicMock())

    app = create_app(_base())
    async with main_mod.lifespan(app):
        pass

    assert captured.get("documents") == "reject"  # default parser fallback (8-cleanup)
    # Sanity: existing fields still carried (no regression).
    assert {"tools", "agents", "workflows"} <= set(captured)
