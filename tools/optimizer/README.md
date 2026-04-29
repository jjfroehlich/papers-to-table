# Optimizer Tool

## Purpose
Orchestrate repeated main-app + eval experiments (compare and optimize studies).

## When to use
- compare model/prompt/retrieval candidates
- tune one model within bounded search spaces
- run overnight multi-stage studies

## Canonical commands (repo root)
```bash
python scripts/papers_to_table.py optimizer compare-models
python scripts/papers_to_table.py optimizer optimize-one-model
python scripts/papers_to_table.py optimizer overnight
```

## Native command (tool-local)
```bash
cd tools/optimizer
python -m paper_optimizer.cli optimize --study-type compare --config configs/compare_models.json --out runs/compare_out
```

## Key inputs
- optimizer config preset (`tools/optimizer/configs/*.json`)
- benchmark manifest paths (table/schema/pdf_dir/gold)
- candidate definitions and optional search spaces

## Key outputs
- study-level summary artifacts
- per-candidate run/eval outputs
- recommended winner/default diagnostics

## Test command
```bash
bash scripts/test-optimizer-tool.sh
```

## Common failure modes
- missing backend/eval deps
- unresolved fixture paths in config
- failed preflight/provider readiness during candidate runs
- eval failure cascading into study failure

## Relationship to run bundles
Optimizer orchestrates main-app runs and eval scoring; it does not reimplement extraction or scoring logic.

## Reproducibility notes
Keep configs checked-in, pin candidate IDs/models, and preserve output directories for audit trails.
