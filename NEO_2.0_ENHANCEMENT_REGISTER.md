# Neo 2.0 Enhancement Register

An architectural review of Phases 1–8 against the actual codebase. Every claim
about current behaviour cites `path:line`; where a deferral is an _absence_ (a
missing endpoint or unhandled case), that is stated plainly instead of a line
cite. This document is analysis only — it proposes no implementations and changes
no roadmap phase.

**Release-blocker rule applied throughout.** Any gap that would stop Neo 1.0 from
delivering an _advertised_ capability is NOT filed as a 2.0 enhancement; it is
raised in **Required Before Neo 1.0 Release** with a reason. Per instruction I
err toward flagging.

## Corrections to the supplied deferral list (verified resolved in code)

Three supplied items were **closed in Phase 6k** and are not carried into the
register except as noted:

1. **"Non-streaming `/chat` holds the pooled tenant DB connection across
   `provider.complete()`."** — Resolved. `/chat` now uses a scoped session and
   short bookending transactions (Txn A commits the user message _before_ the
   call; Txn B persists the assistant message _after_), and the provider call is
   explicitly annotated `# Provider call holding NO DB connection`
   (`apps/api/app/presentation/http/routers/chat.py:421`, structure at `:310-323,
:428-438`, dep `StreamingCurrentUserDep` at `:287`).
2. **"Provider-failure persistence differs between `/chat` (rolls back
   everything) and `/chat/stream` (keeps the user message)."** — Resolved /
   aligned. Both commit the user message before the provider call, so a provider
   failure leaves it persisted on both paths
   (`chat.py:313-315`).
3. **"Memory extraction runs inline in the chat turn, adding latency."** —
   Resolved as stated: extraction is now scheduled off the response path via
   FastAPI `BackgroundTasks` (`chat.py:440-449`). A _residual_ remains — those
   tasks run in-process, not on durable/queued infrastructure — which is carried
   forward as a Phase 5 theme item below, not as the original latency bug.

---

## Phase 1 — Foundation

### 1.1 Prod web image bakes `NEXT_PUBLIC_API_URL` at build time

- **Description.** The production Next.js image is built with `pnpm --filter web
build` (`apps/web/Dockerfile:20`), and the API base URL is read from
  `process.env.NEXT_PUBLIC_API_URL` (`apps/web/src/lib/env.ts:2`). Next inlines
  `NEXT_PUBLIC_*` at build time, so one image cannot be promoted across
  environments with different API hosts — the URL is frozen into the bundle.
- **Why deferred.** Dev/compose passes the value at runtime
  (`docker-compose.yml:51`), so the gap only bites a build-once/deploy-many
  pipeline that does not exist yet.
- **Business value.** Medium — one artifact promoted dev→staging→prod is standard
  release hygiene; rebuilding per environment invites drift.
- **Technical value.** Medium — enables immutable-image promotion.
- **Complexity.** Medium (runtime public-config injection pattern).
- **Priority.** Medium.
- **ADR required.** No.

### 1.2 Docker anon-volume venv/`node_modules` footgun

- **Description.** The dev overlay mounts anonymous volumes over `/app/.venv`
  and the `node_modules` trees (`docker-compose.override.yml:8,17-19`). A stale
  anon venv survives image rebuilds, so a newly-added dependency is missing at
  runtime until `--renew-anon-volumes`; the documented workaround is
  `make api-rebuild`. This is a papered-over sharp edge, not a fix.
- **Why deferred.** A known workaround exists and the failure is dev-only.
- **Business value.** Low (developer productivity, onboarding friction).
- **Technical value.** Medium — removes a recurring "works on my machine" trap.
- **Complexity.** Low–Medium (volume strategy rework).
- **Priority.** Low.
- **ADR required.** No.

### 1.3 Observability beyond structured logging

- **Description.** Phase 1 ships structured logging and health/readiness checks,
  but there are no metrics, distributed tracing, or an error-tracking pipeline.
  (See the cross-phase Observability theme.)
- **Why deferred.** Sequenced to Phase 11 (Enterprise Readiness),
  `docs/roadmap.md:212-215`.
- **Business value.** High for operating a real tenant fleet.
- **Technical value.** High — turns incident diagnosis from log-grep to signal.
- **Complexity.** Medium.
- **Priority.** Medium (High once real tenants land).
- **ADR required.** Yes (metrics/trace stack + cardinality/PII policy).

---

## Phase 2 — Identity Platform

### 2.1 `/orgs/switch` endpoint + refresh preserves the active org

- **Description.** `refresh` does not preserve the previously-active tenant; it
  re-selects `active[0].organization_id` — the _first_ active membership
  (`apps/api/app/application/use_cases/auth.py:181-184`, whose own comment says
  "`/orgs/switch` will replace this later"). There is **no org-switch endpoint**
  (`apps/api/app/presentation/http/routers/auth.py` exposes only
  register/login/refresh/logout, `:52,:78,:96,:114`). A user in multiple orgs
  cannot deterministically choose or keep an org across a token refresh.
- **Why deferred.** Single-org users are unaffected; multi-org UX was postponed.
- **Business value.** High for any customer with users spanning multiple orgs.
- **Technical value.** Medium — completes the multi-tenant membership model.
- **Complexity.** Medium.
- **Priority.** High. _(Also raised as a candidate release-blocker — see below.)_
- **ADR required.** No.

### 2.2 Refresh token in `localStorage`, not an httpOnly cookie

- **Description.** The web app stores the refresh token in `localStorage`
  (`apps/web/src/store/session.ts:24-40`), so any XSS can exfiltrate a long-lived
  credential. The code itself flags the intent to "move to httpOnly cookie when
  we have a session/CSRF story" (`session.ts:24`).
- **Why deferred.** httpOnly cookies require a CSRF-defense design the app does
  not yet have.
- **Business value.** High — reduces blast radius of a front-end XSS to the
  short-lived access token.
- **Technical value.** Medium — needs a cookie/CSRF model server-side.
- **Complexity.** Medium.
- **Priority.** High.
- **ADR required.** Yes (cookie/CSRF/session model).

### 2.3 API-key issuance & management endpoints

- **Description.** An `api_keys` table exists
  (`apps/api/app/infrastructure/db/models/tenancy.py`), but there are **no
  endpoints** to issue, list, rotate, or revoke keys (no route matches
  `api_key` under `routers/`). Programmatic/machine access to Neo is therefore
  not self-serve.
- **Why deferred.** Admin tooling was consolidated toward Phase 11.
- **Business value.** Medium–High — API keys are how integrations and CI call
  Neo without interactive login.
- **Technical value.** Medium.
- **Complexity.** Medium (hashing, scopes, rotation, last-used).
- **Priority.** Medium.
- **ADR required.** No (schema exists; endpoints + scope model only).

### 2.4 Email verification & password reset

- **Description.** Neither flow exists (no route matches `verify`/`reset` under
  `routers/`; `auth.py` has only register/login/refresh/logout). A user who
  forgets their password is permanently locked out; email ownership is never
  proven.
- **Why deferred.** Requires transactional email infrastructure not yet present.
- **Business value.** High — self-serve recovery is table stakes for real users.
- **Technical value.** Medium (needs email transport + signed tokens).
- **Complexity.** Medium.
- **Priority.** High. _(Password reset raised as a candidate release-blocker.)_
- **ADR required.** No.

---

## Phase 3 — AI Platform

### 3.1 Provider routing / fallback / retry policy

- **Description.** Provider selection is config-driven and fail-fast, with real
  Anthropic + mock implementations. There is no cross-provider fallback,
  circuit-breaking, or standardized retry/backoff on transient upstream errors —
  a provider outage surfaces directly to the caller.
- **Why deferred.** A single configured provider is sufficient for 1.0; the port
  seam already isolates the concern.
- **Business value.** Medium — availability during upstream incidents.
- **Technical value.** Medium — reuses the existing `ChatProvider` port.
- **Complexity.** Medium.
- **Priority.** Low–Medium.
- **ADR required.** Yes (routing/failover policy, cost/latency trade-offs).

---

## Phase 4 — Chat Persistence

The two supplied Phase 4 items (connection-holding on `/chat`; divergent
provider-failure persistence) are **resolved** — see _Corrections_ above. No new
Phase 4 enhancement is filed beyond streaming resumability, noted as low
priority:

### 4.1 Stream resumability / reconnect

- **Description.** SSE streaming has no resume-after-disconnect; a dropped
  connection loses the in-flight assistant turn (the turn still persists via Txn
  B on completion, but a mid-stream drop cannot be re-attached).
- **Why deferred.** Acceptable for 1.0; adds protocol complexity.
- **Business value.** Low–Medium (flaky-network UX).
- **Technical value.** Medium.
- **Complexity.** High (event IDs, replay buffer).
- **Priority.** Low.
- **ADR required.** Yes.

---

## Phase 5 — Memory Platform

### 5.1 Durable / queued background-job infrastructure

- **Description.** Post-6k, memory extraction runs off the response path via
  FastAPI `BackgroundTasks` (`chat.py:440-449`) — but those run **in-process**
  and are lost on crash/restart, with no retry, dead-letter, or backpressure.
  This is the residual after the original inline-latency bug was fixed.
- **Why deferred.** In-process tasks were the minimal way to get extraction off
  the turn; durable infra is a larger investment.
- **Business value.** Medium — reliability of the "Neo remembers" promise.
- **Technical value.** High — a queue also unblocks future async work (indexing,
  notifications).
- **Complexity.** High (broker/worker + delivery semantics).
- **Priority.** Medium.
- **ADR required.** Yes (queue technology + at-least-once semantics).

### 5.2 Prove the LLM memory extractor (default is mock)

- **Description.** `memory_extractor` defaults to `"mock"`
  (`apps/api/app/infrastructure/config/settings.py:80`). A real
  `LLMMemoryExtractor` exists
  (`apps/api/app/ai/extractors/llm/extractor.py:24`, wired at
  `app/ai/extractors/__init__.py:22-24`) but is unproven at scale — extraction
  quality, cost, and dedup behaviour on real conversations are unmeasured.
- **Why deferred.** Mock keeps CI deterministic; the real extractor needs an
  evaluation harness like the retrieval benchmark.
- **Business value.** High — mock memory learns nothing real.
- **Technical value.** Medium (evaluation + prompt tuning).
- **Complexity.** Medium.
- **Priority.** Medium–High.
- **ADR required.** No (an eval-and-enable exercise, not new architecture).

---

## Phase 6 — AI Orchestration & Multi-Agent Platform

### 6.1 LLM-generated / editable conversation titles

- **Description.** Titles are the first user message truncated to 60 chars
  (`chat.py:89-93`, applied at `:558`). For a user who asks many short questions
  in one thread, every title collapses toward the same unhelpful prefix, and
  there is no rename. There is no LLM-summarized title.
- **Why deferred.** First-message titles were the cheap default; summarization
  adds an LLM call.
- **Business value.** Medium — conversation list usability.
- **Technical value.** Low–Medium.
- **Complexity.** Low–Medium.
- **Priority.** Medium.
- **ADR required.** No.

---

## Phase 7 — Workflow Platform

All three are **already documented residuals** in the roadmap
(`docs/roadmap.md:102-127`); restated here with 2.0 framing.

### 7.1 IP-pinning transport (close the DNS-rebinding window)

- **Description.** The SSRF guard validates resolved IPs, but httpx re-resolves
  on connect, leaving a DNS-rebinding window for tenant-supplied URLs
  (`docs/roadmap.md:115-123`). Mitigated today by `follow_redirects=False`, the
  host allowlist, and fail-closed-on-empty-allowlist.
- **Why deferred.** Pinning while preserving TLS SNI + cert verification needs a
  custom httpx transport; a subtly wrong one silently disables cert verification
  — a worse failure than the narrow window (`roadmap.md:117-123`).
- **Business value.** Medium (defense-in-depth for tenant workflow URLs).
- **Technical value.** Medium.
- **Complexity.** High (custom transport, correct TLS).
- **Priority.** Medium.
- **ADR required.** Yes (transport design + TLS verification proof).

### 7.2 Per-tenant workflow credentials (encryption at rest + KMS)

- **Description.** Tenant workflow rows carry no secrets; outbound calls use the
  deployment's single configured token (`docs/roadmap.md:124-127`). Tenants
  cannot supply their own credentials.
- **Why deferred.** Requires encryption-at-rest + key management, deliberately
  kept out of Phase 7.
- **Business value.** High for multi-tenant workflow isolation.
- **Technical value.** High (also unblocks other per-tenant secrets).
- **Complexity.** High.
- **Priority.** Medium (High if tenants author real workflows in 1.0).
- **ADR required.** Yes (secret storage, KMS, rotation).

### 7.3 Workflow write / CRUD management API

- **Description.** Tenant `workflows` rows must be inserted directly into the DB;
  there is no management surface (`docs/roadmap.md:106-108`).
- **Why deferred.** Explicitly consolidated into Phase 11 admin tooling.
- **Business value.** Medium–High (self-serve workflow management).
- **Technical value.** Medium.
- **Complexity.** Medium.
- **Priority.** Medium.
- **ADR required.** No.

---

## Phase 8 — Document Intelligence Platform

_(Two items here — real PDF/DOCX parsing and original-file storage — are release
blockers and are detailed in the closing section; summarized here for phase
completeness.)_

### 8.1 Real PDF/DOCX parsing — **release blocker** (see below)

- Only `text/plain` and `text/markdown` parse for real; other declared types are
  now rejected with 415 rather than mock-fabricated
  (`apps/api/app/ai/documents/dispatch.py`, `settings.document_parser` default
  `"reject"`). Detailed under _Required Before Neo 1.0 Release_.

### 8.2 Original-file storage — **release blocker** (see below)

- Only extracted `full_text` is persisted, never the uploaded bytes; the code
  labels this a GO-LIVE GATE
  (`apps/api/app/presentation/http/routers/documents.py:57-64`). Detailed below.

### 8.3 Surface citations under chat answers (8e-3) — **candidate release blocker**

- **Description.** The `search_documents` tool returns citations to the _model_
  (8d), and the standalone `/documents/search` UI shows them (8e-1/8e-2), but the
  **chat response carries no structured citation surface** — `ChatResponse`
  exposes `tool_invocations` (name+ok only) and no citations
  (`apps/api/app/presentation/http/schemas/chat.py:43`;
  `app/application/ports/chat.py:46`). When Neo answers from documents in chat,
  the user sees prose that may mention a source but no linked, structured
  citation panel. Detailed below.
- **Priority.** High.
- **ADR required.** No (surface + schema addition, not new architecture).

### 8.4 Token-based chunker

- **Description.** `chunk_size`/`overlap` are in **characters**, using a
  ~4-chars/token proxy against the model's token cap
  (`apps/api/app/ai/documents/chunker.py:10-12`). Character sizing mis-estimates
  on code/CJK and cannot target the embedding model's true token budget.
- **Why deferred.** The docstring calls a token-aware chunker "the refinement,
  not this slice."
- **Business value.** Medium (retrieval quality on non-English/code corpora).
- **Technical value.** Medium — a tokenizer dependency behind the `Chunker` port.
- **Complexity.** Medium.
- **Priority.** Medium.
- **ADR required.** No (additive `Chunker` implementation, ADR 0001 precedent).

### 8.5 Reranking for thin retrieval score margins

- **Description.** There is **no reranker** (no `rerank`/`Reranker` anywhere in
  `apps/api/app`); search returns floor-filtered top-k by raw cosine
  (`routers/documents.py` search handler). The V1/V2 benchmark showed scores
  compressed into a narrow band just above the 0.50 floor (min margin ~0.006–
  0.009, per `apps/api/tests/fixtures/retrieval-benchmark/…`), which a
  cross-encoder rerank stage is designed to separate.
- **Why deferred.** Retrieval is functionally correct (6/6 on the benchmark);
  reranking is a quality lift, not a fix.
- **Business value.** Medium–High (answer precision, fewer near-miss citations).
- **Technical value.** High (a rerank seam benefits memory retrieval too).
- **Complexity.** Medium–High (model choice, latency budget).
- **Priority.** Medium.
- **ADR required.** Yes (rerank model, latency/cost, where it sits in the seam).

### 8.6 De-duplicate overlapping text across adjacent search results

- **Description.** `BlockAwareChunker` carries whole trailing blocks as overlap
  (ADR 0001, Decision 3), so adjacent chunks legitimately share text. When two
  adjacent chunks both clear the floor, the search panel renders visibly
  duplicated passages; there is no merge/dedup step in the search handler
  (`routers/documents.py`).
- **Why deferred.** Overlap is deliberate for retrieval recall; presentation
  dedup is polish.
- **Business value.** Low–Medium (result readability).
- **Technical value.** Low–Medium.
- **Complexity.** Low–Medium (span-merge on adjacent same-document hits).
- **Priority.** Low.
- **ADR required.** No.

---

## Required Before Neo 1.0 Release

Items that would stop Neo 1.0 from delivering an advertised capability. **R1 and
R2** are the known blockers; **R6** was surfaced during review and confirmed by
the PM. The three previously-flagged candidates (R3–R5) have since been **ruled
by the PM to Neo 2.0** — recorded under _Ruled to Neo 2.0_ below with rationale
and binding conditions so the decisions don't reopen. This section is
authoritative for blocker status; the earlier "candidate release-blocker"
annotations in the phase entries (8.3, 2.4, 2.1) are superseded by these rulings.

### R1. Real PDF/DOCX parsing (known blocker)

Phase 8's advertised purpose is to "understand, process, search, and reason over
enterprise documents … ingestion and parsing **across formats**"
(`docs/roadmap.md:156-168`). Today only `text/plain`/`text/markdown` parse for
real; every other declared type is rejected with 415
(`apps/api/app/ai/documents/dispatch.py`, `document_parser` default `"reject"`).
Enterprise documents are overwhelmingly PDF and Word, so a user uploading the
most common formats is turned away. **Blocks** the headline document-intelligence
capability.

### R2. Original-file storage (known blocker)

Only extracted `full_text` is stored, never the uploaded bytes; the upload route
documents this as a GO-LIVE GATE because, without originals, re-indexing after a
parser upgrade requires users to re-upload and a "view/download source" is
impossible (`apps/api/app/presentation/http/routers/documents.py:57-64`).
**Blocks** trustworthy long-lived corpora and source-of-truth retrieval; a corpus
ingested pre-storage is permanently pinned to whatever first parsed it.

### R6. Close / gate open registration for the pilot _(new — PM-confirmed blocker)_

Neo 1.0 launches as a controlled, admin-provisioned pilot, but `POST /register`
is **open** (`apps/api/app/presentation/http/routers/auth.py:52`): arbitrary
users can self-provision accounts _and_ organizations. For an invite-only pilot
that is both a **scope mismatch** (unintended tenants) and a **security
mismatch** (unauthenticated account/org creation). Critically, it also
re-introduces the **permanent-lockout problem** — a self-registered user has no
administrator relationship and, with no password-reset flow (R4), is
unrecoverable — the very problem whose absence makes R4 safe to defer.
**Requirement:** registration must be **closed or gated** for the pilot —
invite-only, admin-created accounts, or the endpoint feature-flagged off.
**R4's deferral is contingent on this landing.**

### Ruled to Neo 2.0 (decision trail — recorded so the debate doesn't reopen)

The three items flagged during review were ruled by the PM to Neo 2.0. Their
per-phase enhancement entries stand; the blocker candidacy is withdrawn.

- **R3 — Citations under chat answers (8e-3) → 2.0 enhancement.** _PM rationale:_
  the advertised citation-first capability is delivered on the **Documents search
  surface**, where every result carries a verifiable citation (8e-1/8e-2). Chat
  citations are an enhancement, not a release requirement. Filed as Phase 8 item
  **8.3** (`ChatResponse` has no citation field, `schemas/chat.py:43`).

- **R4 — Password reset → 2.0 (conditional).** _PM rationale:_ 1.0 launches as a
  controlled, admin-provisioned pilot, so a locked-out user is recoverable by an
  administrator. **Explicit condition:** this deferral holds _only_ while accounts
  are admin-provisioned and self-registration is closed — i.e. it is **contingent
  on R6 landing**. If open registration is ever re-enabled, password reset
  returns to blocker status. Filed as Phase 2 item **2.4** (no `reset` route;
  `auth.py:52-114`).

- **R5 — `/orgs/switch` + refresh org preservation → 2.0 (binding condition).**
  _PM rationale:_ the refresh-rebind defect (`auth.py:181-184`) is **unreachable
  until a user can belong to more than one org**. **Binding dependency:** the fix
  must ship in the **same slice as org invitations / multi-org membership** — it
  must not land before, and multi-org membership must not land without it. Filed
  as Phase 2 item **2.1**.

---

## Top 10 by Priority (across all phases)

| #   | Item                                        | Phase | Priority   | Notes                                         |
| --- | ------------------------------------------- | ----- | ---------- | --------------------------------------------- |
| 1   | Real PDF/DOCX parsing (R1)                  | 8     | Blocker    | Advertised "across formats"                   |
| 2   | Original-file storage (R2)                  | 8     | Blocker    | Self-labelled go-live gate                    |
| 3   | Close/gate open registration for pilot (R6) | 2     | Blocker    | Admin-provisioned pilot; guards R4's deferral |
| 4   | Refresh token → httpOnly cookie             | 2     | High       | XSS blast-radius                              |
| 5   | Citations under chat answers, 8e-3          | 8     | High (2.0) | Ruled out of 1.0 — search surface cites       |
| 6   | Password reset                              | 2     | High (2.0) | Deferral contingent on R6                     |
| 7   | `/orgs/switch` + refresh rebind             | 2     | High (2.0) | Must ship with multi-org membership           |
| 8   | Prove/enable LLM memory extractor           | 5     | Med–High   | Mock learns nothing                           |
| 9   | Per-tenant workflow credentials             | 7     | Medium     | Multi-tenant isolation                        |
| 10  | Reranking for thin score margins            | 8     | Medium     | Retrieval precision                           |

_(R1, R2, R6 are the confirmed 1.0 blockers. Items 5–7 are the former flagged
candidates now ruled to Neo 2.0 — see Required-Before-1.0; they rank high within
2.0. Durable/queued background-job infra (item 5.1, Medium) falls just outside
this table.)_

---

## Themes — recurring gaps spanning phases

- **Admin / management surfaces.** Multiple capabilities exist as tables/logic
  with no management API: API keys (2.3), workflow CRUD (7.3), org switching
  (2.1). These converge on the Phase 11 admin console.
- **Secrets & credential management.** Per-tenant workflow credentials (7.2) and
  any future per-tenant integration secrets need one encryption-at-rest + KMS
  story rather than N bespoke ones.
- **Durable background-job infrastructure.** Memory extraction (5.1) is the first
  async workload; document re-indexing, notifications, and email (2.4) will all
  want the same queue/worker substrate.
- **Observability.** Structured logging exists, but metrics, tracing, and
  audit-querying (1.3) are absent — felt across every phase once real tenants
  operate.
- **Front-end security posture.** localStorage refresh token (2.2) and
  build-time-baked config (1.1) are both "fine for dev, wrong for a hardened
  prod web tier."
- **Retrieval quality.** Token-aware chunking (8.4), reranking (8.5), and result
  dedup (8.6) are one theme: raw cosine over character chunks is correct but
  coarse.

---

## Items Explicitly Rejected

Evaluated and intentionally **not** recommended for Neo 2.0, so the same debates
don't reopen.

- **Blockchain / on-chain audit ledger.** A Postgres audit table with RLS meets
  the tamper-evidence need; a chain adds ops burden and zero enterprise value.
- **AI avatars / video personas.** Cosmetic; orthogonal to knowledge, workflows,
  and communication — the actual roadmap.
- **Voice cloning.** Legal/consent risk vastly outweighs any assistant benefit;
  Phase 10 phone calls do not require it.
- **AutoGPT-style open-ended autonomy.** Directly contradicts the deliberate
  agent-permission model (7d): consent is _explicit agent selection_, not an
  agent free to act unsupervised.
- **Building our own vector database.** `pgvector` + HNSW already backs memory and
  document search under the same RLS; a separate vector store adds a second
  consistency/tenancy boundary for no gain.
- **Per-tenant model fine-tuning.** Retrieval-augmented generation with good
  chunking/reranking covers the grounding need at a fraction of the cost and
  operational complexity of per-tenant training pipelines.
- **Replacing Postgres RLS with app-layer tenant checks.** RLS (ENABLE + FORCE +
  `NOBYPASSRLS` runtime role) is the platform's strongest isolation guarantee;
  moving tenancy into app code trades a database-enforced invariant for one that
  every new query can silently forget.
- **GraphQL / microservices re-platforming.** A REST modular monolith on Clean
  Architecture is serving fine; a rewrite spends the 2.0 budget on plumbing, not
  capability.
- **Client-side embedding or raw-embedding exposure.** Embeddings never need to
  leave the server; the whitelist discipline (MemoryOut / DocumentSearchResult
  omit vectors) is a deliberate boundary, not an oversight to "open up."
- **Real-time collaborative (multi-cursor) document editing.** Neo reasons over
  documents; it is not a document editor, and CRDT infrastructure is a product in
  its own right.
- **Agent/plugin marketplace.** Premature ecosystem-building before the core
  single-tenant capabilities (documents, integration, communication) are proven.

---

_End of register. No implementation, schema, config, or roadmap changes were made
in producing this document._
