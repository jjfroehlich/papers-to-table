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
- fixed candidate list
- same benchmark, same prompt stack, same retrieval defaults
- use when choosing among explicit model candidates

```bash
python scripts/papers_to_table.py optimizer compare-models
```

### Optimize One Model
- one baseline candidate
- bounded search space for a single model family
- use when you want to tune retrieval parameters or similar knobs without changing the model family

```bash
python scripts/papers_to_table.py optimizer optimize-one-model
```

### Overnight Sequence
- multi-stage sequence
- compare models, prompts, retrieval settings, retrieval modes, then run the optimization stage which sweeps different parameter spaces

```bash
python scripts/papers_to_table.py optimizer overnight
```

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
- recommended winner/default diagnostics

## Canonical Presets

These are the experiment templates. Each preset is focused on one comparison question. 

- `tools/optimizer/configs/compare_models.json`
- `tools/optimizer/configs/compare_prompts.json`
- `tools/optimizer/configs/compare_retrieval.json`
- `tools/optimizer/configs/compare_retrieval_modes.json`
- `tools/optimizer/configs/optimize_one_model.json`
- `tools/optimizer/configs/compare_models_overnight.json`
- `tools/optimizer/configs/optimize_overnight.json`

You would modify a preset if you want to:

- test a new candidate model or remove one that is no longer relevant
- compare a different prompt bundle or retrieval configuration
- narrow or widen the search space for a single-model optimization run
- create a new overnight sequence with your own staged order

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

Benchmark intent labels:

- real benchmark: expects non-fixture paths and meaningful development or overnight use
- fixture/manual: safe for checked-in examples and manual inspection
- smoke: minimal contract check, not meaningful benchmark evidence

Important interpretation rules:

- `compare-models` ranks explicit candidate lists.
- `optimize-one-model` starts from one baseline and proposes challengers.
- `overnight` chains several compare and optimize stages together.

## Planned Benchmark Suites And Replicates

Benchmark suites and replicates are now specified in the optimizer spec, but they are not implemented in the current runtime yet.

Use benchmark suites when you need one study to cover several distinct benchmark aspects, for example:

- text extraction
- figure or vision-heavy extraction
- reasoning-heavy fields
- metadata-heavy matching and extraction

Use replicates when you want to estimate stability instead of trusting one candidate × benchmark run.

Planned additive config shape:

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

Interpretation guidance for the future suite or replicate reports:

- mean ± SD or SEM gives a stability signal when `n > 1`
- `n = 1` should be read as a warning, not as a variance estimate
- failed, unscored, or degraded replicates must stay visible in the report
- raw winner and recommended default can differ when trust caveats are material

Until runtime support lands, continue using the current single-benchmark `smoke` / `dev` / `holdout` workflow.

## How Outputs Are Organized

Each experiment writes an experiment directory with:

- `report.html` HTML report with charts, scores, and the summary
- `experiment.json` resolved experiment config and preset
- `summary.json` compact status summary and winner metadata
- `best_candidate.json` winner record, when one exists
- `results/results.csv` tabular candidate results
- `results/results.jsonl` candidate results with nested detail
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
