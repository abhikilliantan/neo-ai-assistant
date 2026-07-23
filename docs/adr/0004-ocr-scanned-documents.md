# 0004. OCR for Scanned / Image-Only PDFs

Status: Accepted
Date: 2026-07-23
Deciders: document-intelligence / platform owners
Supersedes: none

> Design-only ADR. No implementation, schema change, migration, or other file is
> included. Every statement about current behaviour cites `path:line` (paths
> relative to repo root). Decisions the decider must still make are left in Open
> Questions rather than resolved silently. This ADR builds directly on the ADR
> 0003 subprocess isolation harness; it does not re-open those decisions.

## Context

Real-world documents are frequently scanned or image-only PDFs with **no text
layer**. Today Neo detects these and rejects them rather than fabricating an
empty document. The scanned check is the last gate in the PDF child parser:
after extracting text per page, `app/ai/parsing/pdf_parser.py:105-108` computes
`total_chars < n_pages * _min_chars_per_page()` and raises
`ChildParseError(_SCANNED_MSG, error_class="parse_error")`, where
`_SCANNED_MSG = "No extractable text — if this is a scanned document, OCR isn't
supported yet."` (`pdf_parser.py:43`). The per-page floor is config
(`document_pdf_min_chars_per_page: int = 10`, `app/infrastructure/config/settings.py:176`),
threaded to the child via env (`app/ai/documents/pdf.py:36`, read at
`pdf_parser.py:46-48`). `error_class="parse_error"` maps to `DocumentParseError`
(`app/ai/parsing/harness.py:48-49`) → **HTTP 422**. ADR 0003 deferred OCR
explicitly as "its own future item" (`docs/adr/0003-document-parsing.md:169-170,
348`). This ADR is that item.

Five facts about the current pipeline shape this ADR:

1. **OCR is a branch inside the existing child parser, not new plumbing.** The
   child already dispatches `name=="pdf" → parse_pdf` (`app/ai/parsing/child.py:26-29`);
   the harness (`harness.py:63-85`) and the parent-side adapter
   `SubprocessPdfParser` (`app/ai/documents/pdf.py:17-37`) are format-agnostic and
   consume `{"text", "page", "section"}` block dicts (`pdf_parser.py:96`). OCR
   replaces the _raise_ at `pdf_parser.py:105-108` with a rasterize→OCR path that
   emits the same block dicts. Nothing upstream changes.

2. **The harness gives OCR real resource limits for free — but no network.** The
   child runs under `RLIMIT_AS` (default 1 GiB, `harness.py:44`, applied
   `harness.py:55-60,107`), a `RLIMIT_CPU` + wall-clock kill (`communicate(timeout=…)`
   at `harness.py:115`; process-group `SIGKILL` on expiry at `harness.py:116-118,
128-135`), runs off the event loop via `asyncio.to_thread` (`harness.py:76`),
   and imports no app/DB/network (`child.py` docstring). ADR 0003 chose pdfminer.six
   precisely because it is permissive-licensed, headless, and **no-network** (OQ7,
   `docs/adr/0003-document-parsing.md`).

3. **The request model is synchronous, twice over.** The upload route wraps ingest
   in `asyncio.wait_for(..., timeout=settings.document_parse_timeout_seconds)`
   (`app/presentation/http/routers/documents.py:112-125`; default `30.0`,
   `settings.py:161`), and the subprocess independently enforces a 30 s
   `communicate` timeout (`harness.py:45,115`). ADR 0003 kept the endpoint's
   request/response shape (no job id, no polling) and deferred async/queue parsing
   to 2.0 (`docs/adr/0003-document-parsing.md:140-145`), tied to the durable
   background-jobs theme (`NEO_2.0_ENHANCEMENT_REGISTER.md:191-204`, itself
   ADR-required).

4. **The provenance model already anticipates OCR's asymmetry.** `ParsedBlock`
   (`app/application/ports/documents.py:48-59`) carries page + nullable section;
   `DocumentPosition` (`ports/documents.py:79-102`) makes `page_start/page_end` a
   range and `section` nullable; `full_text` is the concatenation of block texts
   (`ports/documents.py:72-77`) and the harness builds offsets parent-side so
   `full_text[char_start:char_end] == block.text` holds by construction
   (`harness.py:15-17,151-155`). What does **not** exist yet: any column or field
   marking a document/chunk as OCR-derived or carrying a confidence
   (`app/infrastructure/db/models/documents.py` — the `document_chunks` provenance
   columns are `char_start`/`char_end` mandatory, `page_start`/`page_end`/`section`
   nullable, nothing more), and `DocumentPosition.render()` (`ports/documents.py:91-102`)
   has no OCR awareness.

5. **A "processing" status hook already exists, unused.** `DOCUMENT_STATUSES =
("pending", "ready", "failed")` is defined (`app/infrastructure/db/models/documents.py:48`)
   but the all-or-nothing 8b ingest only ever writes `"ready"`. This is the natural
   hook for the eventual async path.

The crux is performance. Tesseract at 300 DPI is ~0.5–2 s/page and rasterization
adds ~0.1–0.5 s/page → ~1–2.5 s/page all-in. 30 s ÷ ~2 s/page ≈ **12–15 pages**
before the child is hard-killed mid-OCR. A 40-page scan is 40–80 s — it blows
_both_ the subprocess timeout and the route `wait_for`, surfacing as
`DocumentParseError("document processing timed out")` (`documents.py:127-131`).
Raising the timeout to cover `document_max_pages=500` (`settings.py:160`) would
pin an HTTP worker for ~500–1000 s with no progress feedback. **Multi-page OCR
does not fit the synchronous 30 s model, and cannot be made to.**

---

## Decision A — Engine and rasterizer: local Tesseract + pypdfium2

**OCR engine: local Tesseract (Apache-2.0), via `pytesseract`.** Rasterizer:
**pypdfium2 (BSD-3 / Apache-2, PDFium — Chrome's renderer)** to render each PDF
page to a bitmap before OCR. Both are local, headless, and require **no network**.

This is the only combination consistent with ADR 0003's discipline (permissive
licence, headless, no-network — the exact criteria that selected pdfminer.six)
and with Neo's data-control / self-hosted positioning: **scanned documents — the
most sensitive class, because they are paper originals — never leave the
tenant.** pypdfium2 ships prebuilt wheels with the binary bundled (no system
package needed for rendering) and can read page dimensions _before_ rasterizing,
which the security caps in Decision C rely on. Tesseract exposes per-word
confidence scores, which Decision D uses.

**Cloud OCR (Google Vision / AWS Textract / Azure) and vision-LLM OCR are
explicitly NOT the default and NOT in this ADR's slices.** Both send customer
scans to a third party and both require opening network egress in a child that
today has none — a direct conflict with the positioning and the no-network
posture. Vision-LLM is additionally _not_ "free infra": the chat port is
text-only (`ChatMessage.content: str`, `app/application/ports/chat.py:30`; the
provider sends `{"role", "content": m.content}`, `app/ai/providers/anthropic/provider.py:84`),
so it would require extending the port + provider to carry image blocks. Cloud /
vision-LLM OCR is recorded as a **later, per-tenant, opt-in "high-accuracy"
backend behind the same parser interface** (mirroring the mock/real provider
split), gated by an explicit egress-consent flag — never the default.

**System-image change (recorded, not implemented here):** the api image gains
the `tesseract-ocr` system binary plus the `eng` language pack. This is a new
system dependency — the first for the parse child — added deliberately in
exchange for keeping OCR local. pypdfium2 needs no system package.

## Decision B — Phased sync → async (and it _is_ phased, on purpose)

OCR forces the async architecture decision ADR 0003 deferred. Rather than build
the queue now, this ADR ships OCR in **two phases**, and states plainly that the
first does not cover large scans.

**Slice 1 — capped-synchronous OCR (this ADR's buildable scope).** At the branch
point (`pdf_parser.py:105-108`), when OCR is enabled _and_ the page count ≤ an
**OCR page cap**, render each page (pypdfium2, capped DPI + pixel pre-check per
Decision C) → Tesseract → emit blocks with real 1-based page numbers,
`section=None`, and per-page confidence. The OCR path runs under a **separate,
bounded OCR timeout distinct from the 30 s text path** (a scan of a few pages
legitimately needs more than 30 s; a native-text parse must not). A scan **above
the page cap is rejected** with an honest message ("this scan has more pages than
we can OCR right now"), not silently truncated. Slice 1 proves OCR _quality_ on
small scans and, plainly, **does not handle large (e.g. 40-page) scans.**

**Slice 2 — asynchronous background OCR (out of scope for this ADR's build).**
Upload returns `202` immediately with `status="pending"` (the enum already
exists, `app/infrastructure/db/models/documents.py:48`); a durable worker
rasterizes + OCRs off the request path and flips the row to `"ready"` / `"failed"`;
the client polls. This lifts the page cap and is the correct end state for real
40-page scans. **Slice 2 depends on, and is gated by, the 2.0 durable-jobs ADR**
(`NEO_2.0_ENHANCEMENT_REGISTER.md:191-204`, "queue technology + at-least-once
semantics"). **This ADR does not design or build the queue** — it only records
that async OCR is the phase-2 shape and names its dependency.

## Decision C — Security caps in the child harness

OCR **reuses the existing isolation unchanged**: `RLIMIT_AS` (memory),
`RLIMIT_CPU` + wall-clock `SIGKILL` (runtime), process-group kill, off-event-loop
execution, and no network (`harness.py:44,55-60,76,115,128-135`). Rasterization
is the **new attack surface** — a malicious PDF can declare a huge MediaBox or
otherwise induce an enormous render, blowing memory before OCR even starts. New
**pre-allocation** caps, all enforced in the child before rendering a page:

1. **OCR page cap** — refuse to OCR beyond N pages (separate from, and lower than,
   `document_max_pages=500`, `settings.py:160`), threaded via env exactly like the
   existing `NEO_PDF_MIN_CHARS_PER_PAGE` (`pdf.py:36`).
2. **Fixed, code-controlled DPI** — render at a constant DPI chosen in code, never
   a value influenced by the PDF. Higher DPI = more pixels = more memory + time.
3. **Per-page pixel cap** — read the page's dimensions first (pypdfium2 supports
   this) and refuse a page whose rasterized bitmap (width × height × channels at
   the fixed DPI) would exceed a pixel ceiling, **before** allocating it.

`RLIMIT_AS` remains the **backstop** if a cap is mis-set — the same
belt-and-suspenders philosophy as ADR 0003's DOCX decompressed-size cap paired
with `RLIMIT_AS` (`document_docx_max_decompressed_bytes`, `settings.py`). Isolation
is otherwise identical: same child, no new privileges, no network. (A future
cloud/vision backend — Decision A — would require network in the child, a real
posture change deserving its own decision.)

## Decision D — Provenance and schema

**Citations are page-level with `section=None`**, identical to the native-text
PDF contract (`pdf_parser.py:96`): rasterization yields real 1-based page numbers;
OCR encodes no reliable sections. The chunker's `page_start..page_end` range works
unchanged.

**The offset-into-`full_text` invariant is unchanged.** Offsets have never indexed
original bytes — they index `full_text = "".join(block.text)` (`ports/documents.py:72-77`),
which for a native-text PDF is _already_ pdfminer's reconstruction. OCR is the same
contract with a lossier source string: offsets index into the **OCR-reconstructed
text**, and `full_text[char_start:char_end] == block.text` still holds by
construction (`harness.py:15-17,151-155`). No new offset machinery.

**Proposed schema deltas (recorded here, implemented in the slice — no migration
in this ADR):**

- A **document-level `extraction_method` column** on `documents` with values
  `"text"` / `"ocr"`. Document-level is correct because a PDF is _wholly_ one or
  the other — a PDF either has a usable text layer or it doesn't, and the scanned
  detection (`pdf_parser.py:105-108`) is a whole-document decision.
- A **per-chunk `ocr_confidence`** (nullable float) on `document_chunks`,
  aggregated from Tesseract's per-word confidence (0–100). NULL for native-text
  rows. Persisted in slice 1 in the same migration as `extraction_method` (OQ c),
  and the input to the confidence floor (OQ d).
- **`DocumentPosition.render()` appends "(OCR)"** (`ports/documents.py:91-102`)
  when the document is OCR-derived, so an OCR citation never claims the same
  authority as a native-text one.

## Decision E — Config: `document_ocr_enabled`, default off

OCR is gated by a **`document_ocr_enabled` flag, default off**, in the per-format
style of `document_native_parsers` (`settings.py:181`, set property at `:231-233`).
Shipped dark, enabled per pilot. This keeps the production default (reject scans)
until OCR quality is proven per corpus, and lets a data-sensitive tenant leave it
off entirely.

## Decision F — Benchmark: a real scanned fixture

Slice 1 adds a **real scanned-PDF fixture** to the retrieval benchmark
(`apps/api/tests/fixtures/retrieval-benchmark/`) and proves, under the benchmark's
existing protocol, that (a) OCR'd text is _searchable_ (a query retrieves the
right page) and (b) citations are sane (page-level, `(OCR)`-marked). This is the
OCR analogue of the scanned-vs-text margin the PDF slice measured — quality is
proven on a real file, not asserted.

---

## Alternatives rejected

- **Cloud OCR / vision-LLM as the default** — rejected for 1.0: customer scans
  egress to a third party (conflicts with the data-control pitch) and require
  network in the no-network child. Kept as a later opt-in backend (Decision A).
- **Rasterize with pdf2image + poppler** — rejected: poppler is a **GPL system
  binary** (`pdftoppm`), adding a heavier system dependency and a
  subprocess-within-the-subprocess. pypdfium2 needs no system package and reads
  dimensions first (Decision C).
- **Rasterize with Wand/ImageMagick + Ghostscript** — rejected: two system
  binaries, Ghostscript's AGPL/CVE history, and `policy.xml` hardening burden.
- **Synchronous OCR for arbitrary page counts** — rejected as physically
  impossible under the harness (see Context crux): a 40-page scan cannot fit 30 s,
  and a 500-page synchronous timeout is untenable. Hence the phased split.
- **Building the job queue in this ADR (skip slice 1)** — rejected: proving OCR
  quality does not require the queue, and the queue is a large, ADR-required
  investment (`register:191-204`). Capped-sync first de-risks the spend.
- **A per-chunk `is_ocr` boolean instead of a document-level column** — rejected:
  OCR is whole-document, so per-chunk duplication would be redundant and could
  drift. Confidence, which _does_ vary per chunk, is separate.

## Consequences

- Scanned PDFs up to the page cap become searchable with honest, `(OCR)`-marked,
  page-level citations; larger scans remain rejected (with a clearer message)
  until slice 2.
- The api image grows a system binary (`tesseract-ocr` + `eng`) — the parse
  child's first system dependency.
- The schema gains `extraction_method` and `ocr_confidence` (one slice-1
  migration); the citation renderer becomes OCR-aware.
- The synchronous request can now legitimately take longer than 30 s on the OCR
  path (bounded), a deliberate departure from the uniform text-path timeout.
- The async path (slice 2) is named and unblocked-in-principle but explicitly not
  built here; it inherits the `status` enum hook.

## Risks

- **OCR accuracy on complex layouts / tables / handwriting is limited** with
  Tesseract; low-confidence text could pollute retrieval. Mitigated by the
  `(OCR)` marker, per-chunk confidence, and the confidence floor that skips
  below-floor pages (OQ d).
- **Rasterization memory blowups** from adversarial PDFs — mitigated by the
  pre-allocation caps (Decision C) with `RLIMIT_AS` as backstop.
- **The 15-page cap frustrates users** whose real files exceed it, since 12–40
  pages is common (OQ a). This is the honest cost of shipping slice 1 before the
  queue; large scans wait for slice-2/async.
- **Two OCR-quality unknowns** (accuracy, confidence calibration) are only settled
  by the benchmark fixture (Decision F) on a real scan; the numbers may push the
  page cap or timeout choices.

## Implementation plan (small, independently testable slices)

1. **Slice 1 — capped-synchronous OCR (buildable now).** Add pypdfium2 +
   pytesseract + `tesseract-ocr`/`eng` to the api image. Branch at
   `pdf_parser.py:105-108`: when `document_ocr_enabled` and `n_pages ≤ 15`
   (`document_ocr_max_pages`, OQ a), render (capped DPI + pixel pre-check) → OCR →
   blocks (page, `section=None`, confidence); above the cap → reject honestly
   (large scans are slice-2/async). **Bounded 90 s OCR timeout** distinct from the
   30 s text path (OQ b), still hard-killed by the harness wall-clock kill.
   **Per-page confidence floor (OQ d):** a page below the aggregate-confidence floor
   has its OCR text **dropped (skipped, not failed)** and the upload proceeds on the
   remaining pages; only if **all** pages fall below the floor (no usable text) is
   the document rejected with the scanned-but-unreadable message — the same outcome
   as today's scanned detection, after attempting OCR. **One migration** adds both
   `extraction_method` and `ocr_confidence` (OQ c); `render()` appends "(OCR)".
   Config (all env-configurable): `document_ocr_enabled` (default off),
   `document_ocr_max_pages` (15), the 90 s OCR timeout, and the confidence floor.
   Benchmark: add a real scanned fixture, prove searchable + sane citations, and
   **calibrate the confidence floor against that fixture** (do not guess it).
   **Tests (hermetic where possible):** rasterize+OCR a known small scanned fixture
   → expected text/pages; over-15-page scan → honest rejection; pixel-cap trips
   before allocation on a huge-MediaBox PDF; offset round-trip holds on OCR text; a
   below-floor page is skipped while good pages survive; an all-below-floor document
   is rejected; `(OCR)` marker surfaces in the citation.
2. **Slice 2 — asynchronous background OCR (gated by the 2.0 durable-jobs ADR).**
   `202` + `status="pending"` → durable worker → `"ready"`/`"failed"` + client
   poll; lift the page cap. Not designed here.

## Assumptions

1. **Linux/Docker is the runtime for OCR** — same POSIX `resource`/`SIGKILL`
   basis as ADR 0003; macOS host uses the container. The `tesseract-ocr` binary
   is present in the api image.
2. **A scanned PDF is wholly image-only** — the whole-document detection
   (`pdf_parser.py:105-108`) holds, so `extraction_method` is a document-level
   property. Mixed text+scan PDFs (some pages OCR, some native) are out of scope
   for slice 1 (they currently pass the text floor and parse as text).
3. **Tesseract exposes usable per-word confidence** for the optional
   `ocr_confidence` aggregate.
4. **OCR offset-exactness ≠ OCR fidelity** — offsets into the reconstructed OCR
   text are exact by construction; extraction _accuracy_ is a separate axis,
   surfaced via the `(OCR)` marker and confidence, not hidden.
5. **pypdfium2 renders headless with no network and no system package**, and can
   read page dimensions before rasterizing.
6. **The retrieval benchmark can accept a scanned fixture** without disturbing the
   existing text corpus/queries (`apps/api/tests/fixtures/retrieval-benchmark/`).

## Trade-offs

- **Local Tesseract vs. cloud accuracy** — lower accuracy on complex layouts in
  exchange for keeping scans inside the tenant. Aligned with the positioning; the
  opt-in cloud backend is the escape hatch.
- **Capped-sync vs. full capability** — slice 1 ships value fast and de-risks the
  queue spend, at the cost of rejecting large scans until slice 2.
- **Separate OCR timeout vs. one uniform timeout** — a longer OCR budget is
  necessary but makes the synchronous request slower and less uniform.
- **A system binary vs. pure-Python purity** — Tesseract breaks ADR 0003's
  no-system-binary streak, accepted as the price of local OCR.
- **Document-level marker + optional per-chunk confidence vs. a single field** —
  more schema surface, but honest: the method is whole-doc, the confidence is
  per-chunk.

## Open Questions — Resolved

All four were resolved by the decider on 2026-07-23; rulings and reasoning
recorded below and reflected in the Decision, slice-1 plan, and config notes.

a. **OCR page cap for slice 1 — RESOLVED: 15 pages, env-configurable
(`document_ocr_max_pages`).** 15 covers common short real documents (e.g. a
12-page brochure) while keeping the synchronous OCR timeout bounded (~1–2.5 s/page,
Context crux). Larger scans (e.g. 40 pages) are **explicitly slice-2/async** — no
page cap makes synchronous 40-page OCR acceptable, so the cap is a deliberate
stopgap, not a target to grow.

b. **OCR timeout — RESOLVED: 90 seconds, env-configurable, distinct from the 30 s
text path.** 90 s covers 15 pages at worst-case per-page cost with margin, while
remaining bounded; the native-text parse keeps its 30 s budget so OCR's longer
need does not slow it. The child is still hard-killed by the existing harness
wall-clock kill (`harness.py:115,128-135`) regardless.

c. **Persist per-chunk `ocr_confidence` in slice 1 — RESOLVED: YES, in the same
slice-1 migration as `extraction_method`.** Tesseract already returns per-word
confidence during the OCR pass being run, so capturing it is near-free, whereas
adding the column later is a second migration — the same cost-asymmetry that put
`content_sha256` in ADR 0002's storage row up front. It is also the input to
ruling (d). **One migration adds both `extraction_method` and `ocr_confidence`.**

d. **Minimum OCR confidence — RESOLVED: skip the page, do not fail the upload;
reject only if the whole document is empty. Floor env-configurable, calibrated
against the fixture.** A page whose aggregate confidence falls below a
conservative floor has its OCR text **dropped** (so near-garbage never becomes a
confident-looking citation), but one bad page does **not** fail the upload — the
document proceeds on its usable pages. If **all** pages fall below the floor (no
usable text), the document is rejected honestly with the scanned-but-unreadable
message — the same outcome as today's scanned detection (`pdf_parser.py:105-108`),
reached _after_ attempting OCR. The floor is a tuning parameter (env-configurable,
conservative default) and MUST be calibrated against the real scanned benchmark
fixture added in slice 1 (Decision F), not guessed.
