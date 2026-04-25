# Optimizer Tool

- Status: Normative
- Owner: Optimizer
- Depends on: contracts/eval-summary.md, contracts/optimizer-candidate.md, architecture/integration.md
- Consumed by: tools/optimizer/, docs/optimizer/README.md

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
