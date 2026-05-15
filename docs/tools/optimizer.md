# Optimizer

Optimizer is an orchestration tool for testing and comparing different models, prompts, and config parameters. It launches main-app runs, launches eval on the resulting run bundles, then writes experiment reports.

## What It Is For

Use optimizer when you need to answer questions like:

- which model should be the current default?
- which prompt bundle performs best?
- which retrieval settings are safest to recommend?

## Install
The main installation command will have this installed already. 
From the repository root:

```bash
python scripts/papers_to_table.py install
```

Low-level install:

```bash
cd tools/optimizer
python -m pip install -e .[dev]
```

## Test command
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
- estimated runtime: average 50 minutes per model for all three benchmark datasets in triplicate (May 14, 2026 compare run)
- Python command delegates to `tools/optimizer/scripts/compare_models.sh`
- uses `tools/optimizer/configs/compare_models.json`

```bash
python scripts/papers_to_table.py optimizer compare-models
```

### Full Benchmark
- use when you want a broad end-to-end tuning pass rather than only model selection
- compare models first, then compare prompt packages, retrieval parameters, extraction feature toggles, and finally run a minimal parameter-sweep stub
- each phase runs in triplicate on the current three-dataset dev suite
- model-specific request settings are inherited from `app/backend/src/backend/app/model_profiles/default_profiles.json` unless a future config deliberately sweeps model settings
- Python command delegates to `tools/optimizer/scripts/full_benchmark.sh`
- model phase uses `tools/optimizer/configs/compare_models.json`
- prompt phase materializes `compare_prompts.json` with the model-phase winner
- retrieval-parameter phase materializes `compare_retrieval_parameters.json` with the prompt-phase winner
- extraction-feature phase materializes `compare_extraction_features.json` from the top retrieval-parameter candidates
- final parameter-sweep phase materializes `optimize_parameter_sweeps.json` with the extraction-feature winner. Current parameter sweep is just a small proof of principle (`retrieval_top_k`: `12`, `14`), can be expanded in the future. 

```bash
python scripts/papers_to_table.py optimizer full-benchmark
```

Runtime estimate calculation:

```text
May 14, 2026 observed mean: ~0.82 h per candidate for all 3 datasets in triplicate
model comparison:       9 candidates  * 0.82 h =  7.38 h
prompt comparison:      3 candidates  * 0.82 h =  2.46 h
retrieval parameters:  10 candidates  * 0.82 h =  8.20 h
extraction features:   16 candidates  * 0.82 h = 13.12 h
parameter sweep stub:   2-3 candidates * 0.82 h =  1.64-2.46 h
estimated total:       40-41 candidates * 0.82 h = 32.80-33.62 h
```

`tools/optimizer/scripts/run_study.sh` is an internal helper used by both wrappers. It runs one compare or optimize study from one materialized config, writes logs and run metadata, calls the optimizer CLI, and builds the per-study summary.

## Low-level Command (tool-local)
```bash
cd tools/optimizer
python -m paper_optimizer.cli optimize --study-type compare --config configs/compare_models.json --out runs/compare_out
```

## Inputs
- optimizer config preset (`tools/optimizer/configs/*.json`)
- benchmark manifest paths (table/schema/pdf_dir/gold)
- candidate definitions and optional search spaces

## Outputs
- study-level summary artifacts
- per-candidate run/eval outputs
- optional external-result baselines scored by Eval and shown beside internal candidates
- recommended winner/default diagnostics

## Canonical Presets

These are the experiment templates. Each preset is focused on one comparison question. 

- `tools/optimizer/configs/compare_models.json`
- `tools/optimizer/configs/compare_prompts.json`
- `tools/optimizer/configs/compare_retrieval_parameters.json`
- `tools/optimizer/configs/compare_extraction_features.json`
- `tools/optimizer/configs/optimize_parameter_sweeps.json`

The current dev suite in the planned real-run presets aggregates all three checked-in benchmark datasets:

- `bench_massively_parallel_reporter_assays`
- `bench_genome_editing`
- `bench_spatial_transcriptomics`

You would modify a preset if you want to:

- test a new candidate model or remove one that is no longer relevant
- compare a different prompt bundle or retrieval configuration
- narrow or widen the search space for the full-benchmark optimization stage
- create a new full-benchmark sequence with your own staged order

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
- `optimize`
- `compare`
- `benchmark_suites` (optional)
- `replicates` (optional)

Benchmark intent labels:

- real benchmark: expects non-fixture paths and meaningful development or long-running benchmark use
- fixture/manual: safe for checked-in examples and manual inspection
- smoke: minimal contract check, not meaningful benchmark evidence

Important interpretation rules:

- `compare-models` ranks explicit candidate lists.
- `full-benchmark` chains several compare and optimize stages together.

## Benchmark Suites And Replicates

Benchmark suites and replicates are the canonical runtime model. A simple run is on one benchmark dataset with `replicates.count = 1`; multi-benchmark suites (multiple benchmark datasets) and repeated replicates use the same execution path.

Use benchmark suites when you need one study to cover several distinct benchmark aspects, for example:

- different kind of topics
- text extraction
- figure or vision-heavy extraction
- reasoning-heavy fields

Use replicates when you want to estimate stability instead of trusting one candidate x benchmark run.

## External Result Baselines

Benchmarks can include precomputed filled tables from external software. Optimizer scores them with Eval before the internal candidates and includes them in `results/results.csv`, plots, and the HTML report as `external_{label}` rows.

```json
"external_results": [
  {
    "label": "external_tool_v1",
    "system": "external-tool",
    "path": "../../../external_results/mpra_filled.csv"
  }
]
```

The external table must use stable `row_id` values matching the benchmark gold table. Wide format uses one row per paper and one column per field; long format uses `row_id,column_name,proposed_value`.

Canonical config shape:

```json
{
  "benchmark_suites": {
    "dev_suite": {
      "benchmark_ids": ["bench_text", "bench_vision", "bench_reasoning"],
      "aggregation": {
        "method": "weighted_mean",
        "primary_metric": "content_correctness",
        "weights": {
          "bench_text": 1.0,
          "bench_vision": 1.0,
          "bench_reasoning": 1.0
        }
      }
    }
  },
  "replicates": {
    "count": 3,
    "continue_on_failure": true
  }
}
```

Validation rules:

- `benchmark_suites` and `replicates` are optional.
- suite `benchmark_ids` must reference `benchmarks.manifests` and preserve their configured order.
- `aggregation.method` currently supports `weighted_mean`.
- `aggregation.weights` may only reference benchmark ids in the same suite.
- `replicates.count` must be a positive integer.
- `replicates.continue_on_failure` defaults to continuing when omitted.

Run suite mode with the low-level CLI:

```bash
cd tools/optimizer
python -m paper_optimizer.cli optimize --study-type compare --config configs/compare_models.json --suite dev_suite --out runs/compare_suite
```

Evaluate one candidate against a suite:

```bash
cd tools/optimizer
python -m paper_optimizer.cli evaluate-candidate --config configs/compare_models_contract_smoke.json --candidate-file candidate.json --suite smoke_suite --out runs/single_candidate
```

Interpretation guidance:

- mean plus SD or SEM gives a stability signal when `n > 1`
- `n = 1` is reported as a warning, not as a variance estimate
- failed, unscored, or degraded replicates stay visible in machine-readable outputs and `report.html`
- suite-level weighted means use benchmark-level means, not raw replicate rows
- raw winner and recommended default can differ when trust caveats are material

## Execution Phases

Optimizer is orchestration-only. It does not extract values itself and it does not judge values itself. For every internal candidate x benchmark x replicate, it runs the same ordered phases:

1. Resolve study config: load the preset, selected suite, benchmark manifests, replicate count, candidates, and search space.
2. Materialize candidate bundle: write the candidate manifest and resolved config overlays for that candidate.
3. Launch main-app extraction: start a headless/eval-mode main-app run for that candidate and benchmark. This run parses PDFs, matches rows, retrieves evidence, produces proposals, runs optional figure review, and writes the run bundle.
4. Validate main-app output: confirm the expected run reference, run directory, `run.json`, config snapshot, summaries, and proposal artifacts exist.
5. Launch eval: pass the completed run bundle to eval. Eval then performs its own deterministic scoring phase followed by judge-major LLM batches.
6. Validate eval output: confirm eval summary and expected per-run artifacts satisfy the optimizer contract.
7. Record candidate result: merge main-app runtime metadata, eval metrics, diagnostics, warnings, and artifact references into candidate result rows.
8. Aggregate replicates and suites: summarize candidate x benchmark, candidate x suite, and study-level results.
9. Rank and recommend: rank raw results, apply guardrails and trust caveats, then write `best_candidate.json`, `summary.json`, plots, and `report.html`.

### Proposal And Judging Organization

Proposal generation belongs to the main app phase. The optimizer waits for the main app to produce proposals for the whole candidate run before eval starts. It does not alternate "extract one cell, judge one cell" loops.

Judging belongs to the eval phase. Eval first determines all cells that require LLM judging, then runs grouped judge batches. In dual-judge mode, both judges' per-cell records are preserved and disagreement is reported as a trust signal.

## How Outputs Are Organized

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

## How To Interpret Html Reports

- winner: best benchmark result under the scoring and acceptance rules
- recommended default: operational recommendation after trust, degraded-mode, evidence, or runtime caveats are considered
- degraded candidate: a candidate that ran with capability degradation or contract caveats and should not be treated like a healthy peer

## Diagnosing Bad Runs

Check:

- experiment `summary.json`
- candidate rows in `results/results.jsonl`
- the candidate's nested main-app `run.json` and reviewer summary
- the nested eval `run_summary.json`
