# Eval

Eval can score main-app output (that was run without human review) against human-verified benchmarking data to create an evaluation score. 

## What It Is For

Use this if you want to:

- score extracted values against benchmark data (table with "gold" values)
- compare several runs side by side, for instance to compare different LLM models, prompts, or parameters.
- score a filled table from external software with `--external-result` and compare it to regular main-app runs.

Eval tool will:

- compare the values with the correct values, and use LLMs as judges to determine if the proposed values are correct.
- evaluate per-cell correctness and evidence quality
- quantify judge disagreement and degraded behavior
- inspect deterministic structured false-negative risk through normal eval diagnostics

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

Real benchmark studies should use two judges. Current defaults are:

- `judge_a=google/gemma-4-26b-a4b`
- `judge_b=openai/gpt-oss-20b`

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

## Field Type
Non-text fields use deterministic scoring by default; text fields use LLM judges by default.

Eval accepts canonical field types `boolean`, `categorical`, `numeric`, and `text`.

It also accepts aliases: `bool` for `boolean`; `category` and `enum` for `categorical`; `number`, `int`, `integer`, and `float` for `numeric`; and `string`, `free_text`, and `free-text` for `text`. Unknown field types in schema or proposal metadata fail early with an explicit contract error.

When no eval schema JSON declares a column `field_type`, eval resolves the scoring type per cell from proposal metadata first, then schema metadata, then inference from the values.

Columns with allowed values infer `categorical`; pairs where both values parse as numbers infer `numeric`, so bare `0`/`1` count-like fields do not become boolean; clear boolean vocabulary such as `yes/no`, `present/absent`, and `true/false` infers `boolean`; everything else becomes `text`.


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

Eval separates deterministic scoring from LLM judging.

1. Load and validate the run bundle or external table, gold table, optional schema, and metadata.
2. Join proposals to gold cells by stable row and column identity. Record missing, duplicate, or mismatched cells.
3. Resolve each field as `boolean`, `categorical`, `numeric`, or `text`.
4. Score structured fields and fields with an explicit deterministic policy.
5. Queue judge-backed text cells, including normalized exact matches by default. Use `--enable-text-exact-match-fast-path` to bypass judging for those matches.
6. Run all work for one judge before the next, grouping requests by provider, model, and settings.
7. Merge judge verdicts, disagreements, evidence checks, and deterministic results into the per-cell records.
8. Write run summaries, followed by comparison files when applicable.


## How To Read The Metrics

Start with `content_correctness`. It is the main score for target content cells and counts missing or unscored gold-present cells as incorrect. Use `content_correctness_scored_only` to inspect only cells that received a score.

| Metric | Meaning |
| --- | --- |
| `content_correctness` | Correctness for target content cells. Structured fields are deterministic; text fields normally use one or two LLM judges. |
| `overall_correctness` | Broader correctness that may include metadata fields. |
| `anchor_valid_rate` and `evidence_grounded_correctness` | Whether evidence exists, has valid anchors, and supports correct content. |
| `judge_disagreement_rate` | Share of dual-judged text cells where the judges disagree. High values weaken confidence. |
| `missing_proposal_count` | Gold target cells without a proposal. |
| `join_failure_count` | Missing, duplicate, mismatched, or unmatched target-cell records. Excluded columns are counted separately in `excluded_proposal_count`. |
| `structured_deterministic_failure_count` | Incorrect structured cells scored without an LLM. |
| `structured_adjudication_eligible_count` and `structured_adjudication_eligible_failure_rate` | Structured failures that look like soft mismatches worth inspecting. They do not change the score. |

Per-cell records explain the aggregates. Check `proposal_status`, `evidence_status`, `review_bucket`, `reason_codes`, `deterministic_failure_kind`, and `adjudication_eligible` when a summary looks surprising. Structured fields remain deterministic; Eval does not currently use LLM adjudication to override their scores.

Eval writes the underlying records before aggregating them into `run_summary.json`, `run_summary.csv`, and cross-run comparison files.

## Warnings

- `"high disagreement"`: judges disagree often, so ranking confidence is weaker
- `"judge request failures"`: one judge could not complete some text-cell requests
- `"missing evidence or invalid anchors"`: the run produced values but evidence grounding is weak or missing
- `"unscored text cells"`: the evaluator could not get a deterministic or judged answer for every text cell
