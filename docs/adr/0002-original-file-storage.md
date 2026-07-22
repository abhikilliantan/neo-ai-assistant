# 0002. Original File Storage

Status: Accepted
Date: 2026-07-22
Deciders: platform / document-intelligence owners
Supersedes: none

> Design-only ADR. No implementation, schema change, migration, or other file is
> included. Every statement about current behaviour cites `path:line` (paths
> relative to repo root). Decisions still open are left as Open Questions rather
> than resolved silently.

## Context

Neo persists only a document's extracted `full_text`, never the uploaded bytes.
The upload route documents this as a **go-live gate** in-line
(`apps/api/app/presentation/http/routers/documents.py:57-64`): once a better
parser ships (real PDF/DOCX — Neo 1.0 blocker 2/3), its improvements apply only
to NEW uploads, because re-indexing an existing corpus would require users to
re-upload — the originals are gone.

Current lifecycle of an uploaded file:

- Entry: `POST /api/v1/documents` → `upload_document`
  (`documents.py:48-99`).
- Streaming size-guarded read: `read_upload(...)` (`multipart.py:71-112`) returns
  `UploadedFile(filename, content_type, data: bytes)` (`multipart.py:36-40`); the
  whole file is in memory as `upload.data` (`multipart.py:103,108-112`), bounded
  by `document_max_bytes` (`settings.py:149`, 10 MB).
- **415 gate:** the declared content type is normalized and checked against the
  allowlist; unsupported types are rejected **before any parsing**
  (`documents.py:73-75`). This gate was deliberately made strict in the
  reject-unsupported-types slice (`app/ai/documents/dispatch.py`,
  `document_parser` default `"reject"`).
- Ingest: `asyncio.wait_for(ingest.ingest(session, ..., data=upload.data), ...)`
  (`documents.py:82-92`).
- **Discard point:** in `DocumentIngestService.ingest` (`ingest.py:86-124`) the
  bytes are used **only** by `parse(data=...)` (`:99`) and `len(data)` for
  `byte_size` (`:107`), then go out of scope. Only `parsed.full_text` is
  persisted (`repo.create(..., full_text=parsed.full_text)`, `:102-109`). A
  decode failure during parse surfaces as **422** (`DocumentDecodeError` →
  `DocumentParseError`, mapped in `app/core/exceptions.py`).
- Transaction: one tenant-scoped session (`TenantSessionDep`,
  `deps.py:224-240`) that `session.begin()`s and commits at dependency teardown;
  any exception rolls back the whole thing — the **all-or-nothing "no partial
  document"** guarantee (`ingest.py:96-97`).
- Delete: `soft_delete` tombstones the row (`repositories.py:481-486`); nothing
  to clean because nothing was stored.

Tenant isolation today is Postgres RLS on the `documents` and `document_chunks`
rows (`organization_id` + `app.current_tenant` GUC). **RLS does not reach files
that live outside the database** — that is the central new problem this ADR must
solve, alongside choosing a backend and a write-consistency model.

This ADR decides how Neo retains original uploaded bytes for the next 5+ years.

## Decision

**Store original bytes in object storage exposed through an S3-compatible API,
behind a `StorageProvider` port. The Postgres `documents` row holds only an
opaque pointer (`storage_key`).** The `StorageProvider` seam lets the concrete
backend follow the deployment — local filesystem in dev/CI/single-node, MinIO
on-prem, AWS S3 / Azure Blob / GCS in cloud — without any business-logic change,
exactly like the `ChatProvider` / `EmbeddingProvider` / `Chunker` seams.

Five decisions of record:

1. **The `StorageProvider` seam.** A framework-free `Protocol` in
   `app/application/ports/`, a _dumb opaque-key blob store_ that knows nothing
   about tenants (tenancy is enforced one layer up — Decision 4). Design shape
   (not implementation):

   ```
   class StorageProvider(Protocol):
       async def put(self, *, key: str, data: bytes, content_type: str) -> None: ...
       async def get(self, *, key: str) -> bytes: ...
       async def delete(self, *, key: str) -> None: ...   # idempotent
       async def exists(self, *, key: str) -> bool: ...
   ```

   Selected by `build_storage_provider(settings)`, fail-fast on unknown, mirroring
   `build_document_parser`. Streaming `get`/`put` and a richer `put` return type
   are deferred until the size cap rises above the current 10 MB.

2. **Filesystem-first, object-storage-later.** The first backend is
   `LocalFilesystemStorage` (keys → paths under a configured root on a mounted
   Docker volume). Object-storage backends are added **later, behind the same
   interface**, each proven by its own slice. The filesystem backend is not
   throwaway — it stays permanently as the dev/CI/single-node-on-prem
   implementation.

3. **Schema additions** to `documents` (additive, nullable) — **three columns
   (Open Question 1 resolved)**: `storage_key` (opaque pointer), `storage_backend`
   (which backend wrote it — per-row provenance, mirroring `embedding_model` at
   `models/documents.py:99` and `chunker` from ADR 0001), and `content_sha256`
   (integrity anchor for reprocessing + future dedup — included in slice 1, not
   deferred). No RLS change — `documents` is already RLS-locked.

4. **Tenant isolation outside RLS** via the pointer table as the sole gate to the
   bytes (see _Tenant isolation_ below).

5. **Dual-write ordering** = validate-then-store-then-ingest-then-commit, with an
   immediate compensating delete plus a reconciliation sweep (see _Write ordering_
   below).

## Alternatives rejected

- **Postgres `bytea` (bytes in the DB).** Its one real advantage is decisive-
  sounding: bytes and pointer share one transaction (the dual-write problem
  vanishes) and RLS reaches the bytes for free. Rejected because over 5 years it
  is disqualifying: every upload is WAL-logged and replicated (10 MB files
  amplify WAL/replication), TOAST + vacuum pressure grows, `pg_dump`/PITR backups
  balloon to include the blob corpus, and large reads hold a pooled connection —
  taxing the pgvector OLTP workload Neo depends on. It turns the primary
  transactional database into a blob store.
- **Filesystem forever (as the sole backend).** Simplest and fastest, zero new
  dependency, but not durable across host/volume loss without external
  replication and not multi-replica safe — two API replicas need a shared network
  filesystem (NFS/EFS), reintroducing the operational complexity object storage
  already solves. Kept as _a_ backend, rejected as _the_ backend.
- **Object storage from day one (S3/MinIO in slice 1).** Correct destination,
  wrong first step: it forces a client dependency, credentials, and a new dev
  container before the seam and the retain-on-upload path are even proven, and it
  contradicts single-backend slice discipline. Object storage is added behind the
  proven interface, not ahead of it.
- **Size-threshold hybrid** (small files in DB, large in object store). Two write
  paths, two failure modes, two read paths, a threshold to tune, for negligible
  benefit — object stores handle small objects fine. Rejected: complexity without
  payoff. (The recommended "pointer in Postgres + bytes in object storage" split
  is not this hybrid.)

## Tenant isolation outside the database

RLS protects `documents` _rows_, not bytes on a volume or in a bucket. The
pointer table is made the **only** gate to the bytes:

1. **Keys are org-scoped and server-minted.** `org/{organization_id}/{storage_id}`
   where `storage_id` is a server-generated `uuid4`. Clients never supply or see a
   storage key — they reference a `document_id` (UUID) only. This removes
   IDOR/path-traversal at the storage layer by construction.
2. **Every read re-verifies the tenant through RLS.** The key lives only on the
   `documents` row, so a read must: (a) `SELECT` the `Document` by id under the
   tenant session — RLS filters cross-tenant rows to nothing, so tenant B asking
   for A's `document_id` gets `None` → **404, no existence oracle** (identical to
   the delete path, `documents.py`); (b) belt-and-suspenders assert
   `document.organization_id == tenant_id`; (c) only then `storage.get(key)`.
3. **Isolation proof.** Tenant B can never obtain A's `storage_key` because step
   (a) never returns A's row to B. No key ⇒ no read. The org-prefixed path adds
   defense-in-depth (per-tenant IAM prefix policies and per-tenant retention/
   deletion later) and keeps any leak scoped and auditable; the filesystem backend
   confines all keys under a fixed root and, because both path components are
   server-generated UUIDs, cannot be traversed out of it. **RLS on the pointer
   table transitively protects the bytes.**

## Write ordering (dual-write) — argued, accounting for rejection paths

Two systems (store + Postgres) cannot share a transaction. The correct choice is
_ordering_, argued by the residue of each partial failure — and it must account
for the two upload-rejection paths already in the code:

- **415 unsupported content type** — knowable BEFORE reading the bytes
  (`documents.py:73-75`); made strict deliberately, so every rejected upload of a
  wrong type would orphan a file if bytes were written first. This is a
  _guaranteed_ orphan source, not an edge case.
- **422 decode failure** — knowable ONLY during parsing (`DocumentDecodeError` in
  the text parser), i.e. necessarily _after_ the bytes exist to parse.

**Ordering (precise):**

1. **Cheap validations that need no bytes run FIRST, before any storage write** —
   in particular the **415 content-type gate** (`documents.py:73-75`). A rejected
   type never touches storage, so it never orphans.
2. **Then store the bytes** (`storage.put(key, data)`), key minted per Decision 4.
3. **Then parse / chunk / embed** inside the existing all-or-nothing ingest
   transaction. A **422 decode failure** or **any ingest error** (embed failure,
   timeout, DB error) triggers the **compensating delete** of the just-written
   key.
4. **Then commit the row** carrying `storage_key`.

**Argument.** The two failure residues are asymmetric:

- **Store-first-after-415, DB/parse fails → orphaned bytes:** an object with no
  row. Invisible (RLS surfaces only rows; nothing references it), harmless to
  correctness, reclaimable. The user correctly sees the upload fail.
- **DB-first, store fails → dangling pointer:** a committed `Document` row _and
  its chunks_ claiming a `storage_key` with no bytes. Visible and searchable, yet
  "view original" 404/500s — it breaks the "no partial document" invariant.

An orphan costs _storage_; a dangling pointer costs _correctness_. Fail toward
invisible waste, never visible breakage → the row commits last. Moving the 415
gate ahead of the store removes the only _guaranteed_ orphan source; the
remaining orphan sources (422 and ingest errors) **cannot be moved earlier** —
they are only knowable once the bytes exist to parse — which is exactly why the
compensating delete and reconciliation sweep exist.

**Reconciliation with the all-or-nothing guarantee.** The DB side is unchanged —
ingest remains one transaction that rolls back fully on any failure
(`ingest.py:96-97`). Layering validate-then-store means the only new residue is
orphaned bytes; the guarantee strengthens to: **no partial document, no dangling
pointer; worst case is invisible orphaned bytes.** The key must exist before the
row, so `storage_id = uuid4()` is minted in the app and stored in the dedicated
`storage_key` column, independent of `document_id` generation timing.

**Cleanup — two layers:**

1. **Immediate compensating delete** (slice 1): the ingest `except` block deletes
   the just-written key. Covers the common post-store failures (422, embed error,
   timeout) synchronously.
2. **Reconciliation sweep** (later slice): a periodic set-difference of stored
   keys minus keys referenced by live `documents` rows, deleting only objects
   older than a grace window (≥ the ingest timeout, so it cannot race an in-flight
   upload). This is the _authoritative_ cleanup for the process-crash gap between
   `put` and `except`. It depends on durable background-job infrastructure the
   codebase lacks (only in-process `BackgroundTasks`, `chat.py`), so it ships
   first as a management command.

**Delete path:** soft-delete continues to tombstone the row and **retain** the
bytes (no delete-side dual-write); a later retention job hard-deletes bytes for
documents soft-deleted beyond the retention window.

## Consequences

- **Positive.** Originals are retained from slice 1 forward, closing the go-live
  gate (`documents.py:57-64`) and unblocking re-indexing/reprocessing (blocker
  2/3) with no re-upload. Backups stay small (bytes leave the DB). The seam makes
  the production backend a config choice, not a code change. Tenancy is provably
  enforced outside RLS. The "no partial document" invariant strengthens.
- **Negative.** A dual-write consistency model now exists (managed, not
  eliminated). Orphaned bytes are possible and require cleanup infrastructure. The
  filesystem backend has a hard single-node/non-durable ceiling. Object-storage
  backends add credentials (secrets-management theme). A new read surface
  (download) and its tenant checks must be maintained.

## Schema / API / Migration deltas

**Schema (additive, nullable — migration after `b7e3d9a1f2c4`):**

- `documents.storage_key` — opaque pointer. Nullable because pre-existing rows
  have no stored original (bytes are gone — the gate reason); new uploads always
  set it.
- `documents.storage_backend` — provenance of the writing backend.
- `documents.content_sha256` — integrity anchor for reprocessing + future dedup.
  **Included in slice 1** (Open Question 1 resolved), hashed in the same pass that
  streams the bytes to storage.
- Reuses existing `byte_size` and `content_type` (`models/documents.py`) for
  download headers. **No RLS change.**

**API:**

- Upload: no external signature change — same multipart `POST /documents`;
  internally stores bytes and records `storage_key`.
- **Deferred, NON-blocking (slice 2, Open Question 5 resolved):**
  `GET /api/v1/documents/{id}/original` — tenant-verified per _Tenant isolation_,
  streams bytes with `Content-Type` +
  `Content-Disposition: attachment; filename="<sanitized>"`; legacy rows
  (`storage_key IS NULL`) → 404 "original not available". Not required for 1.0 —
  the go-live gate is retention-for-reprocessing, which storage alone satisfies.
- Reprocess/re-index endpoint — later slice, unblocked by retained originals.

**Migration:** additive, backward-compatible, no backfill possible (legacy
originals are gone; acceptable because the gate lands before real-tenant volume).
Search/chunks unaffected; feature inert until the upload path is wired.

## Risks

- Orphan accumulation if the sweep is skipped — mitigated by immediate
  compensation + backstop sweep.
- Storage growth/cost — per-tenant quotas deferred to Phase 11.
- Filesystem backend is single-node/non-durable — explicit ceiling; prod uses
  object storage.
- IDOR/traversal on keys — mitigated by server-minted UUID keys, never
  client-supplied, root-confined.
- Encryption at rest — **deployment precondition (Open Question 3 resolved):** the
  pilot host MUST provide an encrypted volume for the documents root; no app-level
  envelope encryption for the filesystem backend in 1.0. SSE for object storage
  when it lands.
- Object-store credentials (later slices) — ties to the secrets-management theme.
- Large-file memory — fine at 10 MB; streaming I/O a later refinement.

## Implementation plan (small, independently testable slices)

1. **Storage seam + filesystem backend + retain-on-upload.** `StorageProvider`
   port; `LocalFilesystemStorage` (single backend, `tmp_path`-testable);
   `document_storage_backend` / `document_storage_root` settings; migration adding
   **all three columns — `storage_key`, `storage_backend`, `content_sha256`**;
   `repo.create` persists the key, backend, and hash; the SHA-256 is computed in
   the same pass that streams the bytes to storage; wire
   **validate(415)-then-store-then-ingest-then-commit** into the upload route with
   the immediate compensating delete; compose volume for the api documents root.
   **Tests:** bytes round-trip; `storage_key` + `content_sha256` persisted and the
   hash matches the stored bytes; 415 rejected type writes NOTHING to storage;
   ingest/422 failure ⇒ no `Document` row AND no orphaned bytes (compensation
   fires); a `put` failure ⇒ no row; cross-tenant cannot obtain another tenant's
   key (RLS SELECT → 404). Hermetic (no network).
2. **Download endpoint (deferred, non-blocking — not required for 1.0).**
   `GET /documents/{id}/original`, tenant-verified; legacy-null → 404; correct
   headers.
3. **Reconciliation sweep** (management command, set-difference with grace
   window). **No retention/hard-delete job (Open Question 2 resolved):** soft-delete
   retains bytes indefinitely in 1.0; retention windows and quotas are Phase 11.
4. **Second backend — MinIO** (directional, not binding; Open Question 6) behind
   the same interface — config-selected, proving the abstraction (and, being
   S3-API-compatible, effectively S3 too); dev compose gains a MinIO container. No
   business-logic change.
5. **Reprocess/re-index** (uses retained originals) + per-tenant quotas + retention
   — ties to blocker 2/3 and Phase 11.

**Slice 1 is the first to build and commit:** the smallest increment that makes
the go-live gate real (originals retained from that commit forward), commits to no
cloud dependency yet, and is fully testable against a temp directory with no
network — while locking in the seam that S3/MinIO/Azure later drop into unchanged.

---

## Assumptions

1. The upload size stays modest (`document_max_bytes` = 10 MB, `settings.py:149`),
   so `bytes`-in/`bytes`-out on the `StorageProvider` is acceptable for slice 1;
   streaming I/O is a later refinement.
2. `documents` remains the RLS-locked source of truth for document existence, so
   the pointer-table read is a sound tenancy gate.
3. The go-live gate holds — original-file storage lands BEFORE real-tenant volume,
   so there are few/no legacy `storage_key IS NULL` rows to reconcile.
4. Durable background-job infrastructure does not exist yet (only in-process
   `BackgroundTasks`, `chat.py`), so the reconciliation sweep ships first as a
   management command rather than a scheduled worker.
5. Document identity/PK generation can accommodate an independently-minted
   `storage_id` (the design deliberately decouples the key from `document_id` to
   avoid depending on PK-generation timing).

## Trade-offs

- **Durability/scale vs. immediate simplicity** — object storage is the 5-year
  answer, but slice 1 sacrifices multi-replica durability by shipping the
  filesystem backend first; the seam makes that a temporary, config-level ceiling.
- **Consistency vs. single-transaction simplicity** — separating bytes from the DB
  gives up one-transaction atomicity; we buy it back with argued ordering +
  compensation + sweep, accepting invisible orphaned bytes as the worst case.
- **Provenance/integrity columns vs. schema minimalism** — `storage_backend` and
  `content_sha256` are added in slice 1; the hash is near-free (computed in the
  storage-write pass) and is the integrity anchor for reprocessing, while the
  backend column pays off on a later backend migration — a small, deliberate cost
  consistent with the codebase's per-row provenance discipline.
- **Retain-on-soft-delete vs. prompt reclamation** — 1.0 retains bytes
  **indefinitely** on soft-delete (no hard-delete job), avoiding delete-path
  dual-write entirely, at the cost of unbounded space growth until retention +
  quotas land in Phase 11.

## Open Questions — Resolved

All six were resolved by the decider on 2026-07-22; rulings and reasoning
recorded below. They are reflected in the Decision, Schema deltas, and Slice
sections above.

1. **`content_sha256` — RESOLVED: include in slice 1.** Cost asymmetry: the bytes
   are already streamed to disk in slice 1, so hashing in the same pass is
   near-free, whereas adding the column later is a separate migration. It is the
   integrity anchor for the reprocessing use case this feature exists to serve.
   **Slice 1's migration therefore adds three columns: `storage_key`,
   `storage_backend`, `content_sha256`** — `content_sha256` is no longer optional.
2. **Retention / hard delete — RESOLVED: none in 1.0.** Soft-delete tombstones the
   row and retains bytes **indefinitely**; there is no hard-delete job and it is
   not per-tenant configurable. Retention windows and quotas are deferred to Phase 11. **The retention job is removed from slice scope.**
3. **Encryption at rest — RESOLVED: rely on volume/disk encryption, recorded as a
   deployment precondition.** No app-level envelope encryption for the filesystem
   backend in 1.0; **the pilot host must provide an encrypted volume** for the
   documents root. Object storage will use SSE when it lands.
4. **Compensating delete — RESOLVED: keep both**, as designed — the request-path
   best-effort compensating delete AND the reconciliation-sweep backstop.
5. **Download endpoint — RESOLVED: NOT required for 1.0.** The go-live gate is
   retention-for-reprocessing, which storage alone satisfies.
   `GET /documents/{id}/original` (slice 2) is a **deferred, non-blocking
   enhancement** — cheap to add later, does not gate the release.
6. **First object-storage backend — RESOLVED: MinIO** (slice 4, directional not
   binding). Docker/on-prem parity, runs in dev compose, and S3-API-compatible so
   it effectively proves S3 too.
