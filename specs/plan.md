# Extract Structured Info from Papers Optimizer - plan.md

## Technical direction

The optimizer remains a small CLI-first orchestration service with strict role separation:

- main app executes extraction
- eval app scores run outputs
- optimizer coordinates candidate generation, launching, comparison, persistence, and summarization

## Implementation principles

- Keep orchestration logic explicit and inspectable.
- Keep candidate generation deterministic-first.
- Keep search space bounded and schema-validated.
- Keep candidate bundles immutable and hashable.
- Keep mode differences in control flow, not launch contracts.
- Keep results reproducible from filesystem artifacts.

## CLI architecture

Top-level commands:

- `paper-optimizer optimize --study-type {compare|optimize} --config <path> --out <dir>`
- `paper-optimizer evaluate-candidate --config <path> --candidate-file <path> --benchmark {smoke|dev|holdout} --out <dir>`
- `paper-optimizer validate-best --config <path> --experiment <dir> --out <dir>`
- `paper-optimizer summarize --config <path> --experiment <dir>`

Command dispatch lives in `paper_optimizer/cli.py`.

## Module map

- `settings.py`: config loading, path resolution, and schema validation.
- `benchmarks.py`: split mapping and benchmark-manifest validation.
- `search_space.py`: bounded search-space parsing and numeric-axis expansion.
- `bundle.py`: candidate objects, hashing, and immutable candidate manifest writes.
- `propose.py`: deterministic candidate proposal from bounded search space.
- `launch_main.py`: main-app launch and resolved-config snapshot management.
- `launch_eval.py`: eval-app launch and metric-group projection.
- `pipeline.py`: single-candidate orchestrated run (main then eval) with failure capture.
- `acceptance.py`: primary improvement and guardrail gate evaluation.
- `study.py`: compare/optimize orchestration, holdout validation, and summarize behavior.
- `results.py`: experiment manifests, result rows, summary files, and round summaries.
- `plotting.py`: static CSV + PNG outputs for compare and optimize views.
- `contracts.py`: typed records for candidate, launch result, candidate result, and round summary.

## Data flow

### compare flow

1. Load config, benchmarks, and compare candidates.
2. Materialize immutable candidate bundles.
3. Evaluate each candidate through shared pipeline.
4. Persist per-candidate rows and compare summary.
5. Rank by configured primary metric with deterministic tie handling.
6. Emit compare plots and winner record when available.

### optimize flow

1. Load config, benchmarks, and search space.
2. Evaluate baseline candidate as initial incumbent.
3. For each configured round:
   - propose deterministic bounded challengers
   - suppress duplicate signatures
   - evaluate challengers via shared pipeline
   - apply acceptance gates
   - optionally promote accepted best challenger
   - persist round summary and experiment summary
4. Emit optimize plots.

### holdout validation flow

1. Resolve holdout benchmark split.
2. Load experiment records.
3. Choose validation target set according to study type.
4. Re-evaluate selected candidates on holdout.
5. Persist holdout result artifacts to a separate output directory.

### summarize flow

1. Read experiment manifest.
2. Rebuild mode-appropriate static plots from saved `results.csv`.

## Integration contracts

### main-app launch contract

Main adapter writes candidate-owned files in `runs/<candidate_id>/main/`:

- `main_config_overlay.json`
- `resolved_main_config.json`
- `automation_result.json`

Main launch success requires machine-readable automation JSON with required run artifact references.

### eval-app launch contract

Eval adapter writes `eval_result.json` and consumes eval-produced per-run summary outputs.

Metric projection supports:

- grouped metrics already emitted by eval, or
- `metric_groups` mapping from flat eval metrics into optimizer `primary`, `guardrail`, and `diagnostic` groups

## Persistence contract

Experiment directory is canonical optimizer state.

Required persisted entities:

- experiment manifest
- candidate bundle manifests
- candidate-level CSV and JSONL records
- mode summary
- best-candidate state
- round summaries (optimize)
- static plot CSV/PNG artifacts

## Current architecture limits

- Confirmation reruns are not yet implemented.
- Deterministic pre-promotion artifact checks are partially implemented through pipeline success/failure status but not a separate explicit gate stage.
- Holdout selection in optimize currently ranks stored results by primary metric rather than reading promoted-incumbent lineage as the only source.

## Quality expectations

- Contract errors fail fast at setup or launch stages.
- Candidate failures remain visible as failed candidate rows.
- Summary/plot regeneration works from saved artifacts without rerunning main or eval.
