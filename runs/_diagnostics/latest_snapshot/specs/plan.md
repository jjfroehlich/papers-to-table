# plan.md — Paper Table Agent (Spec-Kit)

## Scope (definition of done)

The implementation is done when the current codebase satisfies every section of `specs/spec.md`, specifically:

- Product summary + golden path are realized end-to-end through CLI/UI.
- Inputs/outputs/guardrails/matching/extraction/retrieval/review UX behave as specified.
- Operational defaults and failure semantics are enforced and visible in `run_report.json`.
- Whole-text + paper-memory feature flag behaves as described.

## Non-goals / constraints

- No hosted backend or SaaS deployment (local-first only).
- UI stays minimal (Run/Review only) with no tuning knobs.
- Avoid speculative features not in the spec (e.g., multi-user review, cloud sync).

## Architecture summary

- **CLI entrypoint**: `paper_table_agent/cli.py` (run/resume/export/bundle/ui).
- **Pipeline runtime**: `paper_table_agent/graph/runner.py` + LangGraph wrapper in `paper_table_agent/graph/workflow.py`.
- **Core services**:
  - LLM clients + JSON parsing: `paper_table_agent/llm/client.py`.
  - Matching/header extraction: `paper_table_agent/graph/matching.py`.
  - Retrieval + chunking: `paper_table_agent/retrieval/*`.
  - Evidence + highlighting: `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/pdf/highlight.py`.
  - Persistence: `paper_table_agent/store/schema.sql` + `paper_table_agent/store/db.py`.
- **Run artifacts**: emitted under `runs/<timestamp>__<table>/` (see `docs/repo_audit.md`).

## Implementation strategy

### P0 — Spec compliance alignment

- Keep spec outputs aligned with the actual run/export behavior.
- Ensure run reports include LLM capability probe summaries.
- Surface effective prompt caps and per-stage LLM call counts in run reports.
- Maintain evidence anchoring and highlight reliability contracts.
- Enforce backend capability routing so constraints-off backends never receive schema/grammar/regex payloads.
- Guarantee structured prompt budgeting and batching so retrieved chunks are never dropped by truncation and all missing columns are attempted.
- Add context planning to select fulltext/memory/retrieval with column-first extraction and deterministic quote anchoring.
- Keep memory-mode extraction payloads anchored to notes-only content while storing summaries in artifacts.

### P1 — Reliability & usability polish

- Expand retrieval/parse fixtures for tricky PDF layouts.
- Broaden evidence finder heuristics for domain-specific phrases.

### P2 — Regression hardening

- Add additional golden-path regression fixtures (multi-column, OCR-heavy).
- Extend coverage for evidence locator edge cases (ellipsis, hyphenation).

## Risk register

- **Model/provider JSON differences**: mitigate with capability probes, guided-json fallbacks, and GLM-style wrapper stripping.
- **Context window limits**: mitigate with prompt budget trimming + whole-text/memory feature flag.
- **Evidence anchoring drift**: mitigate with chunk normalization + evidence finder backfill.

## Test strategy

- **Unit tests**: parsing, normalization, matching, extraction, LLM JSON handling.
- **Integration tests**: stub run + UI smoke + export verification.
- **Deterministic offline tests**: hash embedding/reranker for retrieval.
- **Smoke commands**: `paper-table-agent ui --smoke` + stub run config.
- **Two-tier tests**: hermetic default suite plus opt-in `pytest -m live_llm` for LM Studio E2E runs on synthetic PDFs.
- **Evaluation harness**: audit proposals compared to filled cells with proposal_eval artifacts and run_report updates.

## Rollout strategy

- Whole-text + paper-memory remains feature-flagged in `run_config.json`.
- Debug artifacts gated by `output.debug_reports=true`.
- Capability probes auto-disable guided JSON per model on failure.
