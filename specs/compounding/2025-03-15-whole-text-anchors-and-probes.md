# Whole-text anchors + backend probes

## What changed
- Added a feature-flagged whole-text/paper-memory flow that passes page-anchored text to proposal models when it fits the context budget.
- Introduced backend probes and error classification to distinguish regex/grammar incompatibilities from generic HTTP failures.
- Recorded LLM request metadata per stage to improve post-run diagnostics without full payload capture.

## Why it matters
Proposal models need broader context than short retrieval snippets. Anchored whole-text or memory summaries preserve traceability while improving inference quality. Backend probes prevent brittle runs by surfacing compatibility issues early.

## Durable rule?
Yes. Always provide anchored context when enabling inference-first models, and probe backend compatibility before long runs.

## Proposed update
Add a runbook section describing how to enable whole-text mode and how to interpret backend probe warnings.
