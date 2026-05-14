# Proposals And Evidence Contract

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Machine-readable contracts under [`schemas/`](schemas/) remain current.

- Status: Compatibility reference
- Owner: Shared Contracts
- Depends on: product/main-app.md, product/review-workflow.md
- Consumed by: app/backend/src/backend/app/, tools/eval/

## Purpose

This file defines the shared proposal, evidence, and support-quality contract used across the monorepo.

## Proposal rules

- The main app persists one best proposal per eligible target cell.
- A proposal being present does not imply correctness.
- A proposal may still be reviewable when support is weak, but its support label must remain honest.
- Metadata and front-matter proposals must preserve explicit lane and source truth rather than being hidden inside the generic retrieval path.

Proposal records should preserve enough published information for downstream review and scoring, including:

- stable join identity for the target cell
- proposed value and field context
- support label and primary evidence
- extraction lane when the proposal came from metadata or another non-default path
- failure attribution or degraded-path truth when the proposal is weak, fallback-driven, or partially blocked

## Evidence rules

Evidence is attached to proposals and remains inspectable.

Each proposal may carry multiple evidence items when useful, but one item is primary.
Evidence ranking must be determined by source authority and field relevance, not by model-return order.

Direct text support should normally outrank weaker inferred support when both exist for the same field, unless the field definition explicitly requires reasoning or calculation to interpret the paper correctly.

## Evidence types

The contract must distinguish at least:

- direct quote evidence
- inferred reasoning
- calculation-based justification
- approximate highlight fallback
- quote-plus-page fallback
- caption-grounded figure evidence
- visual-interpretation figure evidence

Fallback evidence must be labeled as fallback rather than presented as exact.
Figure-derived evidence must remain distinct from text-derived evidence even when both support the same proposal.

## Anchor-validation compatibility

The proposal and evidence surface must remain compatible with downstream anchor validation.

That means persisted evidence, quote text, page references, and compatible source-text artifacts must remain available in the run bundle so eval can distinguish:

- `anchor_valid`
- `evidence_present_but_unvalidated`
- `anchor_invalid`
- `missing_evidence`

## Support-label rules

Support labels must remain reviewer-visible and truthful.

The contract must preserve a clear distinction between:

- directly supported values
- inferred or derived values
- weak or fallback-supported values

## Ownership boundary

This file is a compatibility reference for proposal and evidence semantics shared across main app and eval. Canonical markdown behavior lives in `../spec.md`, and machine-readable contracts live in `schemas/`.

Tool docs must reference this file rather than redefining evidence types or support labels.
