# Optimizer

Optimizer is an orchestration tool for testing and comparing different models, prompts, and config parameters. It launches main-app runs, launches eval on the resulting run bundles, then writes experiment reports.

## What It Is For

Use optimizer when you need to answer questions like:

- which model should be the current default?
- which prompt bundle performs best?
- which retrieval settings are safest to recommend?
- dev-check: how does the current app version perform?

## Install
The main installation command will have this installed already. It is from the repository root:

```bash
python scripts/papers_to_table.py install
```

Alternative low-level install:

```bash
cd tools/optimizer
python -m pip install -e .[dev]
```

Test command:
```bash
bash scripts/test-optimizer-tool.sh
```

## Recommended Commands

### Compare Models
- use it to choose among fixed list of models
- fixed candidate list
- on current three-dataset benchmark suite
- done in triplicate to measure variability
- same prompt package, retrieval parameters, and extraction features
- model-specific request settings come from `app/backend/src/backend/app/model_profiles/default_profiles.json`; one can add optimizer knobs to compare model-settings such as temperature/top-p/chat-templates.
- Python command delegates to `tools/optimizer/scripts/compare_models.sh`
- uses `tools/optimizer/configs/compare_models.json`
- Treat compare-models as an overnight run. It can take 10 hrs with 5 models and 2 external results.

```bash
python scripts/papers_to_table.py optimizer compare-models
```

Options:
- `--help`: help
- `--label LABEL`: choose the run label instead of the timestamped default. 
- `--initial-model MODEL_ID`: run a model comparison using the `tools/optimizer/configs/compare_models.json`, but restrict it to one text model. 


### Development Check
- use during implementation to get one fast correctness/runtime signal
- uses the same candidate settings as the canonical model-compare preset
- runs one model, one benchmark, and one replicate
- removes external-result scoring from the run-local config so the report reflects only the app candidate
- defaults to `google/gemma-4-e4b` on `bench_genome_editing`
- writes only run-local materialized config files; checked-in optimizer configs are unchanged

```bash
python scripts/papers_to_table.py optimizer dev-check
python scripts/papers_to_table.py optimizer dev-check --label dev_check_after_parser_fix
```

Options:
- `--help`: help
- `--label LABEL`: choose the run directory label under `tools/optimizer/runs`.
- `--model MODEL_ID`: choose the configured model id. Defaults to `google/gemma-4-e4b`.
- `--benchmark-id BENCHMARK_ID`: choose one benchmark dataset. Defaults to `bench_genome_editing`, which has a useful mix of retrieval-heavy method fields and clear figure-dependent fields such as architecture figures and Figure 3 bar-chart counting.


### Full Benchmark
- use when you want a broad end-to-end tuning pass rather than only model selection
- compare models first, then compare prompt packages, retrieval parameters, and extraction feature toggles
- each phase runs in triplicate on the current three-dataset dev suite
- model-specific request settings are inherited from `app/backend/src/backend/app/model_profiles/default_profiles.json` unless a future config deliberately sweeps model settings
- Python command delegates to `tools/optimizer/scripts/full_benchmark.sh`
- model phase uses `tools/optimizer/configs/compare_models.json`
- prompt phase materializes `compare_prompts.json` with the model-phase winner
- retrieval-parameter phase materializes `compare_retrieval_parameters.json` with the prompt-phase winner
- extraction-feature phase materializes `compare_extraction_features.json` from the top retrieval-parameter candidates
- Full benchmark runtime scales roughly as: `candidate count x benchmark count x replicate count x model speed`. A single candidate costs about `1 - 3 h`, depending on model speed and feature settings. A broad full benchmark with dozens of candidates can take `2-4+ days`.

```bash
python scripts/papers_to_table.py optimizer full-benchmark
python scripts/papers_to_table.py optimizer full-benchmark --initial-model google/gemma-4-e4b
python scripts/papers_to_table.py optimizer full-benchmark --resume tools/optimizer/runs/<run_id>/overnight_manifest.json
```

Options:
- `--help`: help
- `--label LABEL`: choose the full-benchmark run label instead of the timestamped default. 
- `--initial-model MODEL_ID`: Run a full benchmark using the model-compare config, but restrict it to one text model. Later phases still use the model-phase winner in the usual sequence, so this only shortens the first model-compare phase. 
- `--resume PATH`: resume from an existing full-benchmark `overnight_manifest.json`. Resume skips stages already recorded in the manifest and, for the currently active compare stage, reuses completed candidate rows from `experiment/results/results.jsonl`.

## Runtimes

Real world data below, three-benchmark suite with three replicates, with machine `Geforce RTX3090 24GB, 32GB RAM, AMD Ryzen 9 5959X 16-core processor, Win 64x`:

| Stage | Completed Candidates | Completed Runtime | Mean Runtime Per Candidate |
|---|---:|---:|---:|
| model compare | 9 | 12.45 h | 83 min |
| prompt compare | 3 | 6.25 h | 125 min |
| retrieval sweep | 10 | 22.54 h | 135 min |
| extraction feature sweep | 4 | 8.64 h | 130 min |

`20260515_142227_full_benchmark_full_benchmark_20260515-142227`

| Stage |____________________________________________| Runtime Per Candidate |
|---|---:|---:|
| model compare openai/gpt-oss-20b || 48 min |
| model compare google/gemma-4-e4b || 76 min |
| model compare qwen/qwen3.6-27b || 204 min |

`20260524_020807_compare_models`

## Canonical Presets

These are the experiment templates. Each preset is focused on one comparison question. 

- `tools/optimizer/configs/compare_models.json`
- `tools/optimizer/configs/compare_prompts.json`
- `tools/optimizer/configs/compare_retrieval_parameters.json`
- `tools/optimizer/configs/compare_extraction_features.json`

## Config Structure

Optimizer uses explicit JSON presets under `tools/optimizer/configs/`. 

Common config areas:

- `baseline_candidate`
- `compare_candidates`
- `search_space`
- `benchmarks`
- `main_app`
- `eval_app`
- `acceptance`
- `compare`
- `benchmark_suites` (optional)
- `replicates` (optional)

## Benchmark Datasets And Replicates

There are three checked-in benchmark datasets:
- `bench_massively_parallel_reporter_assays`
- `bench_genome_editing`
- `bench_spatial_transcriptomics`

Regular optimizer runs, such as `compare-models` and `full-benchmark`, use the three benchmark datasets and 3 replicates. 
A simple run is on one benchmark dataset with 1 replicate, for example used by `dev-check`. 

## External Result Baselines

Benchmarks can include precomputed filled tables from external software. Optimizer scores them with Eval before the internal candidates and includes them in `results/results.csv`, plots, and the HTML report as `external_{label}` rows.

```json
"external_results": [
  {
    "label": "external_tool_v1",
    "system": "external-tool",
    "replicates": [
      {"replicate_index": 1, "path": "../../../benchmark_datasets/data/external_tool_v1/rep1/mpra_filled.csv"},
      {"replicate_index": 2, "path": "../../../benchmark_datasets/data/external_tool_v1/rep2/mpra_filled.csv"},
      {"replicate_index": 3, "path": "../../../benchmark_datasets/data/external_tool_v1/rep3/mpra_filled.csv"}
    ]
  }
]
```

External runtimes are optional. When available, add `runtime_seconds` to each replicate or place a `runtimes.json`/`runtime.json` file beside the external result directory. For runs that produced every benchmark table in one wall-clock session, use `runtime_scope: "suite_replicate"` so suite summaries count each replicate runtime once instead of once per benchmark.

```json
{
  "runtime_scope": "suite_replicate",
  "unit": "seconds",
  "replicates": [
    {"replicate_index": 1, "runtime_seconds": 1179},
    {"replicate_index": 2, "runtime_seconds": 912},
    {"replicate_index": 3, "runtime_seconds": 941}
  ]
}
```

## Execution Phases

Optimizer is orchestration-only. It does not extract values itself and it does not judge values itself. For every internal candidate x benchmark x replicate, it runs the same ordered phases:

1. Resolve study config: load the preset, selected suite, benchmark manifests, replicate count, candidates, and search space.
2. Materialize candidate bundle: write the candidate manifest and resolved config overlays for that candidate.
3. Launch main-app extraction: start a headless/eval-mode main-app run for that candidate and benchmark. This run parses PDFs, matches rows, retrieves evidence, produces proposals, runs optional figure review, and writes the run bundle.
4. Validate main-app output: confirm the expected run reference, run directory, `run.json`, config snapshot, summaries, and proposal artifacts exist.
5. Launch eval: pass the completed run bundle to eval. Eval then performs its own deterministic scoring phase followed by scoring with one or two judge language models. In dual-judge mode, both judges' per-cell records are preserved and disagreement is reported as a trust signal.
6. Validate eval output: confirm eval summary and expected per-run artifacts satisfy the optimizer contract.
7. Record candidate result: merge main-app runtime metadata, eval metrics, diagnostics, warnings, and artifact references into candidate result rows.
8. Aggregate replicates and suites: summarize candidate x benchmark, candidate x suite, and study-level results.
9. Rank and recommend: rank raw results, apply guardrails and trust caveats, then write `best_candidate.json`, `summary.json`, plots, and `report.html`.


## Outputs
### Overview
- study-level summary artifacts
- per-candidate run/eval outputs
- optional external-result baselines scored by Eval and shown beside internal candidates
- recommended winner/default diagnostics

### How Outputs Are Organized

Each experiment writes an experiment directory with:

- `report.html` HTML report with charts, scores, and the summary
- `experiment.json` resolved experiment config and preset
- `summary.json` compact status summary and winner metadata
- `best_candidate.json` winner record, when one exists
- `results/results.csv` tabular candidate results
- `results/results.jsonl` candidate results with nested detail
- `results/replicate_results.csv` and `results/replicate_results.jsonl` in suite or replicate mode
- `results/benchmark_summary.csv` and `results/benchmark_summary.json` in suite or replicate mode
- `results/suite_summary.csv` and `results/suite_summary.json` in suite mode
- `runs/{candidate_id}/main/` main-app run bundle for that candidate
- `runs/{candidate_id}/eval/` eval run bundle for that candidate
- `plots/` generated comparison charts

### How To Interpret Html Reports

- winner: best benchmark result under the scoring and acceptance rules
- recommended default: operational recommendation after trust, degraded-mode, evidence, or runtime caveats are considered
- degraded candidate: a candidate that ran with capability degradation or contract caveats and should not be treated like a healthy peer