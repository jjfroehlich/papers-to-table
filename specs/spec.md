# Extract Structured Info from Papers Eval Specification

## Purpose

`extract-structured-info-from-papers-eval` is a CLI-first evaluator for run bundles produced by `extract-structured-info-from-papers`.

It reads run artifacts as files, scores proposals against a human-filled gold table, and writes inspectable per-cell, per-run, and cross-run comparison artifacts.

## Product Surface

The evaluator provides two operator workflows:

1. Evaluate one or more run bundles against a gold CSV or XLSX input.
2. Rebuild comparison artifacts from previously written per-run summaries.

The evaluator is not a GUI product and does not run extraction itself.

## Supported Inputs

The evaluator accepts:

- one `--run` directory, repeated `--run` directories, or one `--runs-root`
- one gold CSV or XLSX file
- one optional schema JSON file

### Run Bundle Contract

Each run bundle must contain:

- `run.json`
- `proposals/proposals.jsonl`

The evaluator may also load these files when present:

- `config.snapshot.json`
- `inputs/input_summary.json`
- `summaries/run_summary.json`
- sidecar evidence files
- persisted page-text artifacts
- per-evidence JSON records under the main app's canonical evidence directory
- parsed-document artifacts when page-text-compatible evaluator inputs must be reconstructed from the run bundle

Each proposal record must publish these stable join fields:

- `row_id`
- `column_name`
- `cell_id`

The evaluator scores against published stable identifiers and does not infer hidden main-app join logic.

### Eval-Mode Provenance

When a run is marked as eval mode, the evaluator requires reproducibility metadata for the gold and masked tables, including hashes and snapshot paths.

### Gold Input Contract

Gold inputs may be CSV or XLSX.

Supported gold layouts are:

- wide format with `row_id` and one column per field
- long format with `row_id`, `column_name`, and `gold_value`

For XLSX inputs, one worksheet is scored per invocation. If no worksheet is selected, the first worksheet in workbook order is used.

Gold inputs must provide unique `row_id + column_name` pairs.

## Scoring Behavior

### Gold-Present Policy

Headline scoring includes only gold-present cells by default.

Gold-empty cells are not part of the headline score. Proposals on gold-empty cells are reported as diagnostics.

### Field-Type Scoring

The evaluator resolves a field type per cell and applies one of these scoring paths:

- boolean: deterministic normalization and exact comparison
- categorical: deterministic normalization with alias and `allowed_values` support
- numeric: deterministic normalization with global tolerance defaults and optional per-column overrides
- text: judge-backed scoring by default, with deterministic override when explicitly configured

Judge-backed text scoring uses a bounded response-mode ladder:

- `json_schema`
- `json_object`
- prompt-only JSON mode with app-side parsing

When a text field uses judge-backed scoring and an individual judge request fails at runtime, the evaluator must preserve a per-cell output instead of aborting the whole run. That cell is recorded as unscored with `judge_verdict = "unclear"` and explicit judge-failure diagnostics.

The evaluator may also run two judges on the same text cells when a secondary judge is configured. In that mode it must preserve per-judge verdicts and emit explicit aggregate outputs including `correctness_mean`, `correctness_judge_a`, `correctness_judge_b`, `correctness_abs_delta`, and `judge_disagreement`.

The evaluator must treat degraded but contract-valid main-app runs as scoreable whenever possible. If a run cannot receive a headline score, artifacts must still record `scored = false` plus an explicit `unscored_reason` instead of leaving primary metrics silently blank.

### Join Handling

For gold-present cells, the evaluator distinguishes at least these join outcomes:

- matched proposal
- missing proposal
- duplicate proposals for one join key
- `cell_id` mismatch between gold and proposal

Proposals with no matching gold cell are written as diagnostics and do not count as scored cells.

## Evidence Behavior

Evidence quality is reported separately from correctness.

The evaluator validates lightweight evidence anchors based on page and quote text.

The evaluator must remain compatible with the main app's canonical run bundle even when evidence is persisted as one JSON file per evidence record and page text must be reconstructed from parsed-document artifacts rather than a dedicated sidecar file.

Evidence outcomes distinguish at least these cases:

- `anchor_valid`
- `evidence_present_but_unvalidated`
- `anchor_invalid`
- `missing_evidence`

Evidence metrics do not replace correctness metrics.

When exact page-text sidecars are absent, the evaluator may use stable fallbacks derived from persisted run artifacts, such as parsed-document blocks or normalized source-text artifacts, but it must keep the distinction between fully validated anchors and evidence-present-but-unvalidated outcomes explicit.

## Outputs

Each evaluated run writes:

- `scored_cells.jsonl`
- `scored_cells.csv`
- `run_summary.json`
- `run_summary.csv`
- `judge_records.jsonl` when judge-backed text scoring runs

Batch evaluation and `compare` write:

- `runs_comparison.csv`
- `runs_comparison.xlsx`
- `runs_comparison.parquet`

The CLI may also emit an optional JSON completion payload on stdout. File artifacts remain the canonical contract.

Judge-backed text scoring failures must remain visible in file artifacts through `judge_records.jsonl`, `scored_cells.*`, and run summaries rather than terminating batch evaluation for otherwise valid run bundles.

## Reported Metrics

The evaluator reports headline correctness metrics, evidence metrics, and diagnostics separately.

Headline correctness metrics include:

- `structured_accuracy`
- `boolean_accuracy`
- `categorical_accuracy`
- `numeric_accuracy`
- `text_accuracy`
- `proposal_coverage_on_gold_present`

Evidence metrics include:

- `anchor_valid_rate`
- `correct_and_anchored_rate`

Diagnostics include counts such as:

- `gold_present_cell_count`
- `gold_empty_cell_count`
- `filled_on_gold_empty_count`
- `missing_proposal_count`
- `duplicate_proposal_join_count`
- `cell_id_mismatch_count`
- `unmatched_proposal_count`
- `join_failure_count`
- `evidence_present_but_unvalidated_count`
- `judge_request_failed_count`
- `judge_a_request_failed_count`
- `judge_b_request_failed_count`
- `judge_unclear_text_cell_count`
- `judge_a_unclear_text_cell_count`
- `judge_b_unclear_text_cell_count`
- `judge_json_schema_text_cell_count`
- `judge_json_object_text_cell_count`
- `judge_prompt_only_text_cell_count`

The evaluator must also propagate compact main-app provenance fields into flat per-run comparison rows so downstream optimizer reporting can attribute degraded structured-output modes, parse repair, extraction contract validity, and retrieval-policy choices without reloading verbose run diagnostics.

## Non-Goals

This evaluator does not:

- run extraction
- edit gold tables
- provide a GUI
- import main-app Python code at runtime
- fold correctness and evidence into one opaque score
- score multiple XLSX worksheets in one invocation

## Acceptance Criteria

The product is acceptable when:

1. One run or many runs can be scored from the CLI against CSV or XLSX gold inputs.
2. The evaluator fails explicitly when required artifact files or stable join fields are missing.
3. The evaluator can load the main app's canonical evidence artifacts without requiring main-app runtime imports.
4. Headline scoring uses only gold-present cells by default.
5. Boolean, categorical, and numeric scoring remain deterministic.
6. Text fields use a constrained judge by default, with explicit deterministic override support.
7. Correctness metrics and evidence metrics are reported separately.
8. Per-run and batch artifacts are written with stable filenames.
9. The comparison artifact contains one row per run with run metadata, metrics, and diagnostics.
10. Optional JSON stdout mode supplements, but does not replace, file outputs.
