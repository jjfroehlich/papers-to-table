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

`spec.md` is the integrated cross-repo entry point, not a replacement for the domain-owning current specs.

`product/`, `tools/`, `contracts/`, `architecture/`, and `process/` remain normative for their domains. New behavior changes should update `spec.md` plus the specific owning current file that carries the detailed durable truth.

## Reading order

1. [`spec.md`](spec.md) — integrated current product and system specification
2. [`research.md`](research.md) — rationale, tradeoffs, and historical notes that still matter
3. [`plan.md`](plan.md) — technical direction and roadmap
4. [`tasks.md`](tasks.md) — current verified status and backlog
5. [`process/change-policy.md`](process/change-policy.md) — spec-update ownership and anti-duplication rules
6. [`process/testing-strategy.md`](process/testing-strategy.md) — verification expectations for behavior, docs, and contracts

## Supporting references

The subdirectories remain useful current specs for modular ownership and detailed contracts:

- `product/` — focused product slices and reviewer workflow ownership
- `tools/` — eval and optimizer scope details
- `contracts/` — shared filesystem, summary, and evidence contracts
- `architecture/` — repo boundaries and integration structure
- `process/` — testing and change policy
- `archive/verbatim/` — preserved historical material only

When current truth changes, update `spec.md` plus any owning supporting reference in the same pass.

When `spec.md` and a supporting current file overlap, keep the detailed durable truth in the owning current file and reduce `spec.md` to the integrated summary needed to understand the whole repo.
