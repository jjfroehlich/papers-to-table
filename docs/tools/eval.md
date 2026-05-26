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

- one `--run`, `--runs-root`, or `--external-result`
- `--gold`
- `--out`

Common optional arguments:

- `--schema`
- `--judge-model`
- `--judge-model-b`
- `--judge-api-base`
- `--judge-api-base-b`

Low-level `paper_eval evaluate` also supports `--enable-text-exact-match-fast-path` for calibration runs that intentionally want normalized exact-match text cells to bypass judge scoring. This is disabled by default.

Real benchmark studies should use two judges. Current defaults are:

- `judge_a=google/gemma-4-26b-a4b`
- `judge_b=openai/gpt-oss-20b`

## What It Is For

Use this if you want to:

- score extracted values against benchmark data (table with "gold" values)
- compare several runs side by side, for instance to compare different LLM models, prompts, or parameters.
- score a filled table from external software with `--external-result` and compare it to regular main-app runs.

Eval tool will: 

- compare the values with the correct values, and use LLMs as judges to determine if the proposed values are correct. 
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
python -m paper_eval evaluate --run /abs/run --gold /abs/gold.csv --schema /abs/schema.json --out /abs/eval_out
```

External filled table:

```bash
cd tools/eval
python -m paper_eval evaluate \
  --external-result /abs/external_filled_table.csv \
  --gold /abs/table_gold.csv \
  --out /abs/eval_out
```

## Test command
```bash
bash scripts/test-eval-tool.sh
```

## Inputs

You need:

- run bundle directory (`run.json`, `proposals/proposals.jsonl` minimum)
- or an external filled result table with stable `row_id` values
- gold table (csv/xlsx)
- optional eval schema JSON for field typing, aliases, tolerances, and text-scoring overrides

Required run-bundle artifacts:

- `run.json`
- `proposals/proposals.jsonl`

## Outputs
- summary metrics
- per-cell outputs
- compare artifacts when batch mode is used

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

## Execution Phases

Eval is intentionally staged so deterministic scoring and LLM judging are not interleaved cell by cell.

1. Load inputs: read the run bundle, proposals, gold table, optional eval schema, and run metadata.
2. Join cells: align proposals to gold values by stable row and column identity. Missing or ambiguous joins become explicit metrics.
3. Score deterministic cells: numeric, boolean, categorical, date-like, and text fields with an explicit deterministic policy are scored without an LLM.
4. Collect judge-needed cells: judge-backed free-text cells, including normalized exact text matches by default, are collected into a pending judge queue. The low-level `--enable-text-exact-match-fast-path` flag restores the older exact-match bypass when deliberately requested.
5. Run judge-major batches: eval iterates by judge label first, then groups cells by provider, model, and settings. This means judge A handles its grouped cells, then judge B handles its grouped cells, instead of switching models for every individual cell.
6. Merge judged cells: per-judge verdicts, disagreement state, evidence checks, and deterministic scores are merged into `scored_cells`.
7. Aggregate outputs: write per-run summaries first, then comparison files when multiple runs or existing summaries are compared.


## How To Read The Metrics

Eval first joins canonical run proposals to gold rows and columns. It uses stable run metadata when available (`row_id`, `row_index`, `column_name`) plus the gold table and optional eval schema. Cells that cannot be joined become join failures or missing-proposal counts rather than being treated as wrong values silently.

Metrics are calculated from these joined cells:

- content correctness: the main score for target content cells. Numeric, boolean, and categorical fields are scored deterministically where possible; free-text fields can be judged by one or two configured LLM judges.
- overall correctness: a broader aggregate that can include metadata lanes when the schema included them.
- evidence quality: checks whether persisted evidence exists and remains usable, including anchor-valid highlights, page references, and evidence type.
- canonical outcome accounting: `proposal_status`, `evidence_status`, `review_bucket`, and `reason_codes` are loaded from the proposal artifact. Diagnostic outcomes such as `error`, `not_attempted`, and `not_applicable` are accounted for separately from ordinary wrong values.
- judge disagreement: the rate at which judge A and judge B differ on text-cell correctness.
- missing proposals: target cells present in gold data but missing from the run proposals.
- join failures: run or gold records that could not be aligned to the expected row/column contract.

The evaluator writes per-cell records first, then aggregates those records into `run_summary.json`, `run_summary.csv`, and the cross-run comparison files.

## Warnings

- high disagreement: judges disagree often, so ranking confidence is weaker
- judge request failures: one judge could not complete some text-cell requests
- missing evidence or invalid anchors: the run produced values but evidence grounding is weak or missing
- unscored text cells: the evaluator could not get a deterministic or judged answer for every text cell

## Rebuilding Comparison Outputs

Can be used to re-generate cross-run comparison files for an existing batch of runs (when you already have per-run eval outputs).

```bash
cd tools/eval
paper-eval compare --summaries /absolute/path/to/per-run --out /absolute/path/to/compare_out
```
