# extract-structured-info-from-papers-eval

CLI-first evaluation for `extract-structured-info-from-papers` run bundles.

## Install

```bash
python -m pip install -r requirements.txt
```

## Batch 1 CLI

```bash
python -m paper_eval evaluate --run path/to/run --gold gold.csv --out out/
python -m paper_eval evaluate --run path/to/run --gold gold.xlsx --gold-sheet Sheet1 --out out/
python -m paper_eval evaluate --run path/to/run-a --run path/to/run-b --gold gold.csv --out out/
python -m paper_eval evaluate --runs-root path/to/runs --gold gold.csv --out out/
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

`row_index` may be present for debugging context, but the evaluator does not use row index as the primary scoring join.

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
```

`scored_cells.*` includes per-cell join status, raw values, normalized values, correctness, and diagnostics.
