# extract-structured-info-from-papers-eval

CLI-first evaluation for `extract-structured-info-from-papers` run bundles.

## Install

```bash
python -m pip install -r requirements.txt
```

## What inputs are required

You need:

1. one run directory, many `--run` directories, or a `--runs-root`
2. one gold CSV or XLSX file
3. optional schema JSON when you want field types, numeric tolerances, aliases, or text scoring overrides

### Required run-bundle files

- `run.json`
- `proposals/proposals.jsonl`

### Optional run-bundle files that the evaluator loads when present

- `config.snapshot.json`
- `inputs/input_summary.json`
- `summaries/run_summary.json`
- `evidence/evidence.jsonl`
- `evidence/evidence.json`
- `support/evidence.jsonl`
- `evidence/page_text.json`
- `evidence/page_texts.json`
- `evidence/pages.json`
- `support/page_text.json`
- `support/page_texts.json`
- `support/pages.json`

### Stable join-key contract required from the main app

Every proposal row must publish:

- `row_id`
- `column_name`
- `cell_id`

The evaluator scores by stable published join keys, not by reverse-engineering main-app ID logic. If any of `row_id`, `column_name`, or `cell_id` is missing, evaluation fails immediately with a contract error. `row_index` may be present for debugging context, but it is not used as the primary scoring join.

If gold publishes a `cell_id` and the matched proposal publishes a different `cell_id`, the cell is not scored. The mismatch is recorded in `scored_cells.*`, counted in `cell_id_mismatch_count`, and listed in `join_diagnostics`.

### Eval-mode provenance contract

When a run is marked `run_mode=eval`, the evaluator now requires reproducibility fields for the source tables:

- `gold_table_hash`
- `gold_table_snapshot_path`
- `masked_table_hash`
- `masked_table_snapshot_path`

If either snapshot path is missing or points at a file that is not present in the run bundle, evaluation fails immediately.

### Gold file formats

CSV and XLSX are supported.

- XLSX scoring is exactly one worksheet per invocation.
- `--gold-sheet` selects a worksheet explicitly.
- If `--gold-sheet` is omitted, the first worksheet in workbook order is used.

Supported gold layouts:

1. wide format with a required `row_id` column and one data column per field
2. long format with `row_id`, `column_name`, `gold_value`, and optional `cell_id`

Wide-format gold may also include `{column_name}__cell_id` columns for explicit audit IDs. Gold cells must have unique `row_id + column_name` pairs; duplicate gold join keys fail fast.

## How to evaluate one run

```bash
python -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out out/example-single
```

## How to evaluate many runs

```bash
python -m paper_eval evaluate \
  --runs-root tests/fixtures/example_eval/runs \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out out/example-batch
```

You can also pass repeated `--run` arguments:

```bash
python -m paper_eval evaluate \
  --run path/to/run-a \
  --run path/to/run-b \
  --gold gold.csv \
  --out out/
```

## Rebuild comparison outputs without rescoring

```bash
python -m paper_eval compare --summaries out/example-batch/per-run --out out/example-batch/compare-rebuilt
```

## Text judge behavior

Text fields use judge-backed scoring by default.

- pass `--judge-model` to fix the judge model for the whole evaluation run
- or set `PAPER_EVAL_JUDGE_MODEL`
- set `PAPER_EVAL_JUDGE_API_KEY` for authentication
- optionally set `PAPER_EVAL_JUDGE_API_BASE` or pass `--judge-api-base`

Judge guardrails:

- fixed model per evaluation run
- temperature `0`
- bounded field name, field description, gold value, proposed value, and optional evidence excerpt
- strict verdict labels: `correct`, `incorrect`, `unclear`
- persisted metadata in `scored_cells.*` and `judge_records.jsonl`

If a text field resolves to judge-backed scoring and no judge model is configured, evaluation fails immediately. Highly standardized text columns can opt into deterministic scoring in schema or proposal metadata.

## What the main metrics mean

### Headline metrics

- `structured_accuracy`: accuracy over scored boolean, categorical, and numeric gold-present cells
- `boolean_accuracy`
- `categorical_accuracy`
- `numeric_accuracy`
- `text_accuracy`: accuracy over scored text cells
- `proposal_coverage_on_gold_present`: fraction of gold-present cells with exactly one scoreable matched proposal

### Evidence metrics

- `anchor_valid_rate`: fraction of scored cells with at least one fully validated evidence anchor
- `correct_and_anchored_rate`: fraction of scored cells that are both correct and anchor-valid

### Diagnostics

- `gold_present_cell_count`
- `gold_empty_cell_count`
- `filled_on_gold_empty_count`
- `missing_proposal_count`
- `duplicate_proposal_join_count`
- `cell_id_mismatch_count`
- `unmatched_proposal_count`
- `join_failure_count`
- `evidence_present_but_unvalidated_count`

## Headline vs diagnostic metrics

Headline metrics are:

- `structured_accuracy`
- per-type structured accuracies
- `text_accuracy`
- `proposal_coverage_on_gold_present`

Evidence and retrieval-style signals are separate from the headline score.

- `anchor_valid_rate` and `correct_and_anchored_rate` are evidence metrics, not headline correctness
- gold-empty proposals are diagnostics, not headline errors
- join-key failures are diagnostics you can inspect, not silently guessed matches

## Default gold-present-cell scoring policy

By default the evaluator only scores gold-present cells in headline metrics.

- gold-present cells are scored
- gold-empty cells are left out of headline scoring
- proposals on gold-empty cells are counted as diagnostics only

This keeps incomplete gold tables from turning into false negatives.

## Correctness and evidence are separate

The evaluator does not blend answer correctness and evidence quality into one opaque score.

- a cell can be correct but not anchor-valid
- a cell can be anchor-valid but incorrect
- `correct_and_anchored_rate` is reported separately so both dimensions stay inspectable

## Diagnostics currently implemented

- `anchor_valid_rate` checks whether evidence has a valid page, non-empty quote text, and locatable quote text when persisted page text is available
- `evidence_present_but_unvalidated_count` captures cases where evidence exists but could not be fully validated
- join diagnostics are written into per-cell outputs and summarized in `run_summary.json`

`gold_in_document_rate` is not implemented yet.

## Outputs

Every evaluation run writes stable artifact names:

```text
out/
  per-run/
    {run_id}/
      scored_cells.jsonl
      scored_cells.csv
      judge_records.jsonl          # only when judge-backed text scoring is used
      run_summary.json
      run_summary.csv
  compare/
    runs_comparison.csv
    runs_comparison.xlsx
    runs_comparison.parquet
```

For the same input artifacts, schema, run ordering, and judge configuration, structured outputs are deterministic. Judge-backed text results are only as reproducible as the configured external model, but the evaluator fixes the judge request shape, temperature, and stored metadata.

### Example `run_summary.json` excerpt

```json
{
  "run_id": "run-a",
  "metrics": {
    "structured_accuracy": 1.0,
    "text_accuracy": 1.0,
    "anchor_valid_rate": 0.3333333333333333,
    "join_failure_count": 0
  }
}
```

### Example `scored_cells.csv` rows

```text
record_kind,row_id,column_name,join_status,was_scored,is_correct,evidence_outcome
gold_cell,row-1,status,matched,True,True,anchor_valid
gold_cell,row-2,notes,matched,True,True,missing_evidence
```

### Example `runs_comparison.csv` rows

```text
run_id,structured_accuracy,text_accuracy,anchor_valid_rate,join_failure_count
run-a,1.0,1.0,0.3333333333333333,0
run-b,0.6666666666666666,0.5,0.0,0
```

## Current limitations

- no GUI
- no multi-sheet XLSX scoring in one invocation
- no automatic fallback to hidden main-app join-key logic
- no `gold_in_document_rate` metric yet
- no structured-field support proxy metric yet
- no heavyweight faithfulness or entailment system

## Tested command paths

The repository test suite covers:

- single-run evaluation
- batch evaluation
- comparison artifact rebuilding with `compare`
- join-key failure behavior
- eval-mode provenance validation
- normalization, comparators, evidence checks, and text judge integration

Run the suite from the repo root:

```bash
python -m unittest discover -s tests -v
```
