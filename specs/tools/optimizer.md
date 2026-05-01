# Optimizer Tool

- Status: Normative
- Owner: Optimizer
- Depends on: contracts/eval-summary.md, contracts/optimizer-candidate.md, architecture/integration.md
- Consumed by: tools/optimizer/, docs/tools/optimizer.md

## Purpose

The optimizer is an internal CLI-first orchestration tool for bounded candidate studies.

It coordinates the main app and eval tool to answer a bounded question: which explicit prompt, model, or config candidate performs best on a fixed benchmark under explicit guardrails.

Archive material may remain useful for historical background, but this current file is the complete active source of truth for optimizer behavior.

Optimizer is a companion tool. It is not an extraction runtime and it is not a scoring runtime.

## Role separation

- main app = execution
- eval = scoring
- optimizer = orchestration and tracking

This separation is normative.

## Study modes

The optimizer supports:

- `compare` for fixed candidate-set ranking on a dev benchmark
- `optimize` for bounded incumbent-challenger promotion on a dev benchmark
- `preflight` for contract and launch validation without running a study

Prepared operator workflows are:

- compare models, using fixed model lists on real dev or overnight manifests
- optimize one model, focused on `google/gemma-4-26b-a4b` and primarily `retrieval_top_k` around the default retrieval stack
- overnight run, using staged real-benchmark configs with incremental summaries

## Benchmark policy

- `dev` drives compare and optimize decisions.
- `holdout` remains separate from the main search benchmark.
- Holdout validates final recommendations after dev-phase ranking or optimization.
- Real benchmark configs must stay clearly separate from smoke or fixture configs.
- Real benchmark manifests must fail preflight if they point at fixture assets, omit required benchmark files, or omit required dual-judge configuration.
- Real benchmark configs should default `judge_b` to `openai/gpt-oss-20b` unless current validation evidence shows a more stable cross-family second judge.
- Meaningful compare, optimize, dev, and overnight configs must not silently fall back to fixture benchmarks; fixture and smoke configs exist only for fast contract checks.

## Current benchmark selection behavior

The current optimizer runtime selects one benchmark at a time.

- `benchmarks.smoke`, `benchmarks.dev`, and `benchmarks.holdout` map split names to one benchmark id each.
- Compare and optimize studies currently run against one resolved `dev` benchmark id at a time.
- Holdout validation currently runs against one resolved `holdout` benchmark id at a time.
- Tool-local `evaluate-candidate` currently accepts only `--benchmark smoke`, `--benchmark dev`, or `--benchmark holdout`.
- Current reports, plots, and result rows are candidate-level outputs for one benchmark at a time, not true suite or replicate aggregates.

This single-benchmark behavior is current runtime truth and must remain backward-compatible.

## Benchmark manifests

Existing single benchmark manifests remain valid.

One manifest represents one benchmark definition with one:

- table input
- schema input
- PDF directory
- gold file
- optional eval schema
- main-app argument list
- eval argument list

Manifest-level `benchmark_kind` and `benchmark_label` remain important because they distinguish real benchmark evidence from fixture, smoke, or other non-canonical evidence.

The current runtime shape is represented by `BenchmarkManifest` and corresponds to one table/schema/pdf_dir/gold/eval setup, not a multi-benchmark suite.

## Benchmark suites

Benchmark suites are specified additive behavior for the next implementation pass. They are not implemented in the current runtime yet.

A benchmark suite is an explicit ordered set of benchmark ids.

Its purpose is to let one study evaluate candidates across separate benchmark aspects, for example:

- text extraction
- vision or figure extraction
- reasoning or argumentation
- metadata-heavy matching or extraction

Required suite rules:

- Suites must be explicit in config.
- Optimizer must not silently include all manifests unless config explicitly asks for that.
- Existing `benchmarks.dev` behavior remains the backward-compatible default when no suite is configured.
- Suite order must be preserved in persisted metadata and reports so operators can tell which benchmark ran first and how the suite was constructed.
- A suite must reference known benchmark ids only.
- Suite metadata must preserve enough information to distinguish the suite identifier from the benchmark identifiers nested inside it.

## Proposed additive config shape

The next implementation pass should accept additive suite and replicate config like:

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

Config requirements for that additive shape:

- `benchmark_suites` is an object keyed by suite id.
- Each suite definition must include an ordered `benchmark_ids` array.
- Each suite definition must include explicit aggregation intent.
- `aggregation.method` currently should support `weighted_mean` for suite-level scoring.
- `aggregation.primary_metric` must name one metric already exposed through optimizer acceptance and reporting.
- `aggregation.weights` must be explicit when `weighted_mean` is used.
- `replicates.count` must be a positive integer.
- `replicates.continue_on_failure` controls whether one failed replicate blocks the remaining planned replicates for that candidate × benchmark.

## Replicates

Replicates are specified additive behavior for the next implementation pass. They are not implemented in the current runtime yet.

Replicates repeat candidate × benchmark evaluation.

One replicate is one full main-app plus eval execution for one candidate on one benchmark.

Persisted replicate rows and aggregate inputs must preserve at least:

- `candidate_id`
- `benchmark_id`
- `suite_id` when applicable
- `replicate_index`
- `replicate_id` or `replicate_label`
- primary metrics
- guardrail metrics
- diagnostic metrics
- `score_status`
- `candidate_status`
- runtime
- structured-output, degraded-mode, and trust diagnostics
- main-app artifact references
- eval artifact references

Replicate rules:

- Failed, unscored, and degraded replicates must remain visible and must not be averaged away silently.
- Replicate count `1` is valid but must be reported as `single replicate; no variance estimate`.
- Replicate indexing must be stable enough that reruns, resumed studies, and report rebuilds can distinguish replicate `0` from replicate `1` and beyond.
- Replicate-level artifacts must remain linkable back to the nested main-app and eval outputs that produced them.

## Aggregation

Aggregation is specified additive behavior for the next implementation pass. It is not implemented in the current runtime yet.

### Per candidate × benchmark aggregation

The optimizer should aggregate replicate rows into one candidate × benchmark summary that preserves:

- mean primary metric
- SD
- SEM
- `n_total`
- `n_scored`
- `n_failed`
- `n_degraded`
- runtime mean when available
- runtime SD when available
- trust caveats

### Per candidate × suite aggregation

The optimizer should aggregate benchmark summaries into one candidate × suite summary that preserves:

- weighted mean primary metric across benchmark-level means
- benchmark coverage
- failed benchmark counts
- failed replicate counts
- degraded benchmark or replicate counts
- trust caveats

Suite-level weighted mean should use benchmark-level means, not raw replicate rows, unless a future config explicitly changes this rule.

Ranking must consider trust signals, not only scalar score. Trust signals include degraded mode, contract invalidity, judge instability, missing evidence, benchmark coverage loss, and failed or unscored replicate counts.

## Reports

Suite and replicate reporting is specified additive behavior for the next implementation pass. It is not implemented in the current runtime yet.

HTML reports for suite mode must show:

- suite-level ranking
- per-benchmark breakdown
- replicate mean ± SD or SEM when `n > 1`
- warning when `n = 1`
- failed, unscored, and degraded replicate counts
- candidate stability notes
- links to nested main-app and eval artifacts
- distinction between raw winner and recommended default

Plotting and report tables should make it possible to answer:

- which candidate led at suite level
- which benchmark drove the suite result
- whether the result was stable across replicates
- whether error bars overlap enough that the ranking is fragile
- whether trust caveats weaken the raw winner recommendation

## Backward compatibility

Suite and replicate mode is additive.

The following current behavior must continue to work unchanged:

- existing compare and optimize configs using `benchmarks.dev`
- existing `evaluate-candidate --benchmark smoke|dev|holdout`
- existing result files must remain readable
- existing candidate-level reports must remain readable for old runs

New suite and replicate config must not redefine existing split semantics or silently change the meaning of old configs.

## Candidate and result expectations

Optimizer-owned candidate bundle, result, and decision semantics are defined in `../contracts/optimizer-candidate.md`.

Shared eval-summary fields consumed by optimizer are defined in `../contracts/eval-summary.md`.

## Required behavior

The optimizer must:

- preserve immutable candidate bundles with reproducible metadata
- keep scored-versus-unscored candidate state explicit
- apply gated acceptance rather than single-scalar promotion alone
- preserve truthful partial-study state for interrupted compare, optimize, and overnight workflows
- generate operator-facing reports that explain what happened, why a candidate won or failed, and what to check next
- make degraded prompt-only candidates unmistakable rather than treating them as healthy peers
- distinguish the raw benchmark winner from the recommended operational default when trust caveats differ
- surface retrieval mode, top-k, rescue mode, whole-document mode, structured-output mode, fallback mode, dual-judge status, evidence-anchor audits, metadata-family summaries, join failures, and runtime accounting in reports
- treat judge disagreement, judge request failures, and evidence weakness as first-class trust signals in ranking and report warnings rather than burying them as secondary diagnostics
- sort healthy scored candidates ahead of scored-degraded, unscored, and failed candidates so unsupported structured-output candidates do not look equivalent to valid runs

## Ownership boundary

This file owns optimizer behavior and mode semantics.

It does not own shared scorer outputs or main-app artifact contracts. Those belong in `../contracts/`.
