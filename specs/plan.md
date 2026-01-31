# plan.md — Paper Table Agent (current)

## Current focus

- Proposal-model behavior: inference-first extraction with anchored evidence and graded confidence.
- Whole-text + paper-memory mode (feature-flagged) to provide broader context when retrieval-only snippets are insufficient.
- JSON robustness for mapping + extraction: prompt hardening, wrapper stripping, and parsing fallbacks.
- Backend compatibility probes + regex/grammar incompatibility classification with graceful fallbacks.
- Evidence anchoring + highlight reliability improvements (page/chunk alignment and quote-to-page matching).
- Diagnostics + provenance artifacts for LLM requests, truncation decisions, and evidence anchors.

## Remaining work

- Tune DOI matching weights with real datasets.
- Expand fixture coverage for tricky PDFs (scanned pages, multi-column layouts).
- Improve evidence finder query hints with more domain-specific phrase templates.
