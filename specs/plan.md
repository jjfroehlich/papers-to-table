# plan.md — Paper Table Agent (current)

## Current focus

- P0 correctness: proposals always keep values; evidence is annotated and a finder pass adds highlights when possible.
- Robust matching: header heuristics + DOI-aware bonuses with deterministic fallback.
- Parsing resilience: whitespace/token health checks with OCR fallback and normalized chunk tables.
- Review UX: matched rows only, prev/next navigation, auto-advance decisions, constrained PDF pane.
- Deterministic hash retrieval backends for offline validation.

## Remaining work

- Tune DOI matching weights with real datasets.
- Expand fixture coverage for tricky PDFs (scanned pages, multi-column layouts).
