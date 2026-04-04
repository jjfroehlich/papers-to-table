# extract-structured-info-from-papers-eval

CLI-first evaluation for `extract-structured-info-from-papers` run bundles.

## Install

```bash
python -m pip install -r requirements.txt
```

## CLI

```bash
python -m paper_eval evaluate --run path/to/run --gold gold.csv --out out/
python -m paper_eval evaluate --run path/to/run --gold gold.xlsx --gold-sheet Sheet1 --out out/
python -m paper_eval evaluate --run path/to/run-a --run path/to/run-b --gold gold.csv --out out/
python -m paper_eval evaluate --runs-root path/to/runs --gold gold.csv --out out/
python -m paper_eval compare --summaries out/per-run --out out/compare
```

## Current input contract

### Run bundle

Required:

- `run.json`
- `proposals/proposals.jsonl`

Optional but loaded when present:

- `config.snapshot.json`
- `inputs/input_summary.json`
- `summaries/run_summary.json`
- `evidence/evidence.jsonl`
- `evidence/evidence.json`
- `support/evidence.jsonl`

Each proposal record must publish stable scoring identifiers directly in the artifact bundle:

- `row_id`
- `column_name`
- `cell_id`

Batch 1 matches proposals to gold cells by stable `row_id + column_name` and treats `cell_id` as a required published audit field plus an explicit mismatch diagnostic. `row_index` may be present for debugging context, but the evaluator does not use row index as the primary scoring join.

### Gold table

CSV and XLSX are supported.

- XLSX evaluation is exactly one worksheet per invocation.
- `--gold-sheet` selects the worksheet explicitly.
- If `--gold-sheet` is omitted, the evaluator uses the first worksheet in workbook order.

Supported gold layouts:

1. wide format with a required `row_id` column and one data column per field
2. long format with `row_id`, `column_name`, `gold_value`, and optional `cell_id`

For wide format, optional `{column_name}__cell_id` columns preserve explicit gold cell ids for audit and mismatch diagnostics.

## Current Batch 1 scoring behavior

- scores only gold-present cells in headline structured metrics
- keeps gold-empty cells out of headline scoring and reports them as diagnostics
- uses stable join keys from artifacts instead of row-index-first alignment
- deterministically scores boolean, categorical, and numeric fields
- resolves numeric tolerances from schema per-column overrides first, then global defaults
- leaves text fields unscored in Batch 1 and records them explicitly for later judge-backed handling

## Current Batch 2 comparison and evidence behavior

- `evaluate` now always writes per-run outputs plus a flat comparison table with one row per run
- batch comparison artifacts are written to CSV, XLSX, and Parquet from the same normalized rows
- comparison rows flatten run metadata into stable columns such as `run_id`, `mode`, `model_id`, `vision_model_id`, `parser_identity`, `parser_version`, `prompt_identity`, `schema_identity`, and `config_hash`
- per-run summaries and comparison rows keep evidence quality separate from correctness with `anchor_valid_rate`, `correct_and_anchored_rate`, and `evidence_present_but_unvalidated_count`
- anchor validation requires `page` plus `quote_text`, and when persisted page text is available the quote must be locatable on the cited page to count as `anchor_valid`
- evidence with page and quote but without enough validation support, including quote strings that are not locatable in available persisted text, is reported as `evidence_present_but_unvalidated` instead of counting as fully valid

## Outputs

For each run:

```text
out/
  per-run/
    {run_id}/
      scored_cells.jsonl
      scored_cells.csv
      run_summary.json
      run_summary.csv
  compare/
    runs_comparison.csv
    runs_comparison.xlsx
    runs_comparison.parquet
```

`scored_cells.*` includes per-cell join status, raw values, normalized values, correctness, evidence outcome, and diagnostics.
