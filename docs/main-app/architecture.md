(placeholder, this page should describe in more detail how the app actually works, what is happening step by step, best with some good example text snippets)

# Architecture and data flow
(placeholder, we need a better diagram here, it can be ascii, or in some other way, but needs to be accurate and detailed and informative)
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