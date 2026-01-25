# plan.md — Paper Table Agent (current)

## Current focus

- P0 correctness: proposals always keep values; evidence is annotated and a finder pass adds highlights when possible.
- Value-first extraction with inference rationale, plus evidence finder repair/locator pass.
- Robust matching: header heuristics + DOI-aware bonuses with deterministic fallback.
- Parsing resilience: whitespace/token health checks with OCR fallback and normalized chunk tables.
- Review UX: matched rows only, prev/next proposal navigation, auto-advance decisions, constrained PDF pane.
- Deterministic hash retrieval backends for offline validation.
- JSON extraction/repair hardening with prompt sanitization (drop NaN examples) and optional LLM request/response recording.

## Remaining work

- Tune DOI matching weights with real datasets.
- Expand fixture coverage for tricky PDFs (scanned pages, multi-column layouts).
- Improve evidence finder query hints with more domain-specific phrase templates.
