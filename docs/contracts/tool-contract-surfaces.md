# Contract Surfaces Between Main App, Eval, and Optimizer

This note records the intended boundaries between the three major repository areas.

## Main app -> eval

The main app publishes run bundles that eval consumes.

Stable surfaces include:

- `run.json`
- `config.snapshot.json`
- `proposals/proposals.jsonl`
- published proposal join fields: `row_id`, `column_name`, `cell_id`
- optional supporting summaries and evidence artifacts when present

Eval does not reconstruct hidden internal row or cell identity logic. It scores from published identifiers and published artifacts.

## Main app -> optimizer

The optimizer launches the main app through the stable automation interface rather than importing app runtime logic.

Stable surfaces include:

- `python -m backend.app.automation ...`
- machine-readable automation payloads
- persisted run summaries and artifact pointers
- config-overlay behavior driven by optimizer candidate bundles

The optimizer does not own extraction logic or review logic.

## Eval -> optimizer

The optimizer consumes eval outputs as scoring truth.

Stable surfaces include:

- eval CLI entrypoints
- per-run `run_summary.json`
- configured metric mappings from eval outputs into optimizer primary, guardrail, and diagnostic groups

The optimizer does not duplicate scoring logic.

## Separation of responsibilities

- main app: extraction, evidence presentation, human review, export
- eval: scoring, benchmarking, comparison outputs
- optimizer: orchestration, candidate tracking, calibration studies, decision reports

This separation is intentional and is preserved in the monorepo.
