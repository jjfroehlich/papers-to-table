# Optimizer

Optimizer is an orchestration tool for testing and comparing different models, prompts, and config parameters. It launches main-app runs, launches eval on the resulting run bundles, then writes experiment reports.

![Optimizer orchestration and Eval workflow](../diagrams/refined_svg/03_orchestrator_eval_benchmark_refined.svg)

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
- Treat compare-models as an overnight run. It can take 10+ hrs with 11 models and 6 external/control baselines.

```bash
python scripts/papers_to_table.py optimizer compare-models
```

Options:
- `--help`: help
- `--label LABEL`: choose the run label instead of the timestamped default. 
- `--initial-model MODEL_ID`: run a model comparison using the `tools/optimizer/configs/compare_models.json`, but restrict it to one text model. 

Optimizer compares local models, and includes external-results, positive- and negative controls in the eval and reports.

<img src="../plots/20260615_004637_compare_models_plots_v2/20260615_004637_compare_models_plots_v2_scores_of_all_candidates.jpg" alt="Scores for all local-model candidates, Codex baselines, failed local-agent attempts, and positive and negative controls" class="figure-wide" width="92%" />

*Content-correctness [Eval scores](eval.md) for optimizer run `20260615_004637_compare_models`. Gray points are replicate scores, blue lines are medians, black lines are means, and the numbers above the boxes give those means to one decimal percentage point. “Failed” marks configurations without a complete scorable result. The positive control is gold data; the within-field word-shuffle and cross-field controls were added on 2026-07-10 to calibrate score sensitivity and are excluded from winner selection.*


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
- the routine preset is bounded: broad model compare, two prompt candidates, two retrieval candidates, and three extraction-feature candidates from the top retrieval seed
- model-specific request settings are inherited from `app/backend/src/backend/app/model_profiles/default_profiles.json` unless a future config deliberately sweeps model settings
- Python command delegates to `tools/optimizer/scripts/full_benchmark.sh`
- model phase uses `tools/optimizer/configs/compare_models.json`
- prompt phase materializes `compare_prompts.json` with the model-phase winner and compares `default` against `checklist_guided`
- retrieval-parameter phase materializes `compare_retrieval_parameters.json` with the prompt-phase winner and compares `hybrid_experimental` top-k 8 against `lexical` top-k 12
- extraction-feature phase materializes `compare_extraction_features.json` from the top retrieval-parameter candidate and compares three recall-rescue-enabled feature combinations
- Full benchmark runtime scales roughly as: `candidate count x benchmark count x replicate count x model speed`. A single candidate costs about `1 - 3 h`, depending on model speed and feature settings. 

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

Optimizer exposes the accuracy-runtime trade-off: among the tested local models, longer runtime did not consistently produce a higher average score.

<img src="../plots/20260615_004637_compare_models_plots_v2/20260615_004637_compare_models_plots_v2_score_vs_runtime.jpg" alt="Average benchmark score plotted against runtime for local papers-to-table models and Codex baselines" class="figure-half" width="50%" />

*Average content-correctness [Eval score](eval.md) versus wall-clock runtime for 15 papers, 31 target columns, and three replicates in optimizer run `20260615_004637_compare_models`. Local-model timings were measured on the benchmark workstation documented below; the pale Codex points are external GPT-5.5 xhigh baselines and should not be interpreted as locally measured model runtimes.*

The real-world runtimes below were measured on the project's development and benchmarking workstation. This environment snapshot was captured on 2026-07-10; software and driver versions may differ from older runs.

| Component | Specification |
|---|---|
| Operating system | Windows 11 Pro 64-bit, build 26200 |
| CPU | AMD Ryzen 9 5950X, 16 cores / 32 threads |
| Memory | 32 GB RAM |
| GPU | NVIDIA GeForce RTX 3090, 24 GB VRAM |
| NVIDIA driver | 591.86 |
| Repository and benchmark-data storage | `D:` on a TOSHIBA HDWD220 2 TB SATA HDD, NTFS |

The checked-in routine full-benchmark preset now uses this bounded phase size:

| Stage | Routine Candidates | Notes |
|---|---:|---|
| model compare | 11 | Keeps the current model shortlist. |
| prompt compare | 2 | `default` versus `checklist_guided`; `context_balanced` is excluded from the routine preset. |
| retrieval compare | 2 | `hybrid_experimental` top-k 8 and `lexical` top-k 12 only. |
| extraction feature compare | 3 | Top retrieval seed only; all candidates keep `recall_rescue_enabled=true`. |

The 2026-05-15 full-benchmark attempt was broader and should be treated as a cautionary reference, not the current routine preset:

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

Benchmarks can include precomputed filled tables from external software. Optimizer scores them with Eval before the internal candidates and includes them in `results/results.csv`, plots, and the HTML report as external baseline rows. Set a short <40 char `candidate_id` for each external result to avoid long paths that may exceed operating system limits.

The canonical model comparison currently includes six external/control baselines: three completed external-agent systems, the gold positive control, and two deterministic gold-derived negative controls. All six use the same Eval path but are excluded from winner selection, recommendation rationale, and benchmark-best plots.

- `ext_gold_word_shuffle` is a weak order-sensitivity control. It shuffles whitespace-delimited words within each non-empty target cell; single-token and otherwise unshufflable cells remain unchanged.
- `ext_gold_cross_field` is a strong score-floor control. It reassigns whole non-empty values across target rows and columns and guarantees that no non-empty target cell retains its original gold value. It intentionally mixes field types and is not intended to resemble a realistic extraction system.

Regenerate the checked-in controls, or verify that they still match their gold sources and algorithm:

```bash
python tools/optimizer/scripts/generate_negative_controls.py
python tools/optimizer/scripts/generate_negative_controls.py --check
```

```json
"external_results": [
  {
    "label": "external_tool_v1",
    "candidate_id": "ext_tool_v1",
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
3. Launch main-app extraction: start a headless/eval-mode main-app run for that candidate and benchmark. This run parses PDFs, matches rows, retrieves evidence, produces canonical proposal records, runs optional figure review, and writes the run bundle.
4. Validate main-app output: confirm the expected run reference, run directory, `run.json`, config snapshot, summaries, and proposal artifacts exist.
5. Launch eval: pass the completed run bundle to eval. Eval scores structured fields and explicit deterministic text overrides first, then sends judge-backed text cells to one or two judge language models; normalized exact text matches are judged by default unless a benchmark passes `--enable-text-exact-match-fast-path` through `eval_args`. In dual-judge mode, both judges' per-cell records are preserved and disagreement is reported as a trust signal.
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
- capability-use diagnostics when exposed by run bundles, including canonical typed retrieval scoring metadata, prepared retrieval index source counts, figure planner skip reasons, accepted figure hits, dropped/no-hit figure reasons, recovery use, and whole-document use

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
- content-correctness replicate distribution: boxplots retain individual replicate points, label each mean above the highest plotted replicate, and start the y-axis at zero; other primary metrics keep automatic scaling

### Regenerate The Published 2026-06-15 Boxplots

The documentation's percentage-scale boxplots are reproducible from the historical run's persisted replicate-distribution CSV. From the repository root:

```bash
python tools/optimizer/scripts/render_compare_model_docs_plots.py \
  --input-csv tools/optimizer/runs/20260615_004637_compare_models/compare/experiment/plots/suite_replicate_score_distribution.csv \
  --output-dir docs/plots/20260615_004637_compare_models_plots_v2
```

These published views show means to one decimal percentage point. Normal optimizer report plots retain the metric's native 0–1 scale and show two decimals.
