# Extraction Accuracy and Speed Improvements
 
- Status: Supporting implementation plan, not current implementation truth.
- Current behavior owner: `specs/spec.md`.
- Purpose: define the next main-app extraction improvements and the optimizer measurement path for accuracy and speed.

This file records the agreed plan for improving the complete main app. When these items are implemented, update `specs/spec.md`, `specs/plan.md`, `specs/tasks.md`, config examples, tests, and docs in the same pass as the code.

## Summary

Build the improvement as a main-app execution upgrade, then quantify it with optimizer after the full feature path exists. The new fast path should be field-group batching, exposed as a candidate mode for A/B comparison against current `per_cell`, not a hard default yet. Keep the app general by deriving behavior from schemas and parsed evidence, never benchmark-specific column names.

Key decisions:

- Use LLM-primary column planning, with deterministic validation/fallback so bad plans cannot break extraction.
- Use field-group batching as the first batched implementation; defer full-row extraction.
- Keep existing proposal/evidence/review/export contracts unchanged.
- Run optimizer after the complete main-app feature is implemented.

## Rewritten Priorities

### P0: Guardrails And Baseline

- Fix target eligibility so schema-defined blank metadata fields can be filled.
- Add preservation tests for headers, row order, non-target columns, and blank unsupported values.
- Record current and new call-count/runtime metrics in run summaries.

### P1: LLM-Primary Column Planning

- Add a schema-level planner that produces a generic `column_plan.json`.
- The LLM proposes extraction kind, grouping, visual policy, allowed values, blank policy, and retrieval hints.
- Deterministic validation clamps the plan to supported enum values and falls back to safe defaults when uncertain.
- Planner prompts must be schema-driven and must not mention benchmark datasets.

### P2: Evidence Cards And Retrieval Profiles

- Build one compact evidence card per matched PDF from parser metadata, abstract, methods/results snippets, figure catalog, captions, tables, detected numbers, and candidate evidence.
- Use column plans to choose retrieval profiles, not one broad top-k strategy for every cell.
- Evidence cards remain generic paper summaries, not benchmark-specific answer templates.

### P3: Field-Group Extraction Candidate Mode

- Add `extraction.mode = per_cell | field_group`; keep `per_cell` as the control path.
- Group cells by column plan, such as metadata, methods, results, claims, and visual.
- One LLM call returns multiple cell proposals for one paper/group.
- Split group outputs into existing per-cell `ProposalRecord` and `EvidenceRecord` artifacts.
- Retry only failed, invalid, or evidence-missing cells through the existing per-cell path.

### P4: Schema-Triggered Vision And Lazy Rendering

- Trigger vision from column-plan visual policy or explicit failed-evidence fallback, not merely because retrieval found a caption.
- Batch visual questions by `(pdf_id, figure_ref/page)` where possible.
- Add `parser.page_render_policy = eager | lazy`; keep current eager behavior available, use lazy for the new benchmark candidate.
- Preserve review UI image loading through on-demand rendering.

### P5: Optimizer Quantification

- Add optimizer knobs for extraction mode, planner mode, page render policy, and vision policy.
- Compare current `per_cell` against the full new `field_group` candidate.
- Report accuracy, wall time, text calls, vision calls, batch success rate, retry rate, blank rate, and score per minute.

## Implementation Changes

### Config And API Additions

- `extraction.mode`: `per_cell` default/control, `field_group` new candidate.
- `extraction.column_planning.mode`: `llm_primary` with deterministic fallback.
- `parser.page_render_policy`: `eager` or `lazy`.
- Optimizer candidate knobs for extraction mode, planner mode, page render policy, and vision policy.

### Artifacts

- Add `planning/column_plan.json`.
- Add `evidence_cards/{pdf_id}.json`.
- Extend run stats with batch calls, fallback calls, planner calls, text/vision call counts, and throughput metrics.
- Do not change proposal/evidence join keys or export semantics.

### Generality Constraints

- No benchmark-specific column-name logic outside tests.
- Planner and retrieval behavior must be driven by schema text, field types, allowed values, and parsed paper evidence.
- Synthetic non-benchmark schemas must be included in tests.

## Test Plan

### Unit Tests

- Blank `Authors` or `Publication Year` can be filled when schema-defined.
- Column planner handles benchmark schemas and unrelated synthetic schemas.
- Invalid LLM planner output is clamped or falls back safely.
- Evidence cards are built from parsed documents without benchmark assumptions.
- Field-group output splits into valid per-cell proposals.
- Failed batch cells fall back to per-cell extraction.
- Vision is not triggered only because a caption appears in retrieval.
- Lazy rendering does not render pages until vision/review needs them.

### Integration Tests

- Headless run with `per_cell` still works.
- Headless run with `field_group` produces normal review/export artifacts.
- Contract verification passes for both modes.
- Optimizer can compare current and new modes and report speed/accuracy metrics.

### Benchmark Acceptance

- New candidate produces proposals for all eligible cells.
- Runtime target: under 1 hour for the three-dataset suite.
- Stretch target: near 20 minutes with warm parse cache.
- Accuracy must be measured against current app, not assumed.

## Assumptions

- `field_group` is the first batched mode; full-row extraction is deferred until field-group reliability is proven.
- The LLM is primary for schema planning, but deterministic validation remains authoritative.
- Optimizer measurement happens after the complete main-app feature path is implemented.
- Canonical specs, docs, config examples, and tests are updated when behavior changes, not only this planning file.
