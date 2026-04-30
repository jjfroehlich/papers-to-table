# Eval

Eval can score main-app output (that was run without human review) against human-verified benchmarking data to create an evaluation score. 
It is also the scoring step the optimizer uses when it runs model/prompt/retrieval comparisons and produces reports.

## Quick Start
Eval a run bundle:

```bash
python scripts/papers_to_table.py eval --run /abs/run --gold /abs/gold.csv --schema /abs/schema.json --out /abs/eval_out
```

## Configuration

Eval is CLI-first. 

Required arguments:

- one `--run` or `--runs-root`
- `--gold`
- `--out`

Common optional arguments:

- `--schema`
- `--judge-model`
- `--judge-model-b`
- `--judge-api-base`
- `--judge-api-base-b`

Real benchmark studies should use two judges. Current defaults are:

- `judge_a=google/gemma-4-26b-a4b`
- `judge_b=openai/gpt-oss-20b`

## What It Is For

Use this if you want to:

- score extracted values against benchmark data (table with "gold" values)
- compare several runs side by side, for instance to compare different LLM models, prompts, or parameters.

Eval tool will: 

- compare the values with the correct values, and use LLMs as judges to determine if the proposed values are correct. 

The output of will: 

- evaluate per-cell correctness and evidence quality
- quantify judge disagreement and degraded behavior

## Install
The main installation command will have this installed already. 
From the repository root:

```bash
python scripts/papers_to_table.py install
```

Low-level install from the tool directory:

```bash
cd tools/eval
python -m pip install -e .[dev]
```

## Recommended Command

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

## How To Read The Metrics

- content correctness: main metric for scored content cells
- overall correctness: broader metric that can include metadata lanes
- anchor-valid rate / evidence quality: how much persisted evidence remains anchor-valid. 
- judge disagreement: how often judge A and judge B differ on their judgement of text fields
- join failures / missing proposals: where the run bundle could not line up with benchmark data as expected

## Warnings

- high disagreement: judges disagree often, so ranking confidence is weaker
- judge request failures: one judge could not complete some text-cell requests
- missing evidence or invalid anchors: the run produced values but evidence grounding is weak or missing
- unscored text cells: the evaluator could not get a deterministic or judged answer for every text cell

## Rebuild Comparison Outputs

Used to re-generate cross-run comparison files for an existing batch of runs (when you already have per-run eval outputs).

```bash
cd tools/eval
paper-eval compare --summaries /absolute/path/to/per-run --out /absolute/path/to/compare_out
```
