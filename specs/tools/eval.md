# Eval Tool

## Purpose

The eval tool is an internal CLI-first evaluator for main-app run bundles.

It reads run artifacts from files, scores proposals against a human-filled gold table, and writes inspectable per-cell, per-run, and cross-run comparison artifacts.

For the fuller pre-unification eval spec stack, including detailed module-layout, CLI, rationale, and task-history material, see `../archive/verbatim/eval/spec.md`, `../archive/verbatim/eval/plan.md`, `../archive/verbatim/eval/research.md`, and `../archive/verbatim/eval/tasks.md`.

Eval is a companion tool. It is not a second extraction product and it does not run extraction itself.

## Core workflows

The evaluator supports two workflows:

1. evaluate one or more run bundles against a gold CSV or XLSX input
2. rebuild comparison artifacts from previously written run summaries

## Tool boundaries

Eval must:

- remain a separate runtime from the main app
- read run bundles as files rather than importing main-app runtime code
- keep correctness metrics and evidence metrics separate
- keep deterministic structured scoring separate from judge-backed text scoring
- write filesystem artifacts as the canonical output surface

## Inputs and outputs

Eval consumes main-app run bundles that conform to `../contracts/run-bundle.md`.

Eval emits per-run and cross-run summaries that conform to `../contracts/eval-summary.md`.

Shared proposal and evidence expectations used during scoring are defined in `../contracts/proposals-and-evidence.md`.

## Scoring policy

- Headline scoring uses gold-present cells by default.
- Gold-empty cells are reported as diagnostics, not silently folded into headline correctness.
- Boolean, categorical, and numeric scoring remain deterministic.
- Text scoring is judge-backed by default, with explicit deterministic override support where appropriate.
- Runs that are degraded but contract-valid should remain scoreable whenever possible.
- Unscored outcomes must stay explicit through `scored = false` and `unscored_reason` rather than appearing as silent blanks.

## Judge path

- LM Studio is the default local-first judge path.
- Judge behavior must remain bounded, reproducible, and fully instrumented.
- Judge failures on one cell must not abort an otherwise valid evaluation run.

## Ownership boundary

This file owns eval-tool behavior and scope.

It does not own the shared run-bundle, proposal/evidence, or summary contracts. Those belong in `../contracts/`.