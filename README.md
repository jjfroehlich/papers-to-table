# extract-structured-info-from-papers-eval

`extract-structured-info-from-papers-eval` is a small CLI-first evaluator for run bundles produced by `extract-structured-info-from-papers`.

Its job is to:

- load one run or many run bundles from the main app
- load a human-filled gold CSV or XLSX table
- score extracted values against gold
- keep structured scoring deterministic and inspectable
- use a constrained local LLM judge for text fields when needed
- write explicit per-cell, per-run, and batch comparison artifacts to disk

It is intentionally **not** the main app, not a GUI, and not a general benchmark platform.

## Relationship to the main app

The main app and this evaluator have different responsibilities.

The main app is responsible for:

- generating eval-ready run bundles
- masking target cells in eval mode
- persisting stable identifiers and run metadata
- persisting proposal and evidence artifacts

This evaluator is responsible for:

- reading those artifacts as files
- validating the artifact contract
- scoring proposals against gold
- producing comparison outputs for benchmarking and debugging

This repo does **not** import main-app Python code or recreate hidden main-app join logic.

## Install

Install the dependencies before running the CLI or tests:

```bash
python -m pip install -r requirements.txt
```

The current requirements include:

- `openpyxl` for XLSX gold inputs and XLSX comparison outputs
- `pyarrow` for Parquet comparison outputs

## What inputs the evaluator expects

You need:

1. one run directory, repeated `--run` directories, or a `--runs-root`
2. one gold CSV or XLSX file
3. an optional schema JSON file when you want explicit field types, numeric tolerances, aliases, or text scoring overrides

## Required main-app run artifacts

Every run bundle must contain:

- `run.json`
- `proposals/proposals.jsonl`

Optional files loaded when present:

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

## Stable join-key contract required from the main app

Every proposal row must publish:

- `row_id`
- `column_name`
- `cell_id`

The evaluator scores by those published stable join keys. It does **not** reverse-engineer hidden main-app row or cell ID logic.

If any of `row_id`, `column_name`, or `cell_id` is missing:

- evaluation fails immediately with a contract error

If gold publishes a `cell_id` and the matched proposal publishes a different `cell_id`:

- the cell is not scored
- the mismatch is written into `scored_cells.*`
- `cell_id_mismatch_count` increases
- the problem is listed in `join_diagnostics`

`row_index` may be present for debugging context, but it is not the primary scoring join.

## Eval-mode provenance contract

When a run is marked `run_mode=eval`, the evaluator requires reproducibility fields for the source tables:

- `gold_table_hash`
- `gold_table_snapshot_path`
- `masked_table_hash`
- `masked_table_snapshot_path`

If a required eval-mode provenance field is missing, or a referenced snapshot path does not exist inside the run bundle, evaluation fails immediately.

## Gold file formats

CSV and XLSX are supported.

XLSX policy:

- exactly one worksheet is scored per invocation
- `--gold-sheet` selects a worksheet explicitly
- if `--gold-sheet` is omitted, the first worksheet in workbook order is used

Supported gold layouts:

1. **wide format** with a required `row_id` column and one data column per field
2. **long format** with `row_id`, `column_name`, `gold_value`, and optional `cell_id`

Wide-format gold may also include `{column_name}__cell_id` columns for explicit audit IDs.

Gold contract hardening:

- wide-format gold must include `row_id`
- duplicate `row_id + column_name` pairs fail fast
- missing required join fields fail fast
- empty CSV files or missing header rows fail fast

## Default scoring policy

### Gold-present cells are scored by default

Headline metrics only score **gold-present** cells by default.

- gold-present cells are scored
- gold-empty cells are excluded from headline accuracy
- proposals on gold-empty cells are counted only as diagnostics

This prevents incomplete gold tables from turning into false negatives in the main score.

### Structured fields remain deterministic

These field types are deterministic-first:

- boolean
- categorical
- numeric

### Text fields use the judge by default

Text fields use the constrained judge by default unless a field is explicitly configured as deterministic in schema or proposal metadata.

That means the evaluator is **not** a judge-only black box:

- structured fields remain deterministic
- text judging is constrained, bounded, and explicit
- judge metadata is persisted for auditability

## LM Studio judge path

The default text judge path is **LM Studio** using its OpenAI-compatible local API.

Default settings:

- provider: `lm_studio`
- API base: `http://127.0.0.1:1234/v1`
- configured judge model: `qwen/qwen3.5-35b-a3b`
- temperature: `0`

### LM Studio setup

1. Install and open LM Studio.
2. Load or serve the model `qwen/qwen3.5-35b-a3b`.
3. Start LM Studio's local OpenAI-compatible server.
4. Run the evaluator normally.

If your LM Studio server is on a different URL, pass `--judge-api-base` or set `PAPER_EVAL_JUDGE_API_BASE`.

If you want a different configured judge model, pass `--judge-model` or set `PAPER_EVAL_JUDGE_MODEL`.

If your LM Studio server requires authentication, set `PAPER_EVAL_JUDGE_API_KEY`.

### Judge guardrails

The judge path is intentionally narrow:

- fixed model per evaluation run
- structured JSON-schema-shaped output
- bounded field name, description, gold value, proposal value, and evidence excerpt
- strict verdicts: `correct`, `incorrect`, `unclear`
- no long free-form reasoning written as a core artifact

### What happens when the judge is unavailable

If a text field resolves to judge-backed scoring and LM Studio or the configured judge model is unavailable:

- evaluation fails truthfully
- the evaluator does **not** silently claim that text fields were judged

## What judge metadata is persisted

Judge-backed text cells and `judge_records.jsonl` persist:

- `judge_provider`
- `judge_configured_model_id`
- `judge_resolved_model_id`
- `judge_prompt_version`
- `judge_prompt_hash`
- `judge_verdict`
- `judge_input_hash`
- `judge_temperature`

Compatibility field:

- `judge_model_id` is also written and matches the configured judge model

The evaluator stores both the configured judge model and the actual runtime-served model id returned by LM Studio when available.

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

You can also pass repeated run directories:

```bash
python -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --run tests/fixtures/example_eval/runs/run-b \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out out/example-batch
```

## How to rebuild comparison outputs without rescoring

```bash
python -m paper_eval compare \
  --summaries out/example-batch/per-run \
  --out out/example-batch/compare-rebuilt
```

## Optional machine-readable stdout mode

Artifact files remain the canonical scoring contract.

For orchestration tools, the CLI also supports optional machine-readable completion payloads on stdout:

```bash
python -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --gold tests/fixtures/example_eval/gold.csv \
  --out out/example-single \
  --json-output

python -m paper_eval compare \
  --summaries out/example-batch/per-run \
  --out out/example-batch/compare-rebuilt \
  --json-output
```

JSON stdout payloads include `schema_version`, command kind, success status, output directory, and key produced artifact paths. They are a convenience surface only; files written under `out/` are still the source of truth.

## Output artifacts

Every evaluation writes stable artifact names:

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

Notes:

- CSV is the easiest artifact to inspect or diff
- XLSX and Parquet are alternate renderings of the same comparison rows
- `judge_records.jsonl` is only written when judge-backed scoring actually runs

## What the metrics mean

### Headline metrics

Headline metrics are the main correctness metrics you should compare across runs.

- `structured_accuracy`: accuracy over scored boolean, categorical, and numeric gold-present cells
- `boolean_accuracy`: accuracy over scored boolean gold-present cells
- `categorical_accuracy`: accuracy over scored categorical gold-present cells
- `numeric_accuracy`: accuracy over scored numeric gold-present cells
- `text_accuracy`: accuracy over scored text gold-present cells under the resolved text scoring policy
- `proposal_coverage_on_gold_present`: fraction of gold-present cells with exactly one scoreable matched proposal

### Evidence metrics

Evidence metrics are separate from correctness.

- `anchor_valid_rate`: fraction of scored cells with at least one fully validated evidence anchor
- `correct_and_anchored_rate`: fraction of scored cells that are both correct and anchor-valid

### Diagnostic metrics

Diagnostics explain failure modes and contract problems. They are **not** headline accuracy penalties.

- `gold_present_cell_count`
- `gold_empty_cell_count`
- `filled_on_gold_empty_count`
- `missing_proposal_count`
- `duplicate_proposal_join_count`
- `cell_id_mismatch_count`
- `unmatched_proposal_count`
- `join_failure_count`
- `evidence_present_but_unvalidated_count`

## Headline vs diagnostic behavior

The evaluator keeps these concepts separate on purpose.

Headline correctness:

- `structured_accuracy`
- per-type structured accuracies
- `text_accuracy`
- `proposal_coverage_on_gold_present`

Evidence quality:

- `anchor_valid_rate`
- `correct_and_anchored_rate`

Diagnostics:

- gold-empty proposals
- join-key failures
- unmatched proposals
- evidence-present-but-unvalidated counts

This means:

- a cell can be correct but not anchor-valid
- a cell can be anchor-valid but incorrect
- a proposal on a gold-empty cell is not automatically a headline failure

## Example outputs

### Example `run_summary.json`

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

### Example `scored_cells.csv`

```text
record_kind,row_id,column_name,join_status,was_scored,is_correct,evidence_outcome
gold_cell,row-1,status,matched,True,True,anchor_valid
gold_cell,row-2,notes,matched,True,True,missing_evidence
```

### Example `runs_comparison.csv`

```text
run_id,structured_accuracy,text_accuracy,anchor_valid_rate,join_failure_count
run-a,1.0,1.0,0.3333333333333333,0
run-b,0.6666666666666666,0.5,0.0,0
```

## Error handling and contract hardening

The evaluator now fails early and explicitly for common operator mistakes, including:

- missing run bundle directories
- invalid `--runs-root` paths
- missing required run artifact files
- malformed JSON in run metadata, proposals, sidecar evidence, schema files, or summary files
- missing eval-mode provenance fields
- missing provenance snapshot artifacts
- unsupported gold file types
- empty gold CSV files
- missing required gold join fields
- duplicate gold join keys
- missing comparison-summary inputs for `compare`

The goal is to make failures obvious instead of silently guessing.

## Practical limitations

Current limitations:

- no GUI
- no multi-sheet XLSX scoring in one invocation
- no automatic fallback to hidden main-app join-key logic
- no `gold_in_document_rate` metric yet
- no structured-field support proxy metric yet
- no heavyweight entailment or faithfulness system
- no live LM Studio smoke test in the test suite; judge integration is covered through contract-level mocks

## Non-goals

This repo is not trying to:

- run extraction itself
- edit gold tables
- become a general benchmark platform
- replace deterministic scoring for structured fields with an opaque judge
- mix correctness and evidence into one hidden composite score

## Testing

The repository test suite covers:

- single-run evaluation
- batch evaluation
- expected output generation
- join-key failure behavior
- eval-mode provenance validation
- normalization and deterministic comparators
- evidence validation
- LM Studio judge adapter and text judge integration

Run the suite from the repo root after installing requirements:

```bash
python -m unittest discover -s tests -v
```
