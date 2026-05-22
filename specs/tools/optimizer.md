# Optimizer Tool

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Do not treat this file as normative when it conflicts with the canonical files.

- Status: Compatibility reference
- Owner: Optimizer
- Depends on: contracts/eval-summary.md, contracts/optimizer-candidate.md, architecture/integration.md
- Consumed by: tools/optimizer/, docs/tools/optimizer.md

## Purpose

The optimizer is an internal CLI-first orchestration tool for bounded candidate studies.

It coordinates the main app and eval tool to answer a bounded question: which explicit prompt, model, or config candidate performs best on a fixed benchmark under explicit guardrails.

Archive material may remain useful for historical background, but canonical optimizer behavior now lives in `../spec.md`.

Optimizer is a companion tool. It is not an extraction runtime and it is not a scoring runtime.

## Role separation

- main app = execution
- eval = scoring
- optimizer = orchestration and tracking

This separation is retained here as compatibility guidance and is canonical only where it is reflected in `../spec.md`.

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

The optimizer runtime uses suite and replicate execution as its canonical model:

candidate x suite x benchmark x replicate

A one-benchmark run is represented as a one-benchmark suite with `replicates.count = 1`.

The split names `smoke`, `dev`, and `holdout` may remain as convenience aliases in configs, but runtime execution resolves them into explicit suites such as `smoke_suite`, `dev_suite`, and `holdout_suite`.

Tool-local `evaluate-candidate` is suite-based and accepts `--suite`.

## Runtime planning note

Optimizer studies are sequential by default, so full-benchmark runtime scales with candidate count, benchmark count, replicate count, and model speed.

The 2026-05-15 full-benchmark attempt on the three-benchmark dev suite with three replicates is the current operator reference point:

- model compare: 9 completed candidates, 12.45 h total, about 83 min per candidate
- prompt compare: 3 completed candidates, 6.25 h total, about 125 min per candidate
- retrieval sweep: 10 completed candidates, 22.54 h total, about 135 min per candidate
- extraction feature sweep: 4 completed candidates, 8.64 h total, about 130 min per candidate before interruption

Operator docs should therefore present full benchmark as a multi-day workflow when the candidate set is broad, and recommend reduced candidate sets for routine iteration.

## Benchmark manifests

Single benchmark manifests remain valid as benchmark leaves inside suites.

One manifest represents one benchmark definition with one:

- table input
- schema input
- PDF directory
- gold file
- optional eval schema
- main-app argument list
- eval argument list

Manifest-level `benchmark_kind` and `benchmark_label` remain important because they distinguish real benchmark evidence from fixture, smoke, or other non-canonical evidence.

`BenchmarkManifest` corresponds to one table/schema/pdf_dir/gold/eval setup. Multi-benchmark behavior belongs to suite execution, not to an overloaded manifest.

## Benchmark suites

A benchmark suite is an explicit ordered set of benchmark ids.

Its purpose is to let one study evaluate candidates across separate benchmark aspects, for example:

- text extraction
- vision or figure extraction
- reasoning or argumentation
- metadata-heavy matching or extraction

Required suite rules:

- Suites must be explicit in checked-in configs.
- Optimizer must not silently include all manifests unless config explicitly asks for that.
- One-benchmark suites are the supported simple case.
- A small config-load normalization shim may convert split aliases into one-benchmark suites for local migration convenience.
- Suite order must be preserved in persisted metadata and reports so operators can tell which benchmark ran first and how the suite was constructed.
- A suite must reference known benchmark ids only.
- Suite metadata must preserve enough information to distinguish the suite identifier from the benchmark identifiers nested inside it.

## Config shape

Canonical optimizer configs include suite and replicate sections like:

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
  },
  "compare": {
    "suite_id": "dev_suite",
    "holdout_suite_id": "holdout_suite"
  },
  "optimize": {
    "suite_id": "dev_suite",
    "holdout_suite_id": "holdout_suite"
  }
}
```

Config requirements:

- `benchmark_suites` is an object keyed by suite id.
- Each suite definition must include an ordered `benchmark_ids` array.
- Each suite definition must include explicit aggregation intent.
- `aggregation.method` currently supports `weighted_mean` for suite-level scoring.
- `aggregation.primary_metric` must name one metric already exposed through optimizer acceptance and reporting.
- `aggregation.weights` must be explicit when `weighted_mean` is used.
- `replicates.count` must be a positive integer.
- `replicates.continue_on_failure` controls whether one failed replicate blocks the remaining planned replicates for that candidate x benchmark.

## Replicates


Replicates repeat candidate x benchmark evaluation.

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

### Per candidate x benchmark aggregation

The optimizer aggregates replicate rows into one candidate x benchmark summary that preserves:

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

### Per candidate x suite aggregation

The optimizer aggregates benchmark summaries into one candidate x suite summary that preserves:

- weighted mean primary metric across benchmark-level means
- benchmark coverage
- failed benchmark counts
- failed replicate counts
- degraded benchmark or replicate counts
- trust caveats

Suite-level weighted mean should use benchmark-level means, not raw replicate rows, unless a future config explicitly changes this rule.

Ranking must consider trust signals, not only scalar score. Trust signals include degraded mode, contract invalidity, judge instability, missing evidence, benchmark coverage loss, and failed or unscored replicate counts.

## Reports

HTML reports show:

- suite-level ranking
- per-benchmark breakdown
- replicate mean plus SD or SEM when `n > 1`
- warning when `n = 1`
- failed, unscored, and degraded replicate counts
- candidate stability notes
- links to nested main-app and eval artifacts
- distinction between raw winner and recommended default
- capability-use and suppression diagnostics for vision, figure evidence, candidate selection, recall rescue, and whole-document fallback

Plotting and report tables should make it possible to answer:

- which candidate led at suite level
- which benchmark drove the suite result
- whether the result was stable across replicates
- whether error bars overlap enough that the ranking is fragile
- whether trust caveats weaken the raw winner recommendation

## Migration policy

This private optimizer is allowed to drop pre-suite internal compatibility when simplification improves the tool.

Supported behavior:

- ergonomic wrapper commands remain available
- low-level compare and optimize commands are suite-based
- one-benchmark suites are the supported simple case
- split labels may remain as convenience aliases, but they resolve to suites

Not guaranteed:

- old pre-suite result artifacts remain readable
- old internal one-benchmark execution paths remain available
- old configs without explicit suites are not the preferred config form

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
- surface retrieval mode, top-k, rescue mode, whole-document mode, structured-output mode, fallback mode, dual-judge status, evidence-anchor audits, metadata-family summaries, capability-use/suppression counters, join failures, and runtime accounting in reports
- treat judge disagreement, judge request failures, and evidence weakness as first-class trust signals in ranking and report warnings rather than burying them as secondary diagnostics
- sort healthy scored candidates ahead of scored-degraded, unscored, and failed candidates so unsupported structured-output candidates do not look equivalent to valid runs

## Ownership boundary

This file is a compatibility reference for optimizer behavior and mode semantics. Canonical behavior lives in `../spec.md`.

It does not own shared scorer outputs or main-app artifact contracts. Those belong in `../contracts/`.
