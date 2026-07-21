# 0001. BlockAwareChunker

Status: Accepted (amended 2026-07-21 — see Amendment 1: flip gate changed)
Date: 2026-07-21
Deciders: retrieval/ingest owners
Supersedes: none

> Design-only ADR. No implementation is included. Every statement about current
> behaviour cites `path:line` (paths relative to repo root). Where the code does
> not settle a question, it is left as an Open Question rather than resolved
> silently.

## Context

Document ingest today parses a file into an ordered list of `ParsedBlock`s
(`apps/api/app/application/ports/documents.py:48-59`) whose concatenation is the
canonical `full_text` (`.../ports/documents.py:62-76`, property `71-76`). The
8f-1 text parser guarantees those blocks **tile `full_text` gap-free and without
overlap** (`apps/api/app/ai/documents/text.py:5-8,25-31`), so paragraph and
Markdown-section boundaries are known with exact character offsets at ingest
time.

The one chunker, `FixedSizeChunker`, then **discards those boundaries as split
points** and re-slides a fixed character window over the flat `full_text`:
`stride = chunk_size - overlap` (`apps/api/app/ai/documents/chunker.py:55`), a
loop cutting `full[start:end]` with `end = min(start + chunk_size, n)`
(`chunker.py:60-84`). Blocks are consulted **only** for provenance lookup, via a
precomputed `block_ends` prefix array and a `bisect` back to the containing block
(`chunker.py:44-53`); `section` is taken from the chunk's _first_ block
(`chunker.py:77`) and `page_start/page_end` from the first/last block
(`chunker.py:74-75`).

The V1 retrieval benchmark baseline
(`apps/api/tests/fixtures/retrieval-benchmark/neo_retrieval_benchmark_v1_spec.md`,
appended results block; corpus `neo_retrieval_benchmark_v1.txt`) measured this
exact behaviour at commit `24937e8`, config `chunk_size=1000, overlap=200,
floor=0.50, top_k=5, voyage-3.5 (1024d)`:

- **23 chunks**; scores compressed to **50.9–66.6%**.
- **Minimum margin above the 0.50 floor = 0.009** (Q4 `work from abroad`,
  0.5086; Q3 `bereavement`, 0.5118).
- **Q1 (`annual leave`)** top chunk `3200–4200` _opens mid-sentence in Section 2
  remote-work_; the "26 days" answer sits ~560 chars in, behind a section
  boundary — a wrong-section lead-in produced by the first-block `section` rule
  (`chunker.py:77`).
- **One chunk (`3200–4200`) is the top hit for two unrelated queries**, Q1 and
  Q4, because that fixed window straddles Section 2 → Section 3.
- **Q6 negative control** (`dental`) returned **0 results** — the floor
  (`apps/api/app/presentation/http/routers/documents.py:149-150`) correctly
  rejected everything.

These are structural artefacts of ignoring the block boundaries the parser just
computed. This ADR decides whether and how to introduce a `BlockAwareChunker`
behind the existing `Chunker` Protocol
(`.../ports/documents.py:135,141`).

The three suggestions carried into this ADR — carry the final whole block as
overlap, `section=None` on span, oversized-block fixed-window fallback — are
treated as **proposals to evaluate**, not requirements.

---

## Decision 1 — Chunking algorithm

**Current behaviour.** Fixed character window over `full_text`, block boundaries
ignored as split points (`chunker.py:55,60-84`). A chunk may begin and end
anywhere, including mid-word and mid-sentence (the V1 Q1 chunk starts mid-word,
`"nt. Requests to work remotely…"`).

**Decision.** Introduce `BlockAwareChunker`, a second `Chunker` implementation
(`.../ports/documents.py:135,141`) that packs **whole `ParsedBlock`s greedily**
in document order into a chunk until adding the next block would exceed
`chunk_size` (characters — units unchanged, `apps/api/app/infrastructure/config/settings.py:129`),
then starts a new chunk. Because blocks tile `full_text` exactly
(`text.py:5-8,25-31`), a packed run of consecutive blocks is a contiguous slice
`full_text[start:end]`, so offsets stay exact with no drift. Markdown section
(heading) boundaries are **preferred** split points (see Decision 4). Oversized
single blocks fall back to windowing (Decision 2).

**Alternatives considered.**

- _Keep `FixedSizeChunker` only (do nothing)._ Rejected: the V1 findings
  (wrong-section lead-in, one chunk serving two queries, 0.009 floor margin) are
  structural and unfixable by tuning `chunk_size`/`overlap`; both are pure
  arithmetic knobs (`chunker.py:55`).
- _Sentence-boundary chunker._ Rejected for now: needs sentence segmentation
  (a new dependency or heuristic), is not deterministic across locales without
  care, and the parser already hands us paragraph/section structure for free
  (`text.py:25-31`). A sentence strategy remains additive behind the same
  Protocol later.
- _Semantic / embedding-similarity chunking._ Rejected: requires embedding
  before chunking (inverting the ingest order in `apps/api/app/ai/documents/ingest.py:111-115`),
  is non-deterministic run-to-run, and is far more than the V1 gaps warrant.

**Consequences.**

- (+) Chunks align to paragraph/section edges; no mid-word starts for
  normal-sized paragraphs; the Q1 wrong-section lead-in and the shared-chunk
  problem are directly targeted.
- (+) More topically coherent chunk text → _plausibly_ higher on-topic scores
  and more floor headroom (**to be measured**, not asserted — see Decision 9).
- (−) Chunk sizes become variable; a chunk can be well under `chunk_size` when a
  section ends early. Shorter chunks carry less surrounding context, which can
  _lower_ recall for queries that need cross-paragraph context (Q2 is a semantic,
  zero-shared-word match at 0.524 and is the most at risk).
- (−) More branching logic than a bisect loop; higher constant factor
  (Decision 11).

---

## Decision 2 — Oversized block handling

**Current behaviour.** Not applicable per-block: `FixedSizeChunker` never sees a
block as a unit — it windows the whole `full_text` (`chunker.py:60-84`), so an
over-long paragraph is simply cut by the global window like everything else.

**Decision.** **Accept the proposal.** When a _single_ block's length exceeds
`chunk_size`, split _that block only_ with the existing fixed-window logic
(`stride = chunk_size - overlap`, `chunker.py:55,60-84`) over the block's own
character span; every resulting sub-chunk carries that block's `page` and
`section` (one block ⇒ one section/page) and offsets taken from the window inside
the block. Block-aware packing resumes at the next block.

**Alternatives considered.**

- _Reject the block whole (emit a >`chunk_size` chunk)._ Rejected: it would
  exceed the token-cap guard that `chunk_size` exists to satisfy
  (`ingest.py:18-25,56-66` — `validate_chunk_size_within_token_cap`), risking
  silent truncation at embed time.
- _Split oversized blocks on sentence boundaries._ Rejected here for the same
  reasons as Decision 1's sentence alternative; the fixed window is already
  proven and confined to the rare oversized case.

**Consequences.**

- (+) Reuses trusted logic; confines mid-word splitting to genuinely oversized
  blocks (long code fences, tables, single mega-paragraphs).
- (+) Sub-chunks of one block share one honest `section`/`page`.
- (−) Those sub-chunks reintroduce the exact imprecision the ADR is trying to
  remove — but only within an over-long block, which is rare for prose.

---

## Decision 3 — Overlap semantics

**Current behaviour.** Overlap is a **character count**: consecutive windows
share `overlap` characters because `stride = chunk_size - overlap`
(`chunker.py:55`); `0 <= overlap < chunk_size` is enforced at construction
(`chunker.py:30-33`). Default `overlap = 200` (`settings.py:132`).

**Decision.** Redefine overlap for block-aware packing as a **whole-block carry
budget in characters**: after closing a chunk, seed the next chunk with the
trailing whole block(s) of the one just closed, taking as many _complete_
trailing blocks as fit within `overlap` characters (the proposal's "final block"
is the common case of this rule when only one fits). A carried block is the
immediate predecessor of the new chunk's first fresh block, so the chunk stays a
contiguous `full_text` slice. **Hard guard:** every chunk must introduce at least
one _new_ block beyond the carried overlap, or forward progress fails — reject
configurations that cannot guarantee this at construction, mirroring
`chunker.py:30-33`.

**Alternatives considered.**

- _Character overlap as today._ Rejected: a character carry re-creates mid-block
  fragments at chunk starts, undoing Decision 1's boundary alignment.
- _No overlap._ Rejected: an answer straddling a chunk boundary would be
  recoverable from neither chunk; overlap is cheap insurance.
- _Carry exactly one block always._ Rejected as too rigid: one block may exceed
  the budget (carry nothing) or be tiny (carry more for continuity); the
  budgeted multi-block rule subsumes it.

**Consequences.**

- (+) Overlap regions are whole paragraphs — semantically meaningful continuity.
- (+) Duplicated offsets across chunks are honest and identical to how character
  overlap already duplicates ranges today.
- (−) Overlap size is now variable and data-dependent; harder to reason about
  "how much" overlap a corpus has.
- (−) A pathological run of tiny blocks plus a large budget could carry many
  blocks; the forward-progress guard bounds correctness but not cost.

---

## Decision 4 — Markdown heading handling

**Current behaviour.** The 8f-1 parser already derives `section` from the nearest
preceding ATX heading and attaches it per block (`text.py` module docstring,
"SECTIONS"; `section` field `.../ports/documents.py:59`); `.txt` always yields
`section=None` (deliberate, `text.py` docstring). `FixedSizeChunker` then keeps
only the _first_ block's section (`chunker.py:77`), which is what produced the
V1 Q1 wrong-section citation.

**Decision.** Treat a **heading (a change in a block's `section` value)** as a
_preferred_ split point: when the packer is at or past a soft fill threshold and
the next block belongs to a new section, close the current chunk rather than pack
across the heading. Do **not** make headings _hard_ splits (that would shatter a
document of many short sections into many tiny, context-poor chunks). A heading
block packs together with the body beneath it (they share the derived `section`),
so a chunk normally represents one section.

**Alternatives considered.**

- _Hard split at every heading._ Rejected: pathological for heading-dense docs;
  produces sub-`chunk_size` chunks that embed with little context (the Q2 recall
  risk, amplified).
- _Ignore headings (pack purely by size)._ Rejected: reproduces the V1
  shared-chunk / wrong-section artefacts.

**Consequences.**

- (+) Chunks map cleanly to sections; citations name the right section; Q1-style
  wrong-section lead-ins disappear for well-sized sections.
- (−) A "soft fill threshold" is a new tunable with no obviously-correct default
  (Open Question). Set too low → many tiny chunks; too high → headings ignored.
- (−) No effect on `.txt` (always `section=None`, `text.py`) — the benefit is
  Markdown-only until a real PDF/DOCX parser lands (dispatch currently routes
  only `text/plain`/`text/markdown` to the real parser,
  `apps/api/app/ai/documents/dispatch.py`; everything else is the mock).

---

## Decision 5 — Provenance (`char_start/char_end`, `page_start/page_end`, `section`)

**Current behaviour.** `char_start/char_end` are the window offsets
(`chunker.py:72-73`); `page_start = first.page`, `page_end = last.page`
(`chunker.py:74-75`); `section = first.section` (`chunker.py:77`). These persist
to the `document_chunks` columns `char_start/char_end` (NOT NULL),
`page_start/page_end` (nullable), `section` (nullable)
(`apps/api/app/infrastructure/db/models/documents.py:102-106`;
migration `apps/api/alembic/versions/f4a1c2d3e5b6_documents.py:92-96`). The
citation string is rendered from these by `DocumentPosition.render()`, which
falls back **page → section → char range** (`.../ports/documents.py:91-102`,
fallback `96-102`).

**Decision.**

- **`char_start/char_end`:** first packed block's global start to last packed
  block's global end (window offsets inside the block for the Decision 2
  fallback). Exact by the tiling guarantee (`text.py:5-8,25-31`). Positive
  change: chunk boundaries land on paragraph edges, so citations no longer start
  mid-sentence as in V1.
- **`page_start/page_end`:** keep the first/last rule (`chunker.py:74-75`).
  Inert for txt/md (`page` always `None`, `text.py`), correct for a future
  paginated parser.
- **`section`:** the shared section when **all** packed blocks carry the same
  `section`; **`None`** when the chunk genuinely spans more than one section.
  **This adopts the `section=None`-on-span proposal, but only because Decision 4
  makes spans rare.** The blanket proposal _without_ Decision 4 is **rejected**:
  under render()'s fallback (`.../ports/documents.py:96-102`), a `None` section
  on a txt/md chunk degrades the citation to a bare `chars N-M` range — so nulling
  a chunk that is 95% one section would make citations _worse_, not better. Nulling
  is acceptable only when spans are the exception.

**Alternatives considered (for `section`).**

- _First block's section (today)._ Rejected: this is the V1 Q1 defect
  (`chunker.py:77`).
- _Dominant section by character coverage._ Rejected: a 51/49 split still labels
  the citation with a section wrong for ~half the chunk — a confident-but-wrong
  citation, the exact failure the benchmark's negative control guards against.
- _Store multiple sections._ Rejected: `section` is a single `String(255)`
  (`models/documents.py:106`); a list is a schema and render() change out of
  scope here (noted as an Open Question).

**Consequences.**

- (+) Section labels are either right or explicitly absent — never wrong.
- (−) Multi-section chunks lose the section label entirely and cite a char range;
  acceptable only if Decision 4 keeps them rare.
- (−) `page` provenance remains untested against a real paginated parser (none
  exists; PDF/DOCX are still the mock via `dispatch.py`).

---

## Decision 6 — Deterministic behaviour

**Current behaviour.** `FixedSizeChunker` is a pure deterministic function of
`(document_id, ParsedDocument, chunk_size, overlap)` — arithmetic only, no clock
or RNG (`chunker.py:37-85`); the docstring calls determinism a requirement for
"reproducible embeddings + testable" (`chunker.py:4-6`).

**Decision.** `BlockAwareChunker` **must** preserve this: same `ParsedDocument`
(an ordered block list, `.../ports/documents.py:62-76`) + same config ⇒
byte-identical chunk texts and offsets. Greedy packing with fixed tie-breaking,
no wall-clock, no randomness, iteration strictly in `document.blocks` order.

**Alternatives considered.** _Allow content-adaptive/randomised packing (e.g.
balance chunk sizes)._ Rejected: breaks embedding reproducibility and makes the
benchmark non-comparable (the spec mandates re-running **unchanged**,
`neo_retrieval_benchmark_v1_spec.md` Method).

**Consequences.**

- (+) Benchmark comparability and reproducible embeddings preserved.
- (−) No load-balancing of chunk sizes; a section that ends 10% into a window
  yields a short chunk by design.

---

## Decision 7 — Configuration strategy

**Current behaviour.** `build_chunker(settings)` unconditionally returns
`FixedSizeChunker(chunk_size=document_chunk_size, overlap=document_chunk_overlap)`
(`apps/api/app/ai/documents/__init__.py:52,56`); there is deliberately **no
selector** yet (`__init__.py:11`). Fields: `document_chunk_size=1000`,
`document_chunk_overlap=200`, units characters (`settings.py:129-132`).

**Decision.** Add a `document_chunker: Literal["fixed", "block_aware"]` Settings
field and a selector in `build_chunker`, mirroring the parser selector pattern
(`build_document_parser`, `__init__.py`, and `dispatch.py`). Keep `chunk_size`
and `overlap` shared fields (Decision 3 reinterprets `overlap` as the carry
budget). **Default stays `"fixed"`** until `block_aware` passes the benchmark
(Decision 9); then flip the default in a follow-up. This makes the two chunkers
**coexist behind configuration**, A/B-testable by flipping the flag and re-running
the benchmark under one config (the spec forbids mixing configs mid-run).

**Alternatives considered.**

- _Hard-replace `FixedSizeChunker`._ Rejected: no benchmark evidence yet, and it
  strands already-indexed documents (Decision 8).
- _Per-request/per-document override._ Rejected: violates the spec's
  one-config-per-run rule and complicates provenance further.

**Consequences.**

- (+) Safe rollout; instant rollback by config; clean A/B.
- (−) Two chunkers to maintain behind the Protocol.
- (−) A global flag records the _current_ choice but not what produced a
  _given row_ — see Decision 8's finding.

---

## Decision 8 — Migration for documents already indexed with `FixedSizeChunker`

### Finding: chunker provenance is not recorded per row

`document_chunks` stores, per row: `document_id`, `organization_id`, `ordinal`,
`text`, `embedding`, `embedding_model`, `char_start/char_end`,
`page_start/page_end`, `section`
(`models/documents.py:96-106`; migration `f4a1c2d3e5b6_documents.py:88-96`).
There is **no column identifying which chunker produced the row.** A
`FixedSizeChunker` row and a `BlockAwareChunker` row are **schema-identical and
indistinguishable.**

Contrast `embedding_model`: it _is_ stored per row (`models/documents.py:99`,
migration `:91`), written from the provider's reported model at ingest
(`ingest.py:121`, `add_chunks(... embedding_model=embedding_model ...)`
`repositories.py:377`), and **used to filter at query time** so a model swap
cannot mix vector spaces (`repositories.py:422-423`). Chunking algorithm has **no
equivalent** — you cannot query, filter, or A/B by it from the table. **Stated
plainly: today, given a row, there is no way to tell which chunker made it.**

**Can they coexist in one table?** **Yes.** Both satisfy identical columns and
the `(document_id, ordinal)` uniqueness constraint (`models/documents.py:112`,
migration `:114`); a document is chunked by exactly one algorithm at ingest
(`ingest.py:111`), so within a document all chunks share an algorithm, and search
ranks each chunk independently by cosine within one `embedding_model` space
(`repositories.py:413,422-426`) then floor-filters
(`routers/documents.py:149-150`). Mixing across documents is therefore
**correctness-safe** but **measurement-blind**.

**Decision.**

1. **Add a nullable per-row `chunker` (or `chunker_version`) column**, written at
   ingest exactly as `embedding_model` is (`repositories.py:377`,
   `ingest.py:121`). `NULL` legacy rows are read as `"fixed"` (all existing rows
   predate the change). This turns the finding from "indistinguishable" into
   "labelled", enabling measurement, selective re-chunking, and future
   query-time filtering if ever needed.
2. **Forward-only by default:** new uploads use the configured chunker; existing
   rows are left as-is. No silent re-chunking.
3. **Provide an explicit backfill job** (not automatic) that re-chunks a document
   from its **stored `full_text`** (`models/documents.py:69-70`) and re-embeds.
   This is feasible _without the original bytes_, which are deliberately **not
   stored** (`routers/documents.py:50-57`). **Caveat:** `BlockAwareChunker`
   needs `ParsedBlock` boundaries, and only the flat `full_text` is persisted —
   the blocks are not. For txt/md the parser is a deterministic function of the
   text and `full_text` equals the decoded file exactly (`text.py:5-8`), so
   re-encoding `full_text` and re-parsing reproduces the same blocks. For
   PDF/DOCX (still the mock, `dispatch.py`) blocks cannot be faithfully
   reconstructed from `full_text`; those documents can only be re-chunked by
   **re-upload**, consistent with the existing no-original-bytes stance
   (`routers/documents.py:50-57`).

**Alternatives considered.**

- _No provenance column, rely on the global config flag._ Rejected: the flag is
  point-in-time; it cannot label historical rows, so the benchmark can never
  attribute a score delta to the chunker with confidence.
- _Auto re-chunk everything on deploy._ Rejected: unbounded real Voyage cost and
  latency, and it would silently rewrite the V1 baseline corpus mid-flight.
- _Require re-upload only (no `full_text` backfill)._ Rejected as the default for
  txt/md because `full_text` makes cheaper re-chunking possible; kept as the only
  option for mock-parsed formats.

**Consequences.**

- (+) Rows become attributable; A/B and selective migration become possible.
- (+) Backfill reuses stored `full_text`, avoiding re-parse of original bytes
  (which don't exist).
- (−) A schema migration (new column) plus writer changes in
  `add_chunks`/`ingest`.
- (−) Re-chunk backfill re-embeds → real Voyage cost and 429 exposure (the V1 run
  already hit 429s; see the results block).
- (−) A corpus mid-migration is a mix of algorithms; benchmark runs must pin a
  clean single-algorithm corpus (the spec already forbids mixing).

---

## Decision 9 — Benchmark expectations

**Current behaviour.** V1 baseline captured under `FixedSizeChunker` (results
block in `neo_retrieval_benchmark_v1_spec.md`): 23 chunks; 50.9–66.6%; min floor
margin 0.009; Q1 wrong-section; one chunk serving Q1+Q4; Q6 = 0 results.

**Decision.** Adopt these as the **acceptance gate** for flipping the default to
`block_aware`, and re-run the benchmark **unchanged** under a single
`block_aware` config (spec Method). Directional expectations — **hypotheses to
verify, not guarantees**:

| Metric                             | V1 (fixed)  | Expectation under block_aware                                | Confidence                    |
| ---------------------------------- | ----------- | ------------------------------------------------------------ | ----------------------------- |
| Chunk count                        | 23          | **Will change** — do not assume 23; likely similar or higher | given                         |
| Q1 top-chunk section               | opens in §2 | anchored in §3 leave content                                 | high — direct target of D1/D4 |
| Q1 vs Q4 sharing chunk `3200–4200` | shared      | separate chunks                                              | high — D1/D4                  |
| On-topic scores                    | 50.9–66.6%  | plausibly higher (less off-topic dilution)                   | **low — must measure**        |
| Min floor margin                   | 0.009       | plausibly wider                                              | **low — must measure**        |
| Q6 negative control                | 0 results   | **must stay 0**                                              | hard invariant                |
| Q2 (semantic, 0 shared words)      | 0.524       | **at risk of dropping** (less context)                       | flagged risk                  |

**Hard invariants (regressions that block the flip):** Q6 must remain 0 results;
no Q1–Q5 answer that passed may fall below the floor. Q2 is the canary for the
"shorter chunks lose context" risk.

**Alternatives considered.** _Assert block_aware is better and flip now._
Rejected: the ADR must not claim score improvements it cannot prove; the
benchmark exists precisely to decide this.

**Consequences.**

- (+) An objective, pre-registered gate; the negative control protects against a
  chunker that merely matches more.
- (−) Requires a full benchmark re-run per candidate config (Voyage cost, 429
  exposure).

---

## Decision 10 — Edge cases

**Current behaviour** where defined: empty `full_text` ⇒ `[]`
(`chunker.py:39-40`); overlap validated `0 <= overlap < chunk_size`
(`chunker.py:30-33`); ordinals sequential from 0 (`chunker.py:57,81`); empty file
⇒ zero blocks (`text.py:34,113-114`); whitespace-only file ⇒ a single block
(`text.py` docstring "Degenerate").

**Decision.** `BlockAwareChunker` must define, deterministically:

| Case                                                       | Required behaviour                                                                                  |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Zero blocks (empty file)                                   | return `[]` — match `chunker.py:39-40`                                                              |
| One block ≤ `chunk_size`                                   | one chunk = that block; `section`/`page` from it                                                    |
| One block > `chunk_size`                                   | Decision 2 fixed-window fallback                                                                    |
| Many tiny blocks                                           | pack up to `chunk_size`; if they cross sections, Decision 5 (`section=None`)                        |
| Block exactly = `chunk_size`                               | emit as its own chunk; next starts fresh                                                            |
| Whitespace-only single block (`text.py`)                   | one chunk (or D2 fallback if oversized); `section=None`                                             |
| Lone trailing heading block                                | packs with following body; if none follows, it is its own one-block chunk                           |
| `overlap` ≥ `chunk_size`, or overlap that starves progress | reject at construction — mirror `chunker.py:30-33` + Decision 3 forward-progress guard              |
| Contiguity                                                 | offsets come straight from block spans; exact because blocks tile `full_text` (`text.py:5-8,25-31`) |
| `(document_id, ordinal)` uniqueness                        | ordinals 0..n−1, contiguous — satisfy `models/documents.py:112`                                     |

**Alternatives considered.** _Leave edge cases to the implementation._ Rejected:
the empty/oversized/overlap cases are exactly where offset drift and
non-termination hide; they are decisions, not details.

**Consequences.**

- (+) Termination and offset-exactness are specified, not emergent.
- (−) More cases to test than the fixed windower (the fixed one has essentially
  three).

---

## Decision 11 — Complexity analysis vs the current implementation

**Current (`FixedSizeChunker`).** Builds `block_ends` in O(b) for `b` blocks
(`chunker.py:44-48`); emits ~`n/stride` chunks (`n = len(full_text)`), each doing
a `bisect_right` over `block_ends` twice, O(log b) (`chunker.py:50-53,62,65`).
Total ≈ **O(n + (n/stride)·log b)** time, O(n) output memory.

**Proposed (`BlockAwareChunker`).** Single pass over `b` blocks with greedy
packing, each block appended once; the packer tracks the running section/page
directly, so **no `bisect` is needed**. Oversized blocks add O(block_len/stride)
sub-chunks (Decision 2); summed block lengths = n, so the fallback total is
bounded by O(n/stride). Total ≈ **O(b + n/chunk_size) = O(n)** time (since
`b ≤ n`), O(n) output memory.

**Decision.** Accept the same asymptotic class (O(n) time, O(n) memory) with a
modestly higher constant (packing/overlap bookkeeping, section-span tracking)
offset by dropping the per-chunk `bisect`.

**Alternatives considered.** _Precompute a section index for O(1) span checks._
Rejected as premature: the linear pass already tracks section changes for free.

**Consequences.**

- (+) No asymptotic regression; fewer per-chunk lookups.
- (−) More conditional logic per block; slightly larger code surface to test.

---

## Assumptions (the design depends on all of these)

1. Blocks **tile `full_text` gap-free, in order, exactly** — the offset-exactness
   of every provenance claim here rests on `text.py:5-8,25-31`. If a future
   parser violates tiling, block-aware offsets break.
2. Chunking consumes `ParsedDocument.blocks`; `full_text` is `"".join(block.text)`
   (`.../ports/documents.py:62-76`). Only `full_text` is persisted
   (`models/documents.py:69-70`); blocks are not — hence the re-parse caveat in
   Decision 8.
3. A document is chunked by exactly one algorithm at ingest (`ingest.py:111`), so
   within-document rows are homogeneous.
4. Retrieval ranks each chunk independently by cosine within one `embedding_model`
   space and floor-filters (`repositories.py:413,422-426`;
   `routers/documents.py:149-150`); no cross-chunk assumption is broken by mixing
   algorithms across documents.
5. Real structured `section` exists only for Markdown today; `.txt` is always
   `section=None` and PDF/DOCX are the mock (`dispatch.py`, `text.py`). Section
   benefits are Markdown-only until a real paginated/structured parser lands.
6. `chunk_size` (characters) must stay under the embedding token cap
   (`ingest.py:56-66`); Decision 2 preserves this.
7. Voyage embedding is the active provider for any real re-chunk/benchmark
   (per prior slice); backfill incurs real API cost and 429 exposure.

## Trade-offs (each, and what is sacrificed)

- **Boundary alignment vs chunk-size uniformity** — sacrifices predictable,
  balanced chunk sizes for section-honest boundaries (Decision 1, 6).
- **Coherence vs context** — coherent short chunks may lose the surrounding
  context a semantic query needs; sacrifices some recall (Q2 canary) for
  precision/citation quality (Decision 1, 4, 9).
- **Section honesty vs label availability** — `section=None` on span never
  misleads but sacrifices a usable label (citation drops to a char range via
  render()'s fallback), tolerable only because spans are made rare (Decision 5).
- **Coexistence safety vs maintenance** — two chunkers behind config is safe and
  A/B-able but sacrifices simplicity (Decision 7).
- **Measurability vs schema stability** — a per-row `chunker` column buys
  attribution and selective migration at the cost of a migration + writer change
  (Decision 8).
- **Cheap backfill vs completeness** — re-chunking from `full_text` is cheap for
  txt/md but impossible for mock-parsed formats, which need re-upload
  (Decision 8).

## Open Questions — Resolved

All seven were resolved by the deciders on 2026-07-21; rulings recorded verbatim.

1. **Soft fill threshold (Decision 4) — RESOLVED.** Break at a section boundary
   when the chunk is at 60% or more of chunk_size. Below that, pack across the
   boundary. Implement as a hardcoded module constant, not a Settings field — it
   is a tuning parameter, and exposing it invites fiddling instead of
   benchmarking. If the benchmark shows 60% is wrong, change the constant and
   re-run.

2. **Default flip (Decision 7) — RESOLVED.** Flip block_aware to default only
   when all four hold: (a) Q1's top chunk begins with leave content rather than
   remote-work content, (b) minimum margin above the similarity floor across
   Q1–Q5 is ≥0.03 (V1 was 0.009), (c) the spread between the highest Q1–Q5 score
   and Q6's best rejected score increases versus V1, (d) Q6 still returns zero
   results. This is not a new benchmark epoch. The corpus and queries are
   unchanged; only configuration differs. Append a V2 results block to the
   existing v1 spec. The spec version increments only if the corpus or the
   queries change — otherwise runs stop being comparable, which defeats the
   purpose of a regression benchmark.

3. **Column name and semantics (Decision 8) — RESOLVED.** Name it chunker, a
   string holding name and version together — "fixed-1", "block-aware-1" —
   mirroring how embedding_model holds "voyage-3.5" / "mock-embed-1". Record it;
   do not filter retrieval by it. The distinction from embedding_model is
   deliberate: mixing embedding models is incorrect, because different vector
   spaces make cosine distance meaningless (this is what poisoned the Phase 5d
   memory demo). Mixing chunkers is merely inconsistent — every row is a valid
   vector in the same space, just cut differently. Filtering by chunker would
   silently hide half the corpus to solve a problem that does not exist.

4. **Multi-section citations (Decision 5) — RESOLVED.** Keep section=None for
   spanning chunks. A range or list requires both a schema change and a render()
   change to solve a problem we have no user evidence for, and Decision 4's
   section-aware split points make spans rare by construction. Revisit when real
   PDF parsing makes sections common. The decision is reversible, so deferring is
   cheap.

5. **Overlap budget default (Decision 3) — RESOLVED.** Reuse the existing
   overlap=200 characters as the block-carry budget. Do not introduce a separate
   setting. Two knobs that must be tuned in tandem are worse than one.

6. **Backfill scope and cost (Decision 8) — RESOLVED.** No backfill. Development
   only. There are zero production tenants, and original-file storage does not
   exist yet — so for mock-parsed formats a backfill is impossible regardless.
   Defer until after original file storage lands. A mixed-algorithm corpus is
   acceptable in dev; it is forbidden in production by policy once production
   exists.

7. **PDF/DOCX gating (Assumption 5) — RESOLVED.** No, it does not gate the value.
   Paragraph packing improves .txt retrieval regardless of sections, and Markdown
   is a first-class format users will upload. Only the section-aware split points
   depend on structured parsers — that is one decision out of eleven, and the
   rest deliver value today.

## Recommendation

**Coexist behind configuration (Decision 7), do not replace `FixedSizeChunker`
yet, do not reject.**

Justification: the V1 findings — wrong-section lead-in (`chunker.py:77`), one
window serving two unrelated queries, and a 0.009 floor margin — are structural
consequences of ignoring block boundaries the parser already computes
(`text.py:5-8,25-31`), so the problem is real and `BlockAwareChunker` targets it
directly. But the benefit to _scores_ is a hypothesis the benchmark must confirm
(Decision 9), and an outright replacement would strand every already-indexed
document with no way to even tell which algorithm produced a row (Decision 8's
finding). Introducing it behind a `document_chunker` flag, adding the per-row
`chunker` provenance column, and gating the default flip on an unchanged
benchmark re-run (Q6 = 0 as a hard invariant) captures the upside while keeping
rollback trivial and the measurement honest.

---

## Amendment 1 — 2026-07-21: score-margin flip-gate falsified, replaced with citation-quality metrics

This amendment does NOT reverse the ADR. The core decisions stand: BlockAwareChunker
exists behind the `document_chunker` config flag (Decision 7), with per-row `chunker`
provenance (Decision 8). What changes is the acceptance gate for flipping the DEFAULT
to `block_aware` — the Open Question 2 resolution. Per the ADR README convention the
original gate is left intact above; this block records that it was mis-specified and
what replaced it.

### What happened

The V2 benchmark (block_aware, all else identical: floor 0.50, chunk_size 1000,
overlap 200, voyage-3.5) was run and accepted as honest. Against the original OQ2 gate:

- (a) Q1 top chunk begins with LEAVE content, not remote-work — PASS (repeatable).
- (b) min margin above floor across Q1–Q5 >= 0.03 — did not hold (v2 0.006 vs v1 0.009).
- (c) spread (highest Q1–Q5 − Q6 best-rejected) increases — did not hold
  (v2 0.1983 vs v1 0.2041).
- (d) Q6 returns zero results — PASS.

### Decider's reasoning (verbatim)

> "My criteria (b) and (c) were miscalibrated — I asked a chunking change to improve a
> scoring metric it does not target, and the observed differences (0.003 margin, 0.006
> spread) are smaller than this benchmark can resolve with one document and six queries.
> Treat them as inconclusive, not failed. Criterion (a) passed structurally and
> repeatably. So the decision now rests on a metric I should have specified originally."

Accordingly: criteria (b) and (c) are RECLASSIFIED from FAIL to INCONCLUSIVE (the
V1→V2 deltas — 0.003 in min margin, 0.006 in spread — are below this benchmark's
resolving power with one document and six queries, and score margin is a property of
the embedding model + floor, not the chunker). The score-margin hypothesis behind
(b)/(c) is treated as FALSIFIED as a chunker-acceptance test.

### Replacement gate — citation-quality metrics

The flip decision is re-based on what a chunker actually controls: WHERE the citation
falls. Measured DETERMINISTICALLY from the already-recorded V1/V2 char ranges and the
corpus on disk — no embeddings, no API calls, no re-run:

1. Citation tightness = cited chunk length ÷ minimal answering-span length (lower = tighter).
2. Answer position = where the answering sentence begins in the cited chunk
   (first sentence / first 20% / later).

Minimal answering spans (chosen and stated for review):

    Q1  "Annual leave entitlement is 26 days per calendar year"                        chars 3761-3814 (53)
    Q2  "Engineering staff receive a MacBook Pro 16-inch ... Dell Latitude 7450."      chars 7315-7454 (139)
    Q3  "Compassionate leave of up to five days at full pay ... following a bereavement." chars 5213-5301 (88)
    Q4  "Requests to work remotely from a country ... both People Operations and
         Finance ... thirty consecutive days ..."                                     chars 3204-3485 (281)
    Q5  "Every employee must maintain a current emergency contact record in the people system." chars 15366-15451 (85)

Results (V1 fixed -> V2 block_aware):

    Q   tightness V1 -> V2     answer position V1 -> V2
    Q1  18.9x -> 14.5x         56.1% (later)     -> 4.0%  (first sentence)
    Q2   7.2x ->  6.8x         11.5% (first 20%) -> 10.0% (first 20%)
    Q3  11.4x -> 12.6x         41.3% (later)     -> 0.0%  (first sentence)
    Q4   3.6x ->  2.8x          0.4% (first 20%) -> 30.0% (later)
    Q5  11.8x -> 10.3x         16.6% (first 20%) -> 6.1%  (first sentence)
    avg 10.6x ->  9.4x         first-sentence count 0 -> 3 ; "later" count 2 -> 1

Reading:

- Tightness improved on 4 of 5 (avg 10.6x -> 9.4x). The one looser case (Q3) is an
  overlap-carry artefact (1110-char chunk) but its answer moved 41% -> 0%, so the
  citation is far more useful despite marginal extra length.
- Position improved decisively: block_aware puts the answer in the FIRST SENTENCE for
  Q1/Q3/Q5 (fixed: none) and eliminates BOTH of fixed's buried citations (Q1 56%,
  Q3 41%). The lone regression, Q4 (0.4% -> 30%), is smaller than the two fixes and
  is a case where fixed's early position was itself a mid-word-cut artefact (its chunk
  opened "nt. Requests to work remotely..."), whereas block_aware opens at a clean
  paragraph boundary.

### Amended decision

FLIP the default to `document_chunker="block_aware"` on citation grounds. Decision 7's
"default stays fixed until block_aware passes the benchmark" is satisfied under the
replacement gate. Criterion (a) and (d) still hold; (b)/(c) are inconclusive, not
disqualifying.

Follow-up implementation (separate, gated on approval; not done in this amendment):
change the Settings default `fixed -> block_aware`, update the chunker-selection tests
and conftest ingest expectations, run the full suite green, and record a block_aware
"benchmark of record" (this is a config change, NOT a corpus/query change — it appends
a run block to the v1 spec; the spec version does not increment, per Open Question 2).
