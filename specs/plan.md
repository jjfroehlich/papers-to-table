# plan.md — Paper Table Agent (Spec-Kit)

## Scope (definition of done)

The implementation is done when the current codebase satisfies every section of `specs/spec.md`, specifically:

- Product summary + golden path are realized end-to-end through CLI/UI.
- Inputs/outputs/guardrails/matching/extraction/retrieval/review UX behave as specified.
- PDFs normalize into a parsed-document representation that can drive contextualized, typed retrieval without breaking evidence anchoring.
- Table-aware retrieval artifacts, schema-aware context selection, and quality preset behavior work as specified.
- Operational defaults and failure semantics are enforced and visible in `run_report.json`.
- Whole-text + paper-memory feature flag behaves as described.

## Non-goals / constraints

- No hosted backend or SaaS deployment (local-first only).
- UI stays minimal (Run/Review only) with no tuning knobs.
- Do not make benchmark harnesses, systematic parameter sweeps, or evaluation redesign the primary driver of this phase.
- Avoid speculative features not in the spec (e.g., multi-user review, cloud sync).

## Architecture summary

- **CLI entrypoint**: `paper_table_agent/cli.py` (run/resume/export/bundle/ui).
- **Pipeline runtime**: `paper_table_agent/graph/runner.py` + LangGraph wrapper in `paper_table_agent/graph/workflow.py`.
- **Core services**:
  - Parsed-document normalization + parser adapters: `paper_table_agent/pdf/*`.
  - LLM clients + JSON parsing: `paper_table_agent/llm/client.py`.
  - Matching/header extraction: `paper_table_agent/graph/matching.py`.
  - Retrieval + chunking: `paper_table_agent/retrieval/*`.
  - Context planning + schema-aware extraction policy: `paper_table_agent/graph/context_planner.py`, `paper_table_agent/graph/extraction.py`.
  - Evidence + highlighting: `paper_table_agent/graph/evidence_finder.py`, `paper_table_agent/pdf/highlight.py`.
  - Review queue + triage: `paper_table_agent/ui/*`.
  - Persistence: `paper_table_agent/store/schema.sql` + `paper_table_agent/store/db.py`.
- **Run artifacts**: emitted under `runs/<timestamp>__<table>/` (see `README.md`).

## Implementation strategy

### P0 — Structure-aware retrieval foundation

- Introduce a normalized parsed-document contract that current parser output and GROBID output can both feed.
- Add contextualized `retrieval_text` and typed structural chunks without regressing evidence validation, quote display, or highlighting.
- Add dedicated table-aware retrieval artifacts and context assembly hooks for likely table-derived fields.
- Preserve the current proposal/evidence contracts while replacing the upstream document representation underneath them.

### P1 — Schema-aware extraction and operator quality controls

- Add schema-level retrieval and evidence-source hints that bias context assembly deterministically.
- Upgrade whole-text and paper-memory modes to consume typed elements and table/caption summaries when available.
- Turn quality-first defaults into an explicit preset model and keep effective-config reporting clear.
- Add review triage cues so operators can focus on risky proposals first.

### P2 — Backend expansion and observability hardening

- Add parser adapter support for stronger layout-aware backends behind the same parsed-document contract.
- Expand debug artifacts so parser output, chunk construction, and context assembly can be inspected directly.
- Add regression fixtures for multi-column, table-heavy, and caption-heavy PDFs.

## Risk register

- **Model/provider JSON differences**: mitigate with capability probes, guided-json fallbacks, and GLM-style wrapper stripping.
- **Context window limits**: mitigate with prompt budget trimming + whole-text/memory feature flag.
- **Evidence anchoring drift**: mitigate with retrieval/display text separation, chunk normalization, and evidence finder backfill.
- **Parser normalization drift**: mitigate with one parsed-document contract plus backend-specific fixtures and parity tests.
- **Table false positives / noisy summaries**: mitigate with typed chunk fallbacks, conservative table summarization, and per-column policy hints.

## Test strategy

- **Unit tests**: parsed-document normalization, chunk typing, contextualized retrieval text, schema hints, matching, extraction, LLM JSON handling.
- **Integration tests**: stub run + UI smoke + export verification + table-aware/context-aware retrieval flows.
- **Deterministic offline tests**: hash embedding/reranker for retrieval.
- **Parser contract tests**: verify current parser path and optional parser adapters normalize into the same downstream representation.
- **Smoke commands**: `paper-table-agent ui --smoke` + stub run config.
- **Two-tier tests**: hermetic default suite plus opt-in `pytest -m live_llm` for LM Studio E2E runs on synthetic PDFs.
- **Existing evaluation harness**: keep audit/eval behavior working as a regression aid, but it is not the primary driver of this roadmap.

## Rollout strategy

- Whole-text + paper-memory remains feature-flagged in `run_config.json` and should consume stronger structure incrementally.
- Parsed-document normalization and typed chunking should ship behind compatibility layers so current extraction/evidence flows keep working during rollout.
- Debug artifacts gated by `output.debug_reports=true`.
- Capability probes auto-disable guided JSON per model on failure.
- Quality-first defaults should remain in the shipped config, and preset resolution should make those defaults more explicit rather than more ad hoc.
