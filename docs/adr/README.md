# Architecture Decision Records

This directory records significant architectural decisions for Neo. There was no
prior ADR convention in `docs/` (only `architecture.md` and `roadmap.md`), so
this file establishes one.

## Convention

- One decision per file, named `NNNN-kebab-case-title.md`, `NNNN` a
  zero-padded, monotonically increasing integer starting at `0001`.
- Never rewrite an accepted ADR to change its decision. Supersede it with a new
  ADR and set the old one's status to `Superseded by NNNN`.
- Every claim about **current** system behaviour must cite `path:line`. If a
  claim cannot be supported from the code, the ADR says so explicitly.

## Template

```
# NNNN. Title
Status: Proposed | Accepted | Rejected | Superseded by NNNN
Date: YYYY-MM-DD
Context / Decision / Consequences (positive and negative) / Alternatives.
```

## Index

- [0001](0001-block-aware-chunker.md) — BlockAwareChunker (Proposed)
