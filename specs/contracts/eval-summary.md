# Eval Summary Contract

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Machine-readable contracts under [`schemas/`](schemas/) remain current.

- Status: Compatibility reference
- Owner: Shared Contracts
- Depends on: tools/eval.md
- Consumed by: tools/optimizer/, docs/tools/optimizer.md

## Purpose

This file defines the shared per-run evaluation summary and comparison-row contract produced by eval and consumed by optimizer.

## Shared summary truths

Eval outputs must preserve, in stable machine-readable form:

- explicit `scored` state
- explicit `unscored_reason` when a run or cell is unscored
- headline correctness metrics
- evidence metrics
- join-failure and judge-failure diagnostics
- compact main-app provenance passthrough needed for optimizer reporting
- evidence-anchor audit totals and reason histograms
- metadata-family summaries grouped by field kind, state, and failure attribution

## Headline metric policy

The evaluator reports content-focused correctness metrics as the primary headline surface.

Metadata correctness may remain available as a secondary metric.

Legacy aliases may exist for bounded compatibility, but downstream configurations should prefer the explicit current names.

## Judge-summary policy

When dual-judge mode is enabled, eval summaries must preserve:

- per-judge correctness aggregates
- disagreement metrics
- absolute delta metrics
- judge-specific request-failure and unclear counts
- judge response-mode usage summaries

These outputs must stay explicit rather than being collapsed into a single opaque score.

## Comparison-row policy

Flat comparison rows must carry enough run metadata, metrics, diagnostics, and provenance for optimizer reporting without requiring reload of verbose run diagnostics.

That includes:

- run identity and mode
- scoreability truth
- primary and secondary metrics
- evidence-grounded metrics
- compact extraction and retrieval provenance
- failure-attribution counts
- dual-judge completion truth plus enough per-judge detail for trust reporting

## Ownership boundary

This file is a compatibility reference for the shared eval-output surface used by optimizer. Canonical markdown behavior lives in `../spec.md`.

Optimizer docs may define how the tool uses these summaries, but not redefine their shared fields here.
