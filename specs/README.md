# Spec System

This directory is the current source of truth for papers-to-table.

## Review Pass, 2026-05-01

The current implementation mostly follows the integrated spec: browser mode is primary, the backend keeps run bundles as the cross-tool contract, figure review is config-driven, and eval/optimizer remain companion tools. The largest alignment gaps found in this pass were:

- Browser setup still treated preflight as a separate launch gate instead of running it as the first part of normal run start.
- Blank path configuration was not first-class even though browser mode can collect paths interactively.
- Unmatched PDFs were blocked instead of becoming new reviewable rows for the common "folder of literature plus empty table" workflow.
- Some docs pages were placeholders while the implementation already had concrete behavior.

Those gaps are now reflected in `spec.md` and the manual.

## Proposed Structure

Keep fewer normative files:

- `spec.md`: product, workflow, contracts, and behavior that must stay true.
- `tasks.md`: current backlog and verified status only.
- `research.md`: rationale and historical tradeoffs that still matter.
- `contracts/`: machine-readable schemas and artifact contracts.
- `archive/`: old plans, generated scaffolds, and superseded verbatim specs.

Treat `plan.md`, `product/`, `tools/`, `architecture/`, and `process/` as supporting references while gradually folding durable truth into `spec.md` or `contracts/`. New behavior changes should update `spec.md` first, then only the specific supporting page that owns extra detail.

## Reading order

1. [`spec.md`](spec.md) — integrated current product and system specification
2. [`research.md`](research.md) — rationale, tradeoffs, and historical notes that still matter
3. [`plan.md`](plan.md) — technical direction and roadmap
4. [`tasks.md`](tasks.md) — current verified status and backlog

## Supporting references

The subdirectories remain useful supporting references for modular ownership and detailed contracts:

- `product/` — focused product slices
- `tools/` — eval and optimizer scope details
- `contracts/` — shared filesystem and evidence contracts
- `architecture/` — repo boundaries and integration structure
- `process/` — testing and change policy
- `archive/verbatim/` — preserved historical material only

When current truth changes, update `spec.md` plus any owning supporting reference in the same pass.
