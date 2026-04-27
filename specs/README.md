# Spec system

This directory is the current source of truth for papers-to-table.

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
