# Eval Tool

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Do not treat this file as normative when it conflicts with the canonical files.

- Status: Compatibility reference
- Owner: Eval
- Depends on: contracts/run-bundle.md, contracts/eval-summary.md, contracts/proposals-and-evidence.md
- Consumed by: tools/eval/, docs/tools/eval.md

## Purpose

The eval tool is an internal CLI-first evaluator for main-app run bundles.

It reads run artifacts from files, scores proposals against a human-filled gold table, and writes inspectable per-cell, per-run, and cross-run comparison artifacts.

Archive material may remain useful for historical background, but canonical eval behavior now lives in `../spec.md`.

Eval is a companion tool. It is not a second extraction product and it does not run extraction itself.

## Core workflows

The evaluator supports two workflows:

1. evaluate one or more run bundles against a gold CSV or XLSX input
2. rebuild comparison artifacts from previously written run summaries

## Tool boundaries

Eval must:

- remain a separate runtime from the main app
- read run bundles as files rather than importing main-app runtime code
- keep correctness metrics and evidence metrics separate
- keep deterministic structured scoring separate from judge-backed text scoring
- write filesystem artifacts as the canonical output surface

## Inputs and outputs

Eval consumes main-app run bundles that conform to `../contracts/run-bundle.md`.

Eval emits per-run and cross-run summaries that conform to `../contracts/eval-summary.md`.

Shared proposal and evidence expectations used during scoring are defined in `../contracts/proposals-and-evidence.md`.

## Curated benchmark suite

The current curated benchmark corpus lives under `benchmark_datasets/`.

It is currently organized as two mixed-layout datasets:

- `genome_editing_tools/`
- `spatial_transcriptomics/`

Each dataset must contain:

- `pdfs/` with exactly five active renamed PDFs
- `backup_excluded_papers/` with the preserved excluded source PDFs
- `table_template.csv` as the app-facing spreadsheet input
- `schema.csv` as the app-facing schema input with exactly `column_name,description`
- `schema.json` and `schema.md` as richer gold-annotation guides
- `dataset_readme.md`
- `source_log.csv`
- `curation_notes.md`
- `rename_map.csv`

Dataset-level benchmark files live under `benchmark_datasets/{dataset_id}/`.

The curated suite is intentionally journal-, publisher-, and layout-diverse. Each active dataset should keep exactly five PDFs, preserve traceability from original filenames to active renamed filenames, keep internal fields such as `paper_id`, `pdf_filename`, and `publisher_family` out of the app-facing table, and leave gold-standard extraction cells blank in `table_template.csv` until manual annotation.

Older tool-local benchmark locations are historical only; active datasets should be referenced from `benchmark_datasets/`.

## Scoring policy

- Headline scoring uses gold-present cells by default.
- Gold-empty cells are reported as diagnostics, not silently folded into headline correctness.
- Boolean, categorical, and numeric scoring remain deterministic.
- Text scoring is judge-backed by default, with explicit deterministic override support where appropriate.
- Runs that are degraded but contract-valid should remain scoreable whenever possible.
- Unscored outcomes must stay explicit through `scored = false` and `unscored_reason` rather than appearing as silent blanks.

## Judge path

- LM Studio is the default local-first judge path.
- The default real-benchmark judge pair is `judge_a=google/gemma-4-26b-a4b` and `judge_b=openai/gpt-oss-20b`.
- Judge behavior must remain bounded, reproducible, and fully instrumented.
- Judge failures on one cell must not abort an otherwise valid evaluation run.
- Real benchmark evaluation should run dual-judge scoring by default.
- Dual-judge execution must be judge-major: prepare all eligible text-cell requests, execute all `judge_a` work, execute all `judge_b` work, group batches by effective provider/model/settings, then merge results back into deterministic scored-cell order.
- Per-run summaries must preserve per-judge verdicts, request failures, unclear counts, disagreement counts or rates, and response-mode usage.
- Per-run summaries must include judge execution diagnostics with batch counts, eligible counts, runtime totals, execution order, model-switch counts, and cleanup failures.

## Audit outputs

Eval must emit inspectable audit summaries in stable per-run outputs for:

- evidence-anchor validation totals, validated-versus-unvalidated counts, invalid-anchor counts, and reason histograms
- evidence ID resolution from nested support fields and top-level `primary_evidence_id`, `evidence_ids`, and `ordered_supporting_evidence_ids`
- anchor outcome counts for missing evidence, valid anchors, invalid anchors, present-but-unvalidated evidence, invalid pages, missing quote text, page bounds, missing persisted text, and quote locatability
- metadata-family summaries grouped by field kind, state, and failure attribution
- dual-judge completion truth and disagreement diagnostics
- ratio and coverage metrics must remain within valid numeric bounds; impossible values are contract defects

## Ownership boundary

This file is a compatibility reference for eval-tool behavior and scope. Canonical behavior lives in `../spec.md`.

It does not own the shared run-bundle, proposal/evidence, or summary contracts. Those belong in `../contracts/`.
