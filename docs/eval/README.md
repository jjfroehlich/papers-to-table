# Eval Tool Documentation

The eval tool is an internal benchmarking and scoring utility for run bundles produced by the main app.

It is not the primary product surface. It exists to score runs, compare experiments, and support development-time benchmarking.

## Purpose

- Load one or more run bundles.
- Compare proposals against a human-filled gold table.
- Write per-cell, per-run, and cross-run comparison artifacts.

Run eval commands from `tools/eval/`.

## Install

```bash
cd tools/eval
python -m pip install -r requirements.txt
```

## Inputs

You need:

1. one `--run`, repeated `--run`, or one `--runs-root`
2. one gold CSV or XLSX file
3. an optional schema JSON file for explicit field types, aliases, numeric tolerances, or text-scoring overrides

Required run artifacts:

- `run.json`
- `proposals/proposals.jsonl`

Required published join fields:

- `row_id`
- `column_name`
- `cell_id`

Evidence can be linked either through nested `support.evidence_ids` or through top-level main-app fields: `primary_evidence_id`, `evidence_ids`, and `ordered_supporting_evidence_ids`. Eval resolves those IDs against persisted evidence files and parsed page text before scoring anchors.

## Commands

### Evaluate one run

```bash
python -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --judge-model google/gemma-4-26b-a4b \
  --judge-model-b openai/gpt-oss-20b \
  --out out/example-single
```

### Evaluate many runs

```bash
python -m paper_eval evaluate \
  --runs-root tests/fixtures/example_eval/runs \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --judge-model google/gemma-4-26b-a4b \
  --judge-model-b openai/gpt-oss-20b \
  --out out/example-batch
```

### Rebuild comparison outputs

```bash
python -m paper_eval compare \
  --summaries out/example-batch/per-run \
  --out out/example-batch/compare-rebuilt
```

## Output layout

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

## Scoring behavior

- structured fields stay deterministic where possible
- text fields can use judge-backed scoring when deterministic exact matching is insufficient
- correctness and evidence are tracked separately
- headline metrics default to content cells rather than inflating scores with metadata-only fields
- metadata-family summaries are emitted per run so metadata-lane parser gaps, retrieval misses, evidence ambiguity, and judge failures stay inspectable
- evidence anchor audits now emit evidence-item totals, validated-versus-unvalidated counts, missing-evidence counts, anchor-invalid counts, outcome counts, and reason histograms including invalid pages, missing quote text, page out of bounds, no persisted text, quote not locatable, normalized quote located, and raw quote located

## Judge behavior

LM Studio is only required when a text field cannot be resolved by deterministic exact-match scoring and needs judge-backed text scoring.

Eval uses the same bounded structured-output fallback ladder as the main app:

- `json_schema`
- `json_object`
- prompt-only JSON mode with app-side parsing

Real benchmark studies should use two judges. Per-run summaries and comparison rows now preserve:

- `correctness_judge_a` and `correctness_judge_b`
- disagreement count and rate
- judge-a versus judge-b correctness delta
- judge-specific unclear and request-failure counts
- judge response-mode summaries

Dual-judge execution is judge-major by default: eval prepares all eligible text-cell requests, runs all `judge_a` batches, then all `judge_b` batches, grouped by effective provider/model/settings, and merges results back into the original deterministic cell order. If judge B fails, judge A records remain usable. Per-run summaries include `judge_execution_summary` with batch counts, eligible counts, runtimes, execution order, model-switch diagnostics, and judge cleanup failures when LM Studio cleanup could not be completed cleanly.

Eval now enforces range invariants for ratio metrics. Coverage-style metrics must stay within `[0, 1]`; impossible values are treated as implementation defects rather than silently published.

## Why this tool stays separate from the product surface

Keeping benchmarking separate from the main app:

- avoids benchmarking dependencies in the operator-facing app runtime
- keeps the run bundle an explicit published contract
- makes scoring outputs independently inspectable
- keeps benchmarking optional for operators who only need the main app

## Related docs

- Main app docs: [../main-app/README.md](../main-app/README.md)
- Optimizer docs: [../optimizer/README.md](../optimizer/README.md)
- Contract surfaces: [../contracts/tool-contract-surfaces.md](../contracts/tool-contract-surfaces.md)
