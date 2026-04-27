# Eval companion

The eval tool scores main-app run bundles against gold data.

It is a companion tool, not a second extraction product.

## What it is for

Use eval when you already have one or more run bundles and want to:

- score extracted values against a gold table
- inspect per-cell correctness and evidence quality
- compare several runs side by side
- quantify judge disagreement and degraded behavior

## Install

From the repository root:

```bash
python scripts/papers_to_table.py install
```

Low-level install from the tool directory:

```bash
cd tools/eval
python -m pip install -e .[dev]
```

## Recommended command

```bash
python scripts/papers_to_table.py eval \
  --run /absolute/path/to/run_bundle \
  --gold /absolute/path/to/gold.csv \
  --schema /absolute/path/to/schema.json \
  --out /absolute/path/to/eval_out
```

Low-level command:

```bash
cd tools/eval
paper-eval evaluate ...
```

## Inputs

You need:

- one run bundle path or a runs-root directory
- one gold CSV or XLSX file
- optional schema metadata JSON for field typing, aliases, tolerances, and text-scoring overrides

Required run-bundle artifacts:

- `run.json`
- `proposals/proposals.jsonl`

## Outputs

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

## How to read the metrics

- **content correctness**: main headline metric for scored content cells
- **overall correctness**: broader metric that can include metadata lanes
- **anchor-valid rate / evidence quality**: how much persisted evidence remains anchor-valid
- **judge disagreement**: how often judge A and judge B differ on text fields
- **join failures / missing proposals**: where the run bundle could not line up with gold as expected

## Common warnings

- high disagreement: judges disagree often, so ranking confidence is weaker
- judge request failures: one judge could not complete some text-cell requests
- missing evidence or invalid anchors: the run produced values but evidence grounding is weak or missing
- unscored text cells: the evaluator could not get a deterministic or judged answer for every text cell

## Rebuild comparison outputs

```bash
cd tools/eval
paper-eval compare --summaries /absolute/path/to/per-run --out /absolute/path/to/compare_out
```
