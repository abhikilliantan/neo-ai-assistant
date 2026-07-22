# 0003. Document Parsing (PDF + DOCX)

Status: Accepted
Date: 2026-07-22
Deciders: document-intelligence / platform owners
Supersedes: none

> Design-only ADR. No implementation, schema change, migration, or other file is
> included. Every statement about current behaviour cites `path:line` (paths
> relative to repo root). Decisions still open are left as Open Questions rather
> than resolved silently. One ADR covers both formats; the load-bearing decision
> (process isolation) is format-agnostic, with per-format decisions labelled and
> shipped as separate slices.

## Context

Neo 1.0's headline document-intelligence capability advertises parsing "across
formats," but today only `text/plain` and `text/markdown` parse for real; every
other declared type is rejected (`app/ai/documents/dispatch.py:34-37`,
`document_parser` default `"reject"`). Enterprise documents are overwhelmingly
PDF and Word, so this is Neo 1.0 blocker 2/3.

Four facts about the current pipeline shape this ADR:

1. **The parse runs inline in the async request handler.** The upload route wraps
   ingest in `asyncio.wait_for` (`app/presentation/http/routers/documents.py:99`),
   and ingest calls the parser in that same coroutine
   (`app/ai/documents/ingest.py:107`). `asyncio.wait_for` only cancels at `await`
   points; a synchronous, CPU-bound C-extension parse never yields, so it **blocks
   the event loop and ignores the timeout**. The codebase already states this: the
   parser Protocol docstring says _"a parser cannot reliably self-timeout
   mid-CPU-work"_ (`app/application/ports/documents.py:129`), and the route
   comments _"wait_for cannot interrupt CPU-bound sync work … 8f's real parser
   needs process-level isolation to defend against a CPU/decompression bomb"_
   (`documents.py`, block (c) at `:94-96`). **A real timeout or memory limit is
   only real where the parse can be hard-killed — a separate process.**

2. **Format honesty is an established principle.** ADR 0001 and the 8f-1 text
   parser forbid inferring semantic structure the format does not explicitly
   encode: `.txt` → `section=None`; `.md` → `section` only from explicit ATX
   headings. The 8a provenance model (`app/application/ports/documents.py:20`,
   `DocumentPosition` at `:79-102`) already anticipates the PDF/DOCX asymmetry:
   pages are a RANGE for genuinely paginated formats (PDF), `None` otherwise
   (DOCX paginates at render time), and `section` is nullable.

3. **The offset-exactness invariant must survive.** `ParsedDocument.full_text` is
   the concatenation of block texts (`ports/documents.py:72-77`) and the 8f-1
   parser tiles it gap-free so `full_text[char_start:char_end] == block.text`
   exactly.

4. **Validation and storage already exist.** The upload route runs a streaming
   size guard (→413), a 415 declared-type allowlist gate
   (`documents.py:80-84`), then stores original bytes (ADR 0002,
   `documents.py:92`) before parsing; the dispatcher routes by content type
   (`dispatch.py`), which explicitly reserves the magic-number slot: _"No
   magic-number sniffing here — that is the 8f-2 security slice"_
   (`dispatch.py:12`). Failures map to HTTP via the document exception hierarchy
   (`app/shared/exceptions/documents.py:12-34`): `DocumentTooLargeError`→413,
   `UnsupportedContentTypeError`→415, `DocumentParseError`/`DocumentDecodeError`
   →422.

This ADR decides how Neo parses real PDF and DOCX safely.

## Decision — the subprocess isolation harness (core, format-agnostic)

**Real PDF/DOCX parsing runs in a hard-killable child process, never inline in
the request handler.** This is the load-bearing decision; everything else hangs
off it. Inline parsing with an `asyncio` timeout is explicitly rejected as unsafe
(see Alternatives). The harness:

- **Spawns a fresh subprocess per parse** (see Decision C) whose entrypoint, before
  touching the bytes, sets POSIX resource limits — `RLIMIT_AS` (address space /
  memory) and `RLIMIT_CPU` — and enforces the page cap. It then parses and writes
  a structured result.
- **The parent enforces the wall-clock budget by killing the child** (`SIGKILL`)
  at `document_parse_timeout_seconds` (`settings.py:151`) — a real timeout, since
  a killed process stops regardless of what C code it was running. The parent
  awaits the child via an executor, so the event loop is never blocked.
- Runs the child **unprivileged, with no network and no storage access** — it
  receives bytes and returns structured data; a compromised parser (PDF CVEs are
  common) cannot reach the DB, the store, or the loop, and is killed at the budget.

This composes with ADR 0002's all-or-nothing + compensation: a killed/failed parse
→ ingest raises → the DB transaction rolls back → the storage compensating delete
fires (`documents.py:115-122`) → clean 4xx, no row, no orphaned bytes.

### Decision A — IPC / marshaling boundary (bytes in, structured result out)

- **The parent hands the child BYTES, never a filesystem path.** The parent obtains
  the bytes from the request (`upload.data`) or, for future reprocessing, via
  `StorageProvider.get` (ADR 0002) and **pipes them to the child's stdin**. Handing
  a path would couple the parser to the filesystem backend and break the moment
  storage becomes S3 — the child must be storage-agnostic.
- **The child returns a structured result on stdout, never a raw crash:**
  - Success → a JSON document: an ordered list of blocks, each `{text, page|null,
section|null}`, plus `content_type`. **JSON, not pickle** — the child processes
    untrusted input, so its output must be parsed by the parent with a
    non-executing format and validated into `ParsedDocument` via pydantic. Pickle
    is rejected (unpickling attacker-influenced output risks code execution in the
    parent).
  - Handled failure → a JSON error object `{error_class, message}` that the parent
    maps to the right exception/HTTP status (e.g. `"too_large"`→413,
    `"encrypted"`/`"parse_error"`/`"needs_ocr"`→422). The child catches parser
    exceptions and reports them structurally rather than crashing.
  - Hard failure (OOM-kill, timeout-kill, segfault, non-zero exit with no valid
    result) → the parent detects it (exit status / empty-or-invalid stdout /
    timeout) and maps it: timeout & memory-kill → `DocumentTooLargeError`/
    `DocumentParseError` (413/422), anything else → `DocumentParseError` (422).
    A crash is never surfaced raw.
- **The offset-exactness invariant survives the boundary because the child never
  sends offsets.** The child sends only `(text, page, section)` tuples in reading
  order. The **parent** builds `full_text` = join of block texts (the existing
  `ParsedDocument.full_text` property) and computes char offsets by cumulative
  block lengths (the 8f-1 tiling). JSON preserves the exact Unicode text, so
  `full_text[start:end] == block.text` holds **parent-side, by construction** —
  immune to any child bug about offsets.

### Decision B — Platform assumption (stated plainly, no abstraction)

`RLIMIT_AS`/`RLIMIT_CPU` are POSIX (the Python `resource` module, Linux). **CI and
the production/Docker target are Linux; a non-Docker macOS host is NOT a supported
runtime for real parsing.** We do **not** build a cross-platform limit abstraction.
On a macOS dev host, real parsing is unavailable — developers run the API in the
Linux container, or use the mock parser (`document_parser="mock"`). The real
subprocess parser is wired only where the platform supports the limits; elsewhere
the mock remains the path. This is a documented constraint, not a defect.

### Decision C — Process lifecycle: spawn-fresh-per-parse (slice 1)

**Slice 1 spawns a fresh subprocess for every parse** — a clean process each time,
no state leakage between documents, trivial to reason about, and trivial to
hard-kill. A **persistent process pool** is a later performance optimization and is
**explicitly deferred**; it carries its own hazard (a hung pool worker must be
killed _and replaced_, and a crashed worker recycled without leaking prior-document
state), which is not worth taking on before the harness is proven. Do not build the
pool now.

### Decision D — Request model: synchronous for 1.0

**Parsing is synchronous from the user's perspective — they wait for the upload
response — but isolated in the killable subprocess.** The upload endpoint keeps its
current request/response shape (no job id, no polling). **Async / queue-based
parsing is deferred to 2.0**, tied to the durable-background-jobs theme already in
the 2.0 register (`NEO_2.0_ENHANCEMENT_REGISTER.md`, item 5.1). This ADR introduces
no job queue.

## Per-format sub-decisions

### Sub-decision 1 — DOCX (slice 1)

- **`page = None`.** DOCX paginates at render time, not in the file (8a docstring),
  so there is no honest page number to record.
- **`section` = the enclosing heading from the explicit heading STYLE / outline
  level** (`Heading 1/2/3`, `w:outlineLvl`). This is explicit structure the format
  encodes — honest, exactly like Markdown ATX headings — **not** visual inference.
  **Hard rule: never derive a heading from font size, bold, or position.**
- DOCX is an OOXML **ZIP of XML**: parse = unzip + XML. Attack surface is
  zip/XML bombs and XXE — well-understood and defended below.

### Sub-decision 2 — PDF (slice 2)

- **`page_start`/`page_end` = the true page RANGE** a block spans, per the 8a
  `DocumentPosition` design (`render()` at `ports/documents.py:91-102` already
  yields `p. N` / `pp. N-M`).
- **`section = None`, always.** PDF does not reliably encode sections; a heading
  would have to be inferred from font size/position — the strongest temptation and
  precisely the "confident, wrong citation" the format-honesty principle forbids.
  The honest PDF locator is page range + char offsets; section stays `None`.
- **Image-only / scanned PDFs (no text layer) are detected and rejected** (see
  Failure handling); OCR is deferred to its own future item.

## Validation-order integration (magic-number sniff slots in, replaces nothing)

The new checks land in the existing order (`documents.py`), augmenting it:

1. Streaming **size guard** → 413 (`read_upload`, `documents.py:75`) — unchanged.
2. **415 declared-type allowlist** on the attacker-controlled `Content-Type`
   (`documents.py:80-84`) — unchanged.
3. **NEW: magic-number sniff** — after the 415 gate, before store: verify the
   leading bytes match the declared type (`%PDF-` for PDF, `PK\x03\x04` ZIP for
   DOCX). Mismatch → reject via `UnsupportedContentTypeError` (415, existing
   handler). Placed **before** the ADR-0002 store (`documents.py:92`) so a
   mislabeled file never orphans, and before the parser so a mislabeled bomb never
   reaches it.
4. **Store** original bytes (ADR 0002) — unchanged.
5. **Dispatcher** — extended, not rewritten (`dispatch.py`): add
   `application/pdf → PdfParser`, DOCX → `DocxParser`, keep `text/* →
TextParser`; the `fallback=None` reject path (`dispatch.py:34-37`) stays for
   types with no parser. Real PDF/DOCX parsers execute via the subprocess harness.
   The **mock stays the CI/test fabricator** (`document_parser="mock"`) and
   **reject stays the default** until each real parser is proven — the same
   config discipline storage used (filesystem behind config; safe defaults).

## Offset-invariant mechanism across the IPC boundary

Restated as a single guarantee: **offsets are computed in the parent, never sent
over IPC.** Child → `(text, page, section)` blocks in reading order (exact Unicode
via JSON). Parent → `full_text = "".join(b.text)` and char offsets from cumulative
lengths (8f-1 tiling), yielding `full_text[start:end] == block.text` by
construction. Consequences and honest costs:

- For PDF/DOCX, `full_text` is the **extracted** text, not the original bytes
  (there is no single "original text" in a PDF). This is already the model: the
  original bytes are retained separately (ADR 0002), and the invariant is about
  internal consistency, not fidelity to the file.
- **Any cleanup (dehyphenation, whitespace/reading-order reconstruction) must be
  finalized inside the child before block text is emitted** — whatever string is
  emitted _is_ `block.text`. No post-hoc reflow that desyncs offsets.
- **Extraction FIDELITY (ligatures, CID/Type3 fonts, bad ToUnicode maps) is a
  separate axis** from offset-exactness. Garbled extraction yields
  garbled-but-consistent text: offsets still round-trip; citation _text_ quality
  suffers. That cost belongs to the quality/OCR frontier, not to the invariant,
  which survives.

## Failure handling per document class — reject vs. degrade

Guiding rule: **reject (422) rather than degrade.** Never fabricate, never silently
produce a partial-but-complete-looking document (consistent with the
reject-unsupported-types slice and the "no partial document" invariant). Only a
genuinely-empty _valid_ file yields a zero-chunk document.

| Class                                                | Behaviour                                                                                                                                                        |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Corrupt / malformed**                              | Reject → `DocumentParseError` 422. Never a partial doc.                                                                                                          |
| **Encrypted / password-protected**                   | Detect, reject → 422 with a clear message. 1.0 does not attempt decryption or accept a password (a UX + security surface); do not degrade to empty.              |
| **Scanned / image-only (no text layer)**             | Detect (≈zero extracted text over ≥1 page) → reject → 422 "looks like a scanned document; OCR not supported yet." Never emit an empty/garbage doc. OCR deferred. |
| **Empty but valid** (e.g. a DOCX with no paragraphs) | `full_text == ""`, zero blocks, **no error** — the 8f-1 empty-file semantics.                                                                                    |
| **Invalid** (bytes aren't the declared format)       | Rejected by the magic-number sniff before parse (415/422).                                                                                                       |
| **Partial / truncated**                              | If the parser hits a structural/truncation error → reject 422. Never accept a truncated extraction as if complete.                                               |
| **Unsupported format**                               | Dispatcher `reject` fallback → 415 (existing).                                                                                                                   |

The empty-vs-scanned boundary (how little text over how many pages counts as
"scanned") is a tunable threshold — see Open Questions.

## Security protections — concrete limits

Enforced in the child (bytes/CPU/memory) and the sniff, all Linux:

- **Max upload size:** 10 MB — `document_max_bytes` (`settings.py:149`), already
  enforced streaming by `read_upload`. Bounds _input_.
- **Page cap:** 500 — `document_max_pages` (`settings.py:150`), **today reserved
  and consumed nowhere; it stays reserved until slice 2 (PDF)**, where the child
  enforces it (reject early once exceeded). DOCX (slice 1) has no page concept.
- **Wall-clock timeout:** 30 s — `document_parse_timeout_seconds`
  (`settings.py:151`), enforced by **killing the child** (now a real timeout).
- **Memory cap:** `RLIMIT_AS` in the child — a NEW setting
  `document_parse_max_memory_bytes`, **default 1 GB, configurable** (Open Question 1
  resolved). 512 MB risked OOM-ing a large-but-legitimate document's working set;
  1 GB tolerates real docs while still hard-killing unbounded allocation after the
  10 MB input.
- **Decompressed-size cap (DOCX):** bound total uncompressed bytes read from the
  ZIP — a NEW setting `document_docx_max_uncompressed_bytes`, **default 200 MB**
  (20× the 10 MB upload cap — generous for real files, lethal to zip bombs).
- **XXE disabled (DOCX XML):** disable external-entity resolution, DTDs, and
  network access (defusedxml, or lxml with `resolve_entities=False`,
  `no_network=True`). This defends XXE **and** the billion-laughs/entity-expansion
  class structurally, so **no explicit element-count cap ships in slice 1** — it is
  added only if defusedxml proves insufficient (Open Question 2 resolved).

## Future-format extensibility

New formats (XLSX, PPTX, RTF, HTML) slot in as new parsers behind the **same**
subprocess harness + a dispatcher route + a magic-number signature + the
per-format honesty rules — the harness, IPC, offset mechanism, and failure mapping
are format-agnostic. OCR for image-only PDFs is a heavier, separate capability
(its own dependency and cost) that would plug in later as a fallback for the
scanned-PDF class.

## Alternatives rejected

- **Inline parse with an `asyncio` timeout (the status quo for real parsing).**
  Rejected as unsafe: `wait_for` cannot interrupt CPU-bound C code
  (`ports/documents.py:129`, `documents.py:94-96`); it blocks the event loop and
  enforces no memory bound.
- **Threads instead of a subprocess.** Rejected: a CPython thread running C code
  cannot be hard-killed and shares the process memory/GIL — a bomb still OOMs the
  whole worker. Only a separate process can be `SIGKILL`ed and `RLIMIT`ed.
- **Persistent process pool in slice 1.** Deferred: state-leakage and
  hung/crashed-worker recycling complexity before the harness is proven.
- **Job queue / async parsing in 1.0.** Deferred to 2.0 (durable-background-jobs
  theme).
- **Pickle for the IPC result.** Rejected: unpickling output derived from
  untrusted input risks code execution in the parent; JSON + pydantic validation.
- **Handing the child a filesystem path.** Rejected: couples the parser to the
  filesystem backend; breaks under S3. Pipe bytes.
- **A cross-platform resource-limit abstraction.** Rejected: Linux/Docker is the
  target (Decision B).
- **Inferring PDF sections from layout/fonts.** Rejected (format honesty).
- **PDF first.** Rejected for slice 1: DOCX is the lower-risk format to prove the
  harness (Alternatives → slice order).

## Consequences

- **Positive.** Real timeouts and memory limits become achievable (they are not,
  inline). PDF/DOCX — the bulk of enterprise documents — become ingestible,
  closing blocker 2/3. Parser CVEs are contained to an unprivileged, network-less,
  killable child. Provenance stays honest (PDF pages, DOCX heading styles). The
  offset invariant is preserved parent-side. Composes with ADR 0002 cleanup.
- **Negative.** A subprocess-per-parse adds spawn + IPC overhead. A new child
  entrypoint and several new limit settings enlarge the surface. Real parsing is
  Linux-only (macOS dev must use the container/mock). Reject-not-degrade turns
  some salvageable-ish files away. Extraction fidelity varies and (for scanned
  PDFs) is bounded until OCR lands.

## Risks

- **Spawn overhead per parse** — bounded by the 30 s budget; the pool is the future
  optimization.
- **PDF library CVEs** — mitigated by isolation + rlimits + unprivileged,
  network-less child, killed at budget.
- **IPC volume** (pipe ≤10 MB in, return MBs of JSON) — bounded, acceptable at the
  10 MB cap; streaming IPC is a future refinement.
- **Empty-vs-scanned false positives** (sparse-text PDF misflagged) — a PDF/slice-2
  concern; the text-per-page floor is calibrated then, not guessed now.
- **Platform constraint** — real parsing unavailable on macOS host; documented.
- **New settings mis-tuned** (memory/decompressed caps too low → reject valid docs;
  too high → weak bomb defense) — defaults chosen deliberately generous: 1 GB
  `RLIMIT_AS`, 200 MB decompressed (20× the 10 MB input cap).

## Implementation plan (small, independently testable slices)

1. **Subprocess isolation harness + DOCX text parser (slice 1).** The child
   entrypoint (bytes on stdin → `RLIMIT_AS` (1 GB) / `RLIMIT_CPU` → parse → JSON
   result/error on stdout; no page cap — DOCX has no pages); the parent harness
   (spawn-per-parse, pipe bytes, kill at timeout, map result/failure); `DocxParser`
   (paragraph blocks, `page=None`, `section` from explicit heading styles, XXE off
   via defusedxml, 200 MB decompressed cap — no element-count cap); the DOCX
   magic-number sniff; **per-format dispatcher registration** `docx → DocxParser`
   (mock stays CI/macOS default, reject stays production default for every other
   type — **PDF still rejects after this slice**). Offsets computed parent-side via
   tiling. **Tests (hermetic, no OCR/network):** offset round-trip on a real
   `.docx`; heading-style → `section`, plain paragraph → `None`; zip-bomb and
   entity-expansion (billion-laughs) rejected (not parsed); a deliberately hung
   parse is killed at the timeout (proving the timeout is now real); over-1 GB
   allocation / over-200 MB-decompressed rejected; magic-number mismatch rejected;
   and — composing with ADR 0002 — a parse failure leaves no row and no orphaned
   bytes.
2. **PDF parser on the same harness (slice 2).** Registers `application/pdf →
PdfParser` in the dispatcher (PDF stops rejecting here, not before); page-range
   provenance; **`document_max_pages` (`settings.py:150`) becomes live and enforced
   in the child** (reserved until now); `section=None`; encrypted/password PDFs
   rejected outright; image-only detection with the calibrated text-per-page floor
   → reject (OCR message); `%PDF-` sniff.
3. **Parsing observability + limit tuning (slice 3).** Structured failure logging,
   parse metrics, tune the new caps against real corpora.
4. **Persistent process pool (later, perf — 2.0-ish).** With hung/crashed-worker
   recycling; explicitly not now.
5. **OCR for image-only PDFs (later item).** Heavy dependency; separate capability.
6. **Async/queue-based parsing (2.0).** Durable-background-jobs theme.

**Slice 1 is the first to build and commit:** the subprocess isolation harness +
DOCX, the smallest _safe_ increment — it proves the harness on the lower-risk
format while making real parsing possible at all, consistent with how storage
shipped its safest backend first. PDF follows immediately on the proven harness.

---

## Assumptions

1. **Linux/Docker is the runtime for real parsing** (POSIX `resource` limits);
   macOS host uses the container or the mock. CI is Linux.
2. **Bytes fit in memory** (10 MB cap, `settings.py:149`), so piping to child
   stdin is fine; streaming IPC is a future refinement.
3. **The mock parser stays the CI-unit / non-Linux-dev default**
   (`document_parser="mock"`), and **reject stays the production default** until
   each real parser is proven (per-format).
4. **ADR 0002 storage is in place**: the parent gets bytes from the request or
   `StorageProvider.get`; the child never touches storage.
5. **Offset-exactness ≠ extraction fidelity**: garbled-but-consistent text is
   acceptable at the parsing layer; fidelity/quality is a separate axis.
6. **`document_max_pages` becomes live** (it is reserved today, `settings.py:150`),
   enforced in the child.

## Trade-offs

- **Isolation cost vs. safety** — spawn-per-parse + IPC overhead bought in exchange
  for a _real_ timeout and memory kill; the pool reclaims the cost later.
- **Synchronous request vs. responsiveness** — the user waits for the parse;
  simplest and correct for 1.0; async is a 2.0 durable-jobs concern.
- **Reject-not-degrade vs. best-effort extraction** — preserves the no-partial-doc
  and no-wrong-citation invariants at the cost of turning some marginal files away.
- **JSON IPC vs. faster binary** — safety (no untrusted deserialization) and no new
  dependency over raw speed.
- **DOCX-first vs. PDF-first** — PDF is the bigger user need, but proving the
  harness on the safer format first de-risks the harness before the hostile input.
- **One ADR vs. split** — one ADR keeps the shared harness a single source of
  truth; per-format specifics are labelled sub-decisions shipped as separate slices.

## Open Questions — Resolved

All seven were resolved by the decider on 2026-07-22; rulings and reasoning
recorded below and reflected in the security-limits, slice, and settings notes.

1. **Memory cap (`RLIMIT_AS`) — RESOLVED: 1 GB default, configurable.** 512 MB
   risks OOM-ing a large-but-legitimate document's working set; 1 GB tolerates
   real docs while still hard-killing unbounded allocation. `document_parse_max_
memory_bytes` defaults to 1 GB and is tunable per deployment.
2. **DOCX caps — RESOLVED: decompressed total ≤ 200 MB; rely on defusedxml with
   entity expansion disabled for the billion-laughs class.** 200 MB is 20× the
   10 MB upload cap — generous for real files, lethal to bombs. Disabling entity
   resolution defends the XML-expansion attack structurally, so an explicit
   element-count cap is **deferred unless defusedxml proves insufficient** (no
   element-count setting in slice 1).
3. **Empty-vs-scanned threshold — RESOLVED: DEFER to slice 2 (PDF-only, not in
   slice 1).** Calibrate the text-per-page floor at slice 2 against real scanned
   and sparse-legitimate PDFs rather than guessing now.
4. **Config surface — RESOLVED: per-format enablement, not a single global flag.**
   DOCX and PDF ship in different slices and must be independently enable-able; the
   real parser is registered **per content-type in the dispatcher** as each slice
   lands. `mock` stays the CI/macOS default; `reject` stays the production default
   for any not-yet-proven format. **After slice 1: DOCX parses for real, PDF still
   rejects.**
5. **Encrypted / password PDFs — RESOLVED: reject outright in 1.0.** Accepting
   passwords adds UX and secret-handling surface not wanted in a pilot. Policy
   settled now; the detection/rejection mechanics are slice 2.
6. **Truncated / partial files — RESOLVED: reject on structural error; never
   accept a partial extraction as complete.** This is the no-partial-document
   invariant applied to parsing.
7. **Parser libraries — RESOLVED: slice-time dependency review, not settled here,
   with two binding constraints.** (a) The chosen libraries MUST run fully headless
   with no network; (b) their CVE history MUST be reviewed at slice time as part of
   the choice. **DOCX XML must be parsed with entity resolution disabled regardless
   of library.**
