# Neo AI Assistant — Architecture

Companion to [`roadmap.md`](roadmap.md). This describes the shape of the system;
the roadmap tracks what's built.

## Clean Architecture (backend)

The API (`apps/api`) is layered so business rules never depend on frameworks:

```
apps/api/app/
├── domain/          entities, value objects, domain services (framework-free)
├── application/     use cases + ports — Protocols the infrastructure implements
│   └── ports/       ChatProvider · EmbeddingProvider · Tool · WorkflowClient · …
├── infrastructure/  adapters: db (async SQLAlchemy + RLS), cache, llm, http
├── presentation/    FastAPI routers, schemas, deps
├── core/            middleware, error handlers
├── shared/          constants, enums, exceptions, utilities, types
└── ai/              AI engine: providers, agents, tools, workflows, memory
```

Two cross-cutting invariants hold everywhere:

- **Multi-tenancy is enforced in the database.** Every tenant table runs Postgres
  Row-Level Security (ENABLE + FORCE + an `organization_id = current_setting(
'app.current_tenant')::uuid` policy); the runtime role is `NOBYPASSRLS`.
- **Ports are Protocols.** Adapters (real or mock) are swapped by config. Mocks
  are the CI/test default, so the whole suite runs offline with zero external
  calls.

## The orchestration layer and its platforms

Neo's AI orchestration layer (the tool-use loop + the multi-agent runner) sits
behind the HTTP surface. Capabilities are exposed to the model **as tools**, and
side-effecting tools are gated by the per-agent permission model established in
Phase 7d. Memory (P5), Workflow (P7), and the planned Document Intelligence (P8),
Integration (P9), and Communication (P10) platforms are all **peers** behind this
layer, each behind its own Protocol port:

```
                         ┌──────────────────────────────────────────┐
                         │           Presentation (FastAPI)          │
                         │        /chat   /chat/stream (SSE)         │
                         └────────────────────┬─────────────────────┘
                                              │
                         ┌────────────────────▼─────────────────────┐
                         │           AI Orchestration Layer          │
                         │   agents · tool-use loop · per-agent      │
                         │   permission model (7d) · audit           │
                         └─┬────────┬─────────┬─────────┬─────────┬──┘
              read-only    │        │ side-fx │ read    │ side-fx │ side-fx
        ┌──────────────────▼┐ ┌─────▼─────┐ ┌─▼───────┐ ┌▼───────┐ ┌▼──────────────┐
        │ Memory Platform   │ │ Workflow  │ │ Document│ │ Integr.│ │ Communication  │
        │ (P5)              │ │ Platform  │ │ Intel.  │ │ Platf. │ │ Platform       │
        │ search / retrieve │ │ (P7·n8n)  │ │ (P8 📄) │ │ (P9)   │ │ (P10 📞✉️)      │
        │ read-only tool    │ │ decides   │ │ understand│ │ connect│ │ EXECUTES:      │
        │                   │ │ WHEN/WHY/ │ │ /search/ │ │ HR Genie│ │ voice, WhatsApp│
        │                   │ │ IF        │ │ reason   │ │ SAP·M365│ │ SMS, email,    │
        │                   │ │           │ │ over docs │ │ Jira·…  │ │ Teams, Slack…  │
        └───────────────────┘ └─────┬─────┘ └──────────┘ └────────┘ └───────▲────────┘
                                     │  triggers / requests communication    │
                                     └───────────────────────────────────────┘
                                    (Phase 7 decides · Phase 10 executes)
```

- **Memory Platform (P5)** is a **read-only** capability — `search_memory` is a
  lookup, available to read agents.
- **Workflow Platform (P7)** decides **WHEN, WHY, and under what conditions** an
  action (including a communication) occurs. Workflows are side-effecting tools.
- **Document Intelligence (P8)** gives Neo enterprise _knowledge_ — understand,
  process, search, and reason over documents — grounding later action.
- **Integration Platform (P9)** connects Neo to business systems of record (HR
  Genie, SAP, Microsoft 365, Google Workspace, Jira, GitHub, REST APIs,
  databases, …).
- **Communication Platform (P10)** **EXECUTES** communication — delivering
  messages, making AI voice calls, receiving responses, tracking delivery — over
  a unified communication API, using knowledge from documents (P8) and connected
  systems (P9). It is a set of side-effecting tools.

### Side effects require deliberate agent selection

Workflow, Integration, and Communication are **side-effecting**: they change
external systems, place calls, send messages, and spend on the user's behalf.
They are therefore governed by the **same permission model** (Phase 7d):

- the default `assistant` agent is **read-only** — it can answer, search memory,
  and (Phase 8) reason over documents, but cannot fire a workflow, place a call,
  or send an email;
- side-effecting capability requires selecting a capable agent (`operator` for
  workflows; a communication-capable agent for Phase 10) — **selecting the agent
  is the user's consent**;
- every side-effecting invocation is **audited** (actor `user_id`/`org_id`, the
  capability name, and outcome — never arguments).

A new channel or provider must be **pluggable behind its port without touching
the orchestration layer** — the same discipline as `ChatProvider`,
`EmbeddingProvider`, `Tool`, and `WorkflowClient`.

## Outbound-call safety (SSRF)

Any platform that makes outbound HTTP on tenant-influenced input (Workflow today;
Integration and Communication in future) routes through the shared SSRF guard
(`app/ai/workflows/urlguard.py`): resolve the host, reject if **any** resolved IP
is private/loopback/metadata/etc., `follow_redirects=False`, optional admin host
allowlist. See the roadmap's "Phase 7 — known gaps" for the accepted DNS-rebinding
residual and the planned IP-pinning transport.
