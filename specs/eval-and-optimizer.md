# Eval And Optimizer

- Status: Canonical focused spec
- Owner: Companion Tools
- Depends on: `spec.md`, `architecture.md`, `contracts.md`
- Consumed by: `tools/eval/`, `tools/optimizer/`, docs, tests

## Purpose

This file owns the eval and optimizer companion-tool behavior. Eval scores persisted outputs; optimizer orchestrates bounded studies. Neither tool is a second extraction product.

## Eval Role

Eval is a CLI-first, file-driven companion. It reads run bundles or external filled tables from disk, scores them against gold data, and writes inspectable per-cell, per-run, and comparison artifacts.

Eval must:

- remain a separate runtime from the main app
- read run bundles from files alone
- keep correctness metrics separate from evidence metrics
- keep deterministic structured scoring separate from judge-backed text scoring
- expose deterministic structured failure diagnostics before adding any structured judge adjudication
- preserve join failures and missing proposals explicitly
- write filesystem artifacts as the canonical output surface

## Eval Inputs And Outputs

Eval consumes:

- one or more main-app run bundles, or an external filled table
- a gold CSV or XLSX table
- optional eval schema JSON for field typing, aliases, tolerances, and text-scoring overrides
- optional judge model/provider arguments

Eval writes:

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

Comparison artifacts may be rebuilt from existing summaries.

## Eval Execution Phases

1. Load and validate the run bundle, proposals, gold table, optional eval schema, and run metadata.
2. Join proposals to gold cells by stable row and column identity.
3. Resolve field types from proposal metadata, eval schema, or inference. Accepted canonical field types are `boolean`, `categorical`, `numeric`, and `text`; aliases such as `number`, `bool`, `enum`, and `free_text` canonicalize to those values. Unknown non-empty field types fail with a contract error.
4. Score deterministic fields first: numeric, boolean, categorical, date-like, and text fields with explicit deterministic policy.
5. For deterministic structured failures, preserve `deterministic_failure_kind` and `adjudication_eligible` diagnostics without changing the deterministic score.
6. Collect judge-backed text cells into a pending queue, including normalized exact text matches by default.
7. Run judge-major batches grouped by judge label, provider, model, and settings.
8. Merge per-judge verdicts, disagreement state, evidence checks, and deterministic scores into scored cells.
9. Aggregate per-run summaries and comparison files.

Low-level eval may opt into the deterministic text exact-match fast path with `--enable-text-exact-match-fast-path`; default real benchmark scoring judges text cells, including normalized exact matches.

Field-type inference must not treat bare `0`/`1` numeric pairs as boolean. Allowed values infer `categorical`; pairs where both values parse numerically infer `numeric`; boolean is inferred only for clear boolean vocabulary such as `yes/no`, `present/absent`, or `true/false`; otherwise the field is treated as `text`.

Structured fields remain deterministic-only in the current implementation. Numeric, categorical, and boolean comparisons emit parse and mismatch diagnostics in normal eval outputs. The summary includes `structured_deterministic_failure_count`, `structured_adjudication_eligible_count`, `structured_adjudication_eligible_failure_rate`, and the older compatibility alias `structured_adjudication_eligible_rate`; these are diagnostic counts and do not change headline correctness.

## Judge Policy

LM Studio is the default local-first judge path. Real benchmark evaluation should use two judges by default when available:

- `judge_a=google/gemma-4-26b-a4b`
- `judge_b=openai/gpt-oss-20b`

Dual-judge scoring must preserve per-judge records and expose disagreement metrics. Judge failures on one cell must not abort an otherwise valid evaluation run; they become explicit unscored or failure diagnostics.

Eval judge execution is judge-major: prepare all eligible text-cell requests, execute all `judge_a` work, execute all `judge_b` work, group batches by effective provider/model/settings, then merge results back into deterministic scored-cell order.

Structured judge adjudication is intentionally deferred. It must not be added as a default path unless normal eval diagnostics show that deterministic structured false negatives are common enough to affect benchmark or optimizer ranking quality.

## Benchmark Dataset Policy

The current curated benchmark corpus lives at repository root under `benchmark_datasets/`.

Active benchmark datasets:

- `massively_parallel_reporter_assays`
- `genome_editing_tools`
- `spatial_transcriptomics`

Each active dataset contains:

- `table_template.csv`
- `schema.csv`
- `table_gold.csv`
- `pdfs/`

External result and positive-control comparison tables live under `benchmark_datasets/data/`, currently including:

- `20260517_ext_codex`
- `20260517_ext_kitchin`
- `20260517_ext_agentkit`
- `20260517_gold`

Optimizer benchmark ids for the active datasets are:

- `bench_massively_parallel_reporter_assays`
- `bench_genome_editing`
- `bench_spatial_transcriptomics`

`bench_smoke` is a fixture/contract-check manifest, not benchmark evidence.

## Optimizer Role

Optimizer is orchestration-only. It does not extract values and does not judge values itself. It launches main-app extraction, launches eval on completed outputs, validates contracts, aggregates results, and reports recommendations.

Optimizer must:

- load explicit JSON presets
- materialize candidate bundles and config overlays
- keep compare and optimize workflows distinct
- treat real benchmark presets differently from fixture and smoke presets
- preserve interrupted-study truth on disk
- distinguish raw winners from recommended defaults
- surface trust caveats rather than hiding them behind one scalar score

## Optimizer Workflows

Primary wrapper workflows:

- `python scripts/papers_to_table.py optimizer compare-models`
- `python scripts/papers_to_table.py optimizer dev-check`
- `python scripts/papers_to_table.py optimizer full-benchmark`

`compare-models` ranks a fixed model list on the current three-dataset dev suite in triplicate and includes external baselines and the gold positive control when configured. The current shortlist includes both `google/gemma-4-e4b` and `google/gemma-4-12b` alongside the other configured local candidates.

`dev-check` is the fast development signal. It materializes a run-local config from `compare_models.json`, removes external-result scoring, runs one model, one benchmark, and one replicate, and defaults to `google/gemma-4-e4b` on `bench_genome_editing`.

`full-benchmark` runs phased model, prompt, retrieval-parameter, and extraction-feature studies. Runtime scales by candidate count x benchmark count x replicate count x model speed.

## Suite And Replicate Semantics

Optimizer execution is:

```text
candidate x suite x benchmark x replicate
```

A one-benchmark run is represented as a one-benchmark suite with `replicates.count = 1`.

`smoke`, `dev`, and `holdout` may remain convenience aliases in configs, but runtime execution resolves them into explicit suites such as `smoke_suite`, `dev_suite`, and `holdout_suite`.

Replicate rows must preserve candidate id, benchmark id, suite id, replicate index, score status, candidate status, metrics, runtime, trust diagnostics, and nested artifact references.

Failed, unscored, and degraded replicates remain visible and must not be averaged away silently. A single replicate is valid but reports `n=1` or equivalent low-replicate caveats.

## Optimizer Execution Phases

1. Resolve study preset, selected suite, benchmarks, replicates, candidates, and search space.
2. Materialize a candidate bundle and resolved app config overlay.
3. Launch the main app in headless/eval mode for one candidate x benchmark x replicate.
4. Wait for proposal generation, final summaries, and readable run-bundle contract artifacts.
5. Validate the main-app launch contract.
6. Launch eval against the completed run bundle.
7. Validate eval summary and comparison artifacts.
8. Write candidate result rows with nested main-app and eval references.
9. Aggregate replicate, benchmark, suite, and study summaries.
10. Rank raw winners, apply trust caveats, and write reports, plots, and recommended-default metadata.

Optimizer is sequential by default. Future parallel mode must be explicit and must preserve LM Studio locking and model-residency safety.

## Reports, Plots, And Trust Caveats

Optimizer reports must make these questions answerable:

- which candidate led at suite level
- which benchmark drove the suite result
- whether results were stable across replicates
- whether error bars or low replicate count weaken the ranking
- whether degraded mode, judge disagreement, missing evidence, failed replicates, or contract invalidity weaken the recommendation

Reports and plots must distinguish raw winner from recommended default when trust caveats differ. Candidate-level, benchmark-level, suite-level, replicate-level, and run-level artifacts are all relevant when present.

Capability-use reporting should include text and vision calls, retrieval typed scoring context, prepared retrieval index source counts, figure planner attempts/success/skips/fallbacks, planner skip reasons/confidence, figure-review attempts/success/failure/suppression, successful vision calls without usable hits, dropped/no-hit reasons, accepted figure hits, figure-derived evidence count, candidate-selection attempts/value changes, recall-rescue eligibility/use/skips, and whole-document eligibility/use/skips when run stats expose them.

## Canonical Presets

Current canonical optimizer presets:

- `tools/optimizer/configs/compare_models.json`
- `tools/optimizer/configs/compare_prompts.json`
- `tools/optimizer/configs/compare_retrieval_parameters.json`
- `tools/optimizer/configs/compare_extraction_features.json`

No `optimize_parameter_sweeps.json` preset is currently checked in. If a sweep preset is restored or renamed, update this spec and the docs in the same pass.

Smoke and fixture-manual configs are explicitly non-canonical benchmark evidence.
