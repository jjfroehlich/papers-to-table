# extract-structured-info-from-papers-eval

`extract-structured-info-from-papers-eval` is a CLI-first evaluator for run bundles produced by `extract-structured-info-from-papers`.

It loads one or more run bundles, compares proposals against a human-filled gold table, and writes per-cell, per-run, and cross-run comparison artifacts to disk.

## Install

```bash
python -m pip install -r requirements.txt
```

Current runtime dependencies:

- `openpyxl` for XLSX gold inputs and XLSX comparison outputs
- `pyarrow` for Parquet comparison outputs

## When LM Studio Is Required

LM Studio is only required when a text field cannot be resolved by deterministic exact-match scoring and therefore still needs judge-backed text scoring.

Defaults:

- provider: `lm_studio`
- API base: `http://127.0.0.1:1234/v1`
- judge model: `qwen/qwen3.5-35b-a3b`
- temperature: `0`

Override settings with:

- `--judge-model`
- `--judge-model-b`
- `--judge-api-base`
- `--judge-api-base-b`
- `PAPER_EVAL_JUDGE_MODEL`
- `PAPER_EVAL_JUDGE_API_BASE`
- `PAPER_EVAL_JUDGE_API_KEY`

If judge-backed text scoring is needed and an individual judge request fails at runtime, the affected text cell is recorded as `unclear` with judge-failure diagnostics instead of aborting the full evaluation.

Judge requests now use the same bounded fallback ladder as the main app's extraction path:

- `json_schema`
- `json_object`
- prompt-only JSON mode with app-side parsing

This means eval can benchmark judge models that only work reliably in `structured_output_mode = none`, while still preserving explicit diagnostics about fallback use and judge failures.

When `--judge-model-b` is provided, eval runs both judges on the same judge-backed text cells and writes dual-judge metrics into run summaries. The explicit headline metrics are `content_correctness` and `content_correctness_scored_only`; the older `correctness` and `correctness_mean` fields remain as compatibility aliases to the same content-only values. `overall_correctness`, `metadata_correctness`, `correctness_judge_a`, `correctness_judge_b`, `correctness_abs_delta`, and `judge_disagreement` remain explicit downstream-facing outputs for diagnostics and optimizer consumption.

When the configured judge model is not already active in LM Studio, the evaluator attempts to load it through LM Studio's model-management API before sending judge requests. The evaluator verifies judge-model readiness once per evaluation process and reuses that result instead of probing LM Studio before every scored cell.

## Inputs

You need:

1. one `--run` directory, repeated `--run` directories, or one `--runs-root`
2. one gold CSV or XLSX file
3. an optional schema JSON file for explicit field types, aliases, numeric tolerances, or text-scoring overrides

The optional schema JSON can also scope which columns count toward scoring:

- `scored_columns` or `target_columns`: explicit allow-list of scored columns
- `excluded_columns`: explicit deny-list of columns to skip

When neither is provided, eval excludes common metadata columns by default: `Title`, `Authors`, and `Publication Year`.

### Required Run Artifacts

Every run bundle must contain:

- `run.json`
- `proposals/proposals.jsonl`

The evaluator also loads these files when present:

- `config.snapshot.json`
- `inputs/input_summary.json`
- `summaries/run_summary.json`
- `evidence/evidence.jsonl`
- `evidence/evidence.json`
- `support/evidence.jsonl`
- canonical per-evidence JSON files under `evidence/*.json`
- page-text artifacts under `evidence/` or `support/`
- parsed-document artifacts under `parsed/<pdf_id>/` when page text must be reconstructed from the run bundle

### Required Proposal Join Fields

Every proposal row must publish:

- `row_id`
- `column_name`
- `cell_id`

The evaluator joins on those published stable identifiers and does not reconstruct hidden main-app ID logic.

### Eval-Mode Provenance

When `run_mode` or `mode` resolves to `eval`, the run bundle must also publish:

- `gold_table_hash`
- `gold_table_snapshot_path`
- `masked_table_hash`
- `masked_table_snapshot_path`

Referenced snapshot paths must exist inside the run bundle or evaluation fails.

The evaluator also accepts the main app's current eval-export shape, including nested `eval_artifacts.gold_table.*` and `eval_artifacts.masked_working_table.*` metadata plus `masked_working_table_path`.

When a main-app bundle publishes `artifact_schema_version`, `proposal_schema_version`, or `evidence_schema_version`, the evaluator validates those version tags explicitly and fails fast on unsupported versions.

### Gold Formats

Supported gold inputs are:

- CSV
- XLSX

Supported gold layouts are:

- wide format with `row_id` and one column per field
- long format with `row_id`, `column_name`, `gold_value`, and optional `cell_id`

For XLSX inputs:

- one worksheet is scored per invocation
- `--gold-sheet` selects a worksheet explicitly
- if `--gold-sheet` is omitted, the first worksheet in workbook order is used

Gold inputs must provide unique `row_id + column_name` pairs.

## Commands

### Evaluate One Run

```bash
python -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out out/example-single
```

### Evaluate Many Runs

```bash
python -m paper_eval evaluate \
  --runs-root tests/fixtures/example_eval/runs \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out out/example-batch
```

Repeated `--run` is also supported:

```bash
python -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --run tests/fixtures/example_eval/runs/run-b \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out out/example-batch
```

### Rebuild Comparison Outputs

`compare` rebuilds comparison artifacts from stored per-run summaries without rescoring proposals.

```bash
python -m paper_eval compare \
  --summaries out/example-batch/per-run \
  --out out/example-batch/compare-rebuilt
```

`--summaries` may point to either:

- the per-run summary root
- a specific `run_summary.json`

### Optional JSON Stdout Mode

Both commands support `--json-output` for machine-readable completion payloads on stdout.

Artifacts written under `--out` remain the canonical outputs.

## Output Layout

`evaluate` writes:

```text
out/
  per-run/
    {run_id}/
      scored_cells.jsonl
      scored_cells.csv
      run_summary.json
      run_summary.csv
      judge_records.jsonl
  compare/
    runs_comparison.csv
    runs_comparison.xlsx
    runs_comparison.parquet
```

`judge_records.jsonl` is written only when judge-backed text scoring actually runs.

`compare` writes the three `runs_comparison.*` artifacts directly under its `--out` directory.

## Scoring Behavior

### Headline Scoring Scope

Headline scoring uses only gold-present content cells by default.

When the evaluated run bundle includes main-app matching artifacts, the evaluator first restricts the gold table to rows whose PDFs were actually matched in that run. This keeps optimizer and batch scoring focused on the subset of workbook rows represented by PDFs in the run's input folder.

Gold-empty cells are excluded from headline accuracy and counted only through diagnostics such as `filled_on_gold_empty_count`. Metadata or front-matter fields remain visible as explicit secondary metrics instead of silently inflating the headline score.

Run summaries and comparison rows also propagate main-app extraction-lane and failure-attribution provenance. This keeps parser-gap, retrieval-miss, extraction-miss, evidence-ambiguity, judge-failure, and judge-unclear outcomes visible without reloading verbose main-app diagnostics.

### Field Types

The evaluator resolves one scoring path per cell:

- boolean: deterministic
- categorical: deterministic with alias and `allowed_values` support
- numeric: deterministic with global tolerances and optional per-column overrides
- text: normalized exact matches are scored deterministically first; remaining text mismatches are judge-backed by default, with explicit deterministic override support; judge runtime failures degrade to `unclear` scored outputs with diagnostics

### Evidence

Evidence is tracked separately from correctness.

The evaluator distinguishes these evidence outcomes:

- `anchor_valid`
- `evidence_present_but_unvalidated`
- `anchor_invalid`
- `missing_evidence`

`anchor_valid_rate` counts only fully validated anchors.

## Metrics

Headline metrics:

- `content_correctness`
- `content_correctness_on_gold_present`
- `content_correctness_mean`
- `content_correctness_scored_only`
- `correctness` (compatibility alias for `content_correctness`)
- `correctness_mean` (compatibility alias for `content_correctness_scored_only`)
- `overall_correctness`
- `overall_correctness_scored_only`
- `correctness_judge_a`
- `correctness_judge_b`
- `correctness_abs_delta`
- `judge_disagreement`
- `structured_accuracy`
- `boolean_accuracy`
- `categorical_accuracy`
- `numeric_accuracy`
- `text_accuracy`
- `proposal_coverage_on_content_gold_present`
- `proposal_coverage_on_all_gold_present`
- `proposal_coverage_on_gold_present` (compatibility alias for `proposal_coverage_on_content_gold_present`)

Evidence metrics:

- `anchor_valid_rate`
- `correct_and_anchored_rate`

Diagnostic metrics include:

- `gold_present_cell_count`
- `gold_empty_cell_count`
- `filled_on_gold_empty_count`
- `missing_proposal_count`
- `judge_request_failed_count`
- `judge_a_request_failed_count`
- `judge_b_request_failed_count`
- `judge_unclear_text_cell_count`
- `judge_a_unclear_text_cell_count`
- `judge_b_unclear_text_cell_count`
- `judge_json_schema_text_cell_count`
- `judge_json_object_text_cell_count`
- `judge_prompt_only_text_cell_count`
- `duplicate_proposal_join_count`
- `cell_id_mismatch_count`
- `unmatched_proposal_count`
- `join_failure_count`

Per-run summaries and rebuilt comparison rows also keep scoring truth explicit with:

- `scored`
- `unscored_reason`
- compact main-app provenance fields such as `structured_output_mode`, `prompt_only_degraded_mode_used`, `parse_repair_used`, `extraction_contract_valid`, and retrieval-policy fields
- `evidence_present_but_unvalidated_count`

## Limitations

Current limitations:

- no GUI
- no multi-sheet XLSX scoring in one invocation
- no fallback to hidden main-app join-key logic
- no structured-field support proxy metric yet
- no retrieval-style metric such as `gold_in_document_rate` yet
