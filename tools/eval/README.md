# Eval Tool

## Purpose
Score main-app run bundles against gold data without importing main-app runtime internals.

## When to use
- run-bundle quality checks
- benchmark comparisons across runs/models
- evidence/cell-level scoring audits

## Canonical command (repo root)
```bash
python scripts/papers_to_table.py eval --run /abs/run --gold /abs/gold.csv --schema /abs/schema.json --out /abs/eval_out
```

## Native command (tool-local)
```bash
cd tools/eval
python -m paper_eval evaluate --run /abs/run --gold /abs/gold.csv --schema /abs/schema.json --out /abs/eval_out
```

## Inputs
- run bundle directory (`run.json`, `proposals/proposals.jsonl` minimum)
- gold table (csv/xlsx)
- optional eval schema

## Outputs
- summary metrics
- per-cell outputs
- compare artifacts when batch mode is used

## Test command
```bash
bash scripts/test-eval-tool.sh
```

## Common failure modes
- missing run artifacts (`run.json`, `proposals/proposals.jsonl`)
- unsupported artifact schema version
- invalid gold/schema JSON/CSV shape
- judge endpoint/model unavailable for semantic judge paths

## Run-bundle relationship
Eval is a consumer of main-app contracts; it does not create or mutate run bundles.

## Reproducibility notes
Use fixed judge model IDs and API bases for benchmark reproducibility. Wrapper exposes common judge model flags; advanced judge transport flags remain native-tool options.
