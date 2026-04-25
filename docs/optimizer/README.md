# Optimizer Documentation

The optimizer is an internal calibration and orchestration tool for bounded compare and optimize studies.

It is not the product surface. It exists to run development-time studies against the main app and eval tool.

## Purpose

- Load an optimizer config, benchmark manifests, and a bounded search space.
- Materialize immutable candidate bundles.
- Launch the main app and eval tool for each candidate.
- Apply acceptance gates in optimize mode.
- Persist experiment summaries, candidate records, plots, and reports.

Run optimizer commands from `tools/optimizer/`.

## Install

```bash
cd tools/optimizer
pip install -e .[dev]
```

## Study modes

The prepared optimizer app is organized around three operator workflows:

- compare models: fixed model candidate lists on the real dev or overnight benchmark
- optimize one model: focused `google/gemma-4-26b-a4b` sweeps, primarily `retrieval_top_k`, while holding the new retrieval defaults fixed
- overnight run: staged longer-running real-benchmark studies with incremental summaries

### compare

- evaluates an explicit fixed candidate set on the dev benchmark
- defaults to `compare.require_structured_output_for_extraction=true`, which marks candidates ineligible when provider probing reports `structured_output_mode="none"`
- supports explicit degraded experiments with `compare.allow_degraded_candidates=true`; those candidates stay labeled degraded-experimental in diagnostics
- produces ranked summaries and compare plots
- can optionally run holdout validation for top candidates

### optimize

- evaluates a baseline candidate first
- proposes bounded deterministic challengers round by round
- promotes challengers only when the primary metric and guardrails pass
- writes incumbent tracking, round summaries, plots, and reports

## CLI examples

```bash
paper-optimizer optimize --study-type compare --config config.example.json --out runs/compare
paper-optimizer optimize --study-type optimize --config config.example.json --out runs/optimize
paper-optimizer evaluate-candidate --config config.example.json --candidate-file candidate.json --benchmark dev --out runs/eval_one
paper-optimizer validate-best --config config.example.json --experiment runs/optimize --out runs/holdout
paper-optimizer summarize --config config.example.json --experiment runs/optimize
```

## Recommended monorepo layout

- repo root: this repository
- main app: `app/`
- eval tool: `tools/eval/`
- optimizer tool: `tools/optimizer/`

Prepared configs under `tools/optimizer/configs/` use monorepo-local relative paths.

The canonical compare and optimize paths use real benchmark manifests by default. Smoke and fixture-manual configs remain available only for fast contract checks or deeper manual fixture checks.

## Overnight workflow

The optimizer includes two main shell wrappers:

- `scripts/run_study.sh`: run one compare or optimize study, summarize it, and optionally validate holdout
- `scripts/run_overnight.sh`: run the recommended multi-stage overnight sequence

Prepared config families now separate canonical real-benchmark studies from smoke or fixture-manual checks:

- `compare_models.json`, `compare_prompts.json`, `compare_retrieval.json`, and `compare_retrieval_modes.json`: authoritative real-benchmark compare configs for meaningful development comparisons
- `compare_models_overnight.json` and `optimize_overnight.json`: canonical overnight configs
- `compare_models_fixture_manual.json`: fixture-backed compare config for deeper manual checks
- `compare_models_contract_smoke.json`: minimum smoke config for live contract checks

Real-benchmark manifests now fail preflight if they point at fixture assets, omit required dual-judge settings, or reference missing benchmark files.
Prepared configs now default `--judge-model-b` to `openai/gpt-oss-20b` so judge B is enabled by default without Gemma/Qwen coupling.

Model-compare and overnight candidate lists include:

- `openai/gpt-oss-20b`
- `google/gemma-4-e4b`
- `google/gemma-4-26b-a4b`
- `unsloth/gemma-4-26b-a4b-it`
- `qwen/qwen3.6-27b`
- `qwen/qwen3.6-35b-a3b`
- `unsloth/qwen3.6-35b-a3b`
- `zai-org/glm-4.6v-flash`

The operational default is `unsloth/gemma-4-26b-a4b-it`. `google/gemma-4-26b-a4b` remains the focused optimize-one-model target. The benchmark winner and operational recommendation stay separate report concepts when trust, runtime, or degradation caveats differ.

Reports surface dual-judge completion, disagreement, per-judge failures, evidence-anchor outcome counts, degraded or prompt-only status, and join failures directly in ranked candidate rows. High disagreement and judge-request failures now penalize ranking directly instead of staying report-only context. Degraded and unscored candidates remain ranked below healthy scored candidates.

Recommended study order:

1. `compare_models.json`
2. `compare_prompts.json`
3. `compare_retrieval.json`
4. `optimize_overnight.json`

## Artifact layout

Each experiment directory contains:

- `experiment.json`
- `summary.json`
- `best_candidate.json` when a winner or incumbent exists
- `results/results.csv`
- `results/results.jsonl`
- `rounds/round_<n>.json` for optimize mode
- `plots/*.csv`
- `plots/*.png`
- `runs/<candidate_id>/main/` launch artifacts
- `runs/<candidate_id>/eval/` launch artifacts
- `report.html`

Candidate diagnostics and reports now also surface:

- benchmark winner versus recommended default when trust caveats differ
- dual-judge completion, disagreement, unclear counts, and request failures
- prompt-only degraded runs and extraction-contract validity
- evidence grounding and anchor-audit summaries
- metadata-family failure signals and join failures
- runtime totals plus provider-request accounting

## Why this tool stays internal

The optimizer is intentionally orchestration-only:

- main app = execution and review product
- eval tool = scoring and benchmarking
- optimizer = orchestration, candidate tracking, and decision reporting

This keeps product behavior, scoring behavior, and study orchestration separate without introducing a large shared runtime package.

## Related docs

- Main app docs: [../main-app/README.md](../main-app/README.md)
- Eval docs: [../eval/README.md](../eval/README.md)
- Contract surfaces: [../contracts/tool-contract-surfaces.md](../contracts/tool-contract-surfaces.md)
