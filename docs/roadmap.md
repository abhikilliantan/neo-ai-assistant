# Neo AI Assistant — Roadmap

Canonical phase roadmap. This is the single source of truth for phase status and
scope; per-phase implementation detail lives in the code and commit history
(`git log --oneline`, each commit tagged `(phase N…)`).

| Phase | Name                                    |     Status     |
| ----: | --------------------------------------- | :------------: |
|     1 | Foundation                              |  ✅ Complete   |
|     2 | Identity Platform                       |  ✅ Complete   |
|     3 | AI Platform                             |  ✅ Complete   |
|     4 | Chat Persistence                        |  ✅ Complete   |
|     5 | Memory Platform                         |  ✅ Complete   |
|     6 | AI Orchestration & Multi-Agent Platform |  ✅ Complete   |
|     7 | Workflow Platform (n8n)                 |  ✅ Complete   |
|     8 | Document Intelligence Platform 📄       | 🚧 In progress |
|     9 | Integration Platform                    |   ⬜ Planned   |
|    10 | Communication Platform 📞✉️             |   ⬜ Planned   |
|    11 | Enterprise Readiness                    |   ⬜ Planned   |

> **Sequencing note (8 → 9 → 10).** Document Intelligence, Integration, and
> Communication are ordered deliberately — see
> [Sequencing rationale](#sequencing-rationale-8--9--10) below. Communication was
> briefly slotted as Phase 8; that ordering was **considered and reversed**.

---

## Completed phases

### ✅ Phase 1 — Foundation

Monorepo (Yarn/pnpm workspaces + uv), Docker Compose stack (Postgres 16 +
pgvector, Redis 7, n8n), FastAPI service and Next.js 15 app scaffolded on Clean
Architecture, health/readiness checks, structured logging, CI + pre-commit.

### ✅ Phase 2 — Identity Platform

JWT auth (register/login/refresh), users · organizations · memberships · API
keys, RBAC roles/permissions, and **multi-tenancy enforced by Postgres
Row-Level Security** (ENABLE + FORCE + per-table `organization_id` policy, tenant
set via `app.current_tenant` GUC). The `neo_app` runtime role runs `NOBYPASSRLS`.

### ✅ Phase 3 — AI Platform

`ChatProvider` and `EmbeddingProvider` ports (Protocols) with Anthropic + mock
implementations, config-driven provider selection (fail-fast on misconfig),
token/usage accounting. Mock providers are the CI/test default — zero external
calls in tests.

### ✅ Phase 4 — Chat Persistence

`conversations` / `messages` tables, `POST /chat` and `POST /chat/stream` (SSE).
Short bookending transactions so no DB connection is held across the multi-second
LLM call. **Ephemeral invariant:** intermediate `tool_use`/`tool_result` turns
and injected memory context are never persisted — history is exactly
`[user, assistant]`.

### ✅ Phase 5 — Memory Platform

`memories` (pgvector, HNSW cosine index) + `user_preferences`, best-effort
extract→embed→store after a turn (off the response path), threshold-gated
semantic retrieval injected as ephemeral context, and `search_memory` as a
read-only tool.

### ✅ Phase 6 — AI Orchestration & Multi-Agent Platform

The tool-use loop (inside the provider), `ToolRegistry`, the `Tool` port, live
tool "chips" (`ToolInvocation` + SSE `tool` frames, name+ok only — no
arguments), and a **multi-agent layer**: `AgentDefinition` + `AgentRegistry` +
`AgentRunner`, per-agent persona and tool-subset filtering, per-conversation
agent persistence, and the web agent picker. Closed with transaction-discipline
hardening (6k): `/chat` short bookending txns, background memory writes, aligned
provider-failure semantics.

### ✅ Phase 7 — Workflow Platform (n8n)

**Workflows are tools.** Neo invokes an n8n workflow mid-conversation exactly the
way it invokes `search_memory`, so the tool loop, registry, per-agent filtering,
and chips all compose for free.

- `WorkflowClient` port + `WorkflowRegistry`; `MockWorkflowClient` (CI/test
  default) and the real `N8nWorkflowClient` (hard timeout, no retries, log-safe
  failure markers, token only ever a request header).
- `WorkflowTool` adapter merges workflows into the per-request tool set with a
  build-time collision check.
- **Permission model (7d):** the default `assistant` agent is read-only;
  side-effecting workflows require the **`operator`** agent — deliberate agent
  selection _is_ the user's consent. Every workflow invocation is audited
  (`workflow.invoked` at INFO with agent + workflow + `user_id`/`org_id`, no
  arguments).
- The web UI renders workflow calls as distinct **action chips** ("Created a
  task") vs read-only lookup chips.
- **SSRF guard (7f-1):** outbound URLs are validated by resolving the host and
  checking every resulting IP (loopback, `169.254.169.254` metadata, RFC1918,
  IPv6 ULA/link-local, multicast, etc.), with `follow_redirects=False` and an
  optional admin host allowlist.
- **Tenant-defined workflows (7f-2):** an RLS-locked `workflows` table; the
  per-request tool set = built-ins + this tenant's enabled rows, resolved and
  URL-validated on every request. `operator`'s allow-list is expanded
  per-request so tenant workflows are both visible in specs and invocable.

#### ⚠️ Phase 7 — known gaps & accepted residuals

These are deliberate, documented limitations — deferred, not finished:

- **No workflow WRITE / CRUD API.** Tenant `workflows` rows must currently be
  inserted directly into the database. A management surface is **deferred to
  Phase 11 (Enterprise Readiness)** alongside the rest of the admin tooling.
- **Fail-closed on a non-empty allowlist.** Tenant workflows resolve only when
  `settings.n8n_allowed_hosts` is non-empty. **An empty allowlist disables
  tenant workflows entirely** (built-ins are unaffected). Rationale: the SSRF
  guard accepts DNS rebinding as a residual (see below), which is fully open in
  deny-by-range mode — tolerable for code-owned URLs, not for tenant-supplied
  ones.
- **DNS rebinding is an accepted residual risk** in the SSRF guard. The guard
  validates resolved IPs, but httpx re-resolves on connect, so an
  attacker-controlled name with a tiny TTL could answer public on the check and
  private on the connect. We accept this for now rather than pin the connection
  to the validated IP, because **pinning while preserving TLS SNI + certificate
  verification requires a custom httpx transport, and a subtly wrong one
  silently disables cert verification** — a worse outcome than the narrow
  rebinding window. It is mitigated by `follow_redirects=False` and the host
  allowlist. An **IP-pinning transport is a known future slice.**
- **No per-tenant workflow credentials.** Tenant rows carry no secrets; outbound
  calls use the deployment's single configured token. Per-tenant credential
  storage — encryption at rest + key management — is its own future work and is
  deliberately not smuggled into Phase 7.

---

## Sequencing rationale (8 → 9 → 10)

Document Intelligence, Integration, and Communication are ordered so each builds
on the last:

- **Phase 8 — Document Intelligence** lets Neo understand, process, search, and
  reason over enterprise documents **before** it interacts with external
  systems.
- **Phase 9 — Integration** connects Neo to business applications (HR Genie,
  SAP, Microsoft 365, Google Workspace, Jira, GitHub, REST APIs, databases, and
  future enterprise services).
- **Phase 10 — Communication** builds on **both**, so Neo communicates using
  knowledge from documents and connected systems — email, WhatsApp, SMS, Teams,
  Slack, push notifications, calendar invitations, and AI-powered phone calls.

Communication is a major capability that deserves its own phase rather than
arriving straight after Workflow. Deferring it means that by the time Neo can
call, message, and email on the user's behalf, it **already has enterprise
knowledge (Phase 8) and connected systems (Phase 9)** — making its
communications materially more useful.

---

## In progress

### 🚧 Phase 8 — Document Intelligence Platform 📄

**Purpose.** Let Neo understand, process, search, and reason over enterprise
documents — before it acts on external systems. Ingestion and parsing across
formats, extraction and classification, semantic search, and
retrieval-augmented reasoning over per-tenant document corpora.

This gives Neo enterprise _knowledge_ first: later phases (Integration,
Communication) can then act and communicate grounded in what the documents say,
not just what the user typed. Document access is tenant-scoped under the same
RLS discipline as the rest of the platform, and document reasoning is exposed to
the model through the same Protocol-port/tool seam as everything else.

---

## Planned

### ⬜ Phase 9 — Integration Platform

Connectors to third-party business systems of record — **HR Genie, SAP,
Microsoft 365, Google Workspace, Jira, GitHub, REST APIs, databases, and future
enterprise services** — behind the same port discipline, giving Neo connected
systems to read from and act on. Feeds both Document Intelligence (as document
sources) and Communication (as recipients/context).

### ⬜ Phase 10 — Communication Platform 📞✉️

A unified communication layer across channels — AI-powered phone calls, WhatsApp,
SMS, email, Microsoft Teams, Slack, push notifications, calendar invitations, and
future providers. Users express intent in natural language (_"Call Neha and ask
her to book a restaurant for tomorrow at 9 PM"_, _"Email the proposal to the
client"_, _"Notify Finance on Teams that payroll completed"_); Neo determines
intent, selects the channel, generates context-aware messages or conversations,
executes via the appropriate provider, monitors delivery status and responses,
and reports the outcome.

**Architectural boundary (Workflow ⟷ Communication).**

- The **Workflow Platform (Phase 7)** decides **WHEN, WHY, and under what
  conditions** communication occurs.
- The **Communication Platform (Phase 10)** **EXECUTES** it — delivering
  messages, making AI voice calls, receiving responses, tracking delivery
  status, and exposing a unified communication API to Neo.

**Pluggability.** Every provider sits behind a common abstraction; new channels
must be pluggable **without changes to the AI orchestration layer** — the same
Protocol-port discipline already used for `ChatProvider`, `EmbeddingProvider`,
`Tool`, and `WorkflowClient`.

**Permission model.** Communication actions are **side-effecting** (they place
calls, send messages, spend on the user's behalf) and therefore inherit the
**same agent-permission model Phase 7d established**: deliberate agent selection
is required. A chat with the default read-only agent must **never** be able to
place a phone call or send an email — a communication-capable agent must be
explicitly selected, and every communication action is audited.

### ⬜ Phase 11 — Enterprise Readiness

The admin/management surface (including the deferred **workflow CRUD API** from
Phase 7), audit/observability, quotas & rate limits, per-tenant credential
management (encryption at rest + key management), and the operational hardening
required for enterprise deployment.
