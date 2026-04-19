# Monorepo Spec System

## Purpose

This directory is the canonical current spec source of truth for the monorepo.

The main app is the primary product. Eval and optimizer are internal companion tools that consume or extend main-app artifacts through shared contracts defined once in this tree.

## Target structure

The target structure is intentionally simple:

- `product/`: current main-app product behavior
- `tools/`: current eval and optimizer behavior
- `contracts/`: current shared cross-tool contracts
- `architecture/`: current repo and integration boundaries
- `process/`: current maintenance and verification policy
- `plan.md`: current technical direction and durable rationale summary
- `tasks.md`: current implementation status only
- `archive/verbatim/`: historical legacy spec material only

Anything under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/` is current.
Anything under `archive/verbatim/` is historical and non-normative.

## Reading order

Use this reading order for spec-driven work:

1. `product/overview.md`
2. `product/main-app.md`
3. `product/review-workflow.md`
4. relevant `tools/*.md`
5. relevant `contracts/*.md`
6. relevant `architecture/*.md`
7. `process/change-policy.md`
8. `process/testing-strategy.md`
9. `plan.md`
10. `tasks.md`

If you need historical wording, old acceptance language, or superseded rationale, read the relevant file under `archive/verbatim/`.

## Ownership rules

Each important truth should have one owning file:

- Main-app product behavior belongs in `product/overview.md`, `product/main-app.md`, or `product/review-workflow.md`.
- Shared artifact, proposal, evidence, and summary contracts belong in `contracts/`.
- Repo and tool boundaries belong in `architecture/`.
- Maintenance and verification policy belong in `process/`.
- Implementation status belongs in `tasks.md` only.
- Historical material belongs in `archive/verbatim/` only.

Do not restate shared contracts in product or tool docs beyond a short pointer.

## Historical archive

The historical archive is intentionally narrow.

- Keep verbatim preserved legacy files under `archive/verbatim/`.
- Do not treat historical files as a second current spec surface.
- Do not reintroduce annotated archive copies, migration ledgers, or parallel summary layers unless there is a concrete temporary migration need.

## Update rule

Any behavior change must update the owning current spec file in the same work pass.

If older historical detail is still worth keeping after a rewrite, preserve it in `archive/verbatim/` or leave the existing preserved file in place. Do not create a second semi-current archive layer.