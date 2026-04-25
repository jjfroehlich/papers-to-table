# Eval Tool

- Status: Normative
- Owner: Eval
- Depends on: contracts/run-bundle.md, contracts/eval-summary.md, contracts/proposals-and-evidence.md
- Consumed by: tools/eval/, docs/eval/README.md

## Purpose

The eval tool is an internal CLI-first evaluator for main-app run bundles.

It reads run artifacts from files, scores proposals against a human-filled gold table, and writes inspectable per-cell, per-run, and cross-run comparison artifacts.

Archive material may remain useful for historical background, but this current file is the complete active source of truth for eval behavior.

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
- The default real-benchmark judge pair is `judge_a=google/gemma-4-26b-a4b` and `judge_b=openai/gpt-oss-20b`.
- Judge behavior must remain bounded, reproducible, and fully instrumented.
- Judge failures on one cell must not abort an otherwise valid evaluation run.
- Real benchmark evaluation should run dual-judge scoring by default.
- Dual-judge execution must be judge-major: prepare all eligible text-cell requests, execute all `judge_a` work, execute all `judge_b` work, group batches by effective provider/model/settings, then merge results back into deterministic scored-cell order.
- Per-run summaries must preserve per-judge verdicts, request failures, unclear counts, disagreement counts or rates, and response-mode usage.
- Per-run summaries must include judge execution diagnostics with batch counts, eligible counts, runtime totals, execution order, model-switch counts, and cleanup failures.

## Audit outputs

Eval must emit inspectable audit summaries in stable per-run outputs for:

- evidence-anchor validation totals, validated-versus-unvalidated counts, invalid-anchor counts, and reason histograms
- evidence ID resolution from nested support fields and top-level `primary_evidence_id`, `evidence_ids`, and `ordered_supporting_evidence_ids`
- anchor outcome counts for missing evidence, valid anchors, invalid anchors, present-but-unvalidated evidence, invalid pages, missing quote text, page bounds, missing persisted text, and quote locatability
- metadata-family summaries grouped by field kind, state, and failure attribution
- dual-judge completion truth and disagreement diagnostics
- ratio and coverage metrics must remain within valid numeric bounds; impossible values are contract defects

## Ownership boundary

This file owns eval-tool behavior and scope.

It does not own the shared run-bundle, proposal/evidence, or summary contracts. Those belong in `../contracts/`.
