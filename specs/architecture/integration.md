# Integration

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Do not treat this file as normative when it conflicts with the canonical files.

- Status: Compatibility reference
- Owner: Architecture
- Depends on: contracts/run-bundle.md, contracts/eval-summary.md, contracts/optimizer-candidate.md
- Consumed by: tools/eval/, tools/optimizer/, docs/contracts/

## Purpose

This file preserves compatibility notes for the integration model across the main app, eval, and optimizer. Canonical integration behavior lives in `../spec.md`.

## Integration flow

The monorepo integration flow is:

1. the main app executes extraction and writes a run bundle
2. eval reads the run bundle and writes scored outputs and summaries
3. optimizer launches the main app and eval, then records candidate-level experiment state

## Shared-contract rule

Integration between these tools must happen through explicit persisted contracts.

- main app to eval: `contracts/run-bundle.md` and `contracts/proposals-and-evidence.md`
- eval to optimizer: `contracts/eval-summary.md`
- optimizer-owned candidate and decision artifacts: `contracts/optimizer-candidate.md`

## Decoupling rule

The tools remain separate runtimes.

- eval must not import main-app runtime code to score runs
- optimizer must not reimplement extraction or scoring logic
- main-app product docs must not absorb tool-only behavior

## Provenance rule

Shared provenance needed by downstream tooling must be emitted in stable summary artifacts and machine-readable files, not left only in verbose diagnostics or implicit code paths.
