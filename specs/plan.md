# plan.md — Paper Table Agent (current)

## Current focus

- P0 correctness: evidence-backed proposals and reliable highlights.
- Robust matching: fallback adjudication and header grounding.
- Retrieval resilience: sane chunking, embedding fallbacks, and debug traces.
- Minimal UI: Run + Review only, with evidence-first review.
- CLI/install ergonomics: working console script and headless UI smoke path.
- Keep docs/specs aligned with actual behavior.

## Remaining work

- Monitor retrieval retry heuristics and adjust thresholds with real PDFs.
- Expand fixture coverage for tricky PDFs (scanned pages, multi-column layouts).
