# Optimizer Tool

## Purpose

The optimizer is an internal CLI-first orchestration tool for bounded candidate studies.

It coordinates the main app and eval tool to answer a bounded question: which explicit prompt, model, or config candidate performs best on a fixed benchmark under explicit guardrails.

For the fuller pre-unification optimizer spec stack, including detailed orchestration, rationale, and task-history material, see `../archive/verbatim/optimizer/spec.md`, `../archive/verbatim/optimizer/plan.md`, `../archive/verbatim/optimizer/research.md`, and `../archive/verbatim/optimizer/tasks.md`.

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

## Benchmark policy

- `dev` drives compare and optimize decisions.
- `holdout` remains separate from the main search benchmark.
- Holdout validates final recommendations after dev-phase ranking or optimization.

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

## Ownership boundary

This file owns optimizer behavior and mode semantics.

It does not own shared scorer outputs or main-app artifact contracts. Those belong in `../contracts/`.