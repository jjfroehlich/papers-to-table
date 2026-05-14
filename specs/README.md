# Spec System

This directory contains the current source of truth for papers-to-table.

## Review Pass, 2026-05-01

The current implementation mostly follows the integrated spec: browser mode is primary, the backend keeps run bundles as the cross-tool contract, figure review is config-driven, and eval/optimizer remain companion tools. The largest alignment gaps found in this pass were:

- Browser setup still treated preflight as a separate launch gate instead of running it as the first part of normal run start.
- Blank path configuration was not first-class even though browser mode can collect paths interactively.
- Unmatched PDFs were blocked instead of becoming new reviewable rows for the common "folder of literature plus empty table" workflow.
- Some docs pages were placeholders while the implementation already had concrete behavior.

Those gaps are now reflected in `spec.md` and the manual.

## Canonical Structure

Keep fewer normative files:

- `spec.md`: full product and system behavior, backend phases, run bundle, eval/optimizer behavior, model residency policy, and report/output truth.
- `plan.md`: roadmap and technical direction only.
- `tasks.md`: verified status and backlog only.
- `contracts/schemas/*.json`: machine-readable validation contracts.
- `archive/`: old plans, generated scaffolds, and superseded verbatim specs.

`spec.md`, `plan.md`, and `tasks.md` are the only normative markdown specs. Markdown files under `product/`, `tools/`, `contracts/`, `architecture/`, and `process/` are compatibility references unless they explicitly point back to the canonical files. New behavior changes should update the canonical files first, then update manuals or schemas when needed.

## Reading order

1. [`spec.md`](spec.md) — integrated current product and system specification
2. [`plan.md`](plan.md) — technical direction and roadmap
3. [`tasks.md`](tasks.md) — current verified status and backlog
4. [`research.md`](research.md) — non-normative rationale, tradeoffs, and historical notes that still matter

## Supporting references

The subdirectories remain useful compatibility references and historical detail:

- `product/` — older focused product slices and reviewer workflow notes
- `tools/` — older eval and optimizer scope notes
- `contracts/` — older shared artifact notes plus current `schemas/`
- `architecture/` — older repo boundary and integration notes
- `process/` — older testing and change-policy notes
- `archive/verbatim/` — preserved historical material only

When current truth changes, update `spec.md`, `plan.md`, or `tasks.md`. Do not create a new normative markdown spec unless the canonical structure changes in this README first.
