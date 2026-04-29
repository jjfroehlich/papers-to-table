# Architecture and data flow

```mermaid
flowchart LR
  A[Inputs: table + schema + PDFs + config] --> B[Preflight/readiness]
  B --> C[Parsing]
  C --> D[Matching]
  D --> E[Retrieval]
  E --> F[Extraction]
  F --> G[proposals/proposals.jsonl + evidence/evidence.jsonl]
  G --> H[Review decisions]
  H --> I[Export content-only XLSX + audit logs]
  G --> J[Eval consumes run bundle]
  I --> J
  J --> K[Optimizer orchestrates repeated main-app + eval runs]
```

## Dependency boundaries
- Main app emits run bundles.
- Eval consumes run bundles from files only.
- Optimizer orchestrates main app + eval.
- Eval must not import main-app runtime internals.
- Optimizer must not reimplement eval or main-app logic.

## Key contracts
- Run bundle contract: `specs/spec.md` and `specs/contracts/`
- Artifact schemas: `specs/contracts/schemas/`
- Canonical CLI: `scripts/papers_to_table.py`
