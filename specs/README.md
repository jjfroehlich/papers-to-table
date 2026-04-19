# Monorepo Spec System

## Purpose

This directory is the canonical specification source of truth for the entire monorepo.

The main app remains the primary product.
The eval and optimizer tools are internal companion tools that consume or extend main-app artifacts through shared contracts defined once in this tree.

## How the spec system works

The spec tree is organized by ownership:

- `product/` defines user-facing product behavior for the main app.
- `tools/` defines the companion-tool surfaces and boundaries.
- `contracts/` defines shared cross-tool data and artifact contracts exactly once.
- `architecture/` defines monorepo structure and integration boundaries.
- `process/` defines maintenance policy and testing expectations.
- `archive/` preserves historical, exploratory, superseded, and implementation-detail-heavy spec material, including a strict verbatim preservation layer.
- `plan.md` is the supportive implementation-planning index for this spec system.
- `tasks.md` is the canonical cross-monorepo status tracker.

## Normative vs supportive files

Normative files are the files that define expected behavior or required contracts:

- `product/overview.md`
- `product/main-app.md`
- `product/review-workflow.md`
- `tools/eval.md`
- `tools/optimizer.md`
- `contracts/run-bundle.md`
- `contracts/proposals-and-evidence.md`
- `contracts/eval-summary.md`
- `contracts/optimizer-candidate.md`
- `architecture/monorepo-layout.md`
- `architecture/integration.md`
- `process/change-policy.md`
- `process/testing-strategy.md`

Supportive files help implementation and maintenance but do not own runtime behavior by themselves:

- `archive/`
- `plan.md`
- `tasks.md`
- `AGENTS.md`

If a supportive file conflicts with a normative file, the normative file wins and the supportive file must be updated.
`plan.md` should preserve durable rationale, technical foundations, current risks, and open questions that help future contributors understand why the normative files look the way they do.
`archive/` preserves earlier source material and detailed historical context that should remain traceable even when no longer normative.

## Lossless migration rule

This spec system now uses a lossless reorganization model:

- current behavior and active contracts belong in the normative files listed above
- older, exploratory, superseded, or more detailed material belongs in `archive/`
- shortening a normative file is acceptable only when the removed detail is preserved elsewhere and linked clearly
- large deletions are suspicious until every major removed section has an explicit disposition

Prefer moving, splitting, indexing, cross-linking, and archiving over deleting or heavily summarizing.

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

If you need historical rationale, old section wording, or superseded implementation detail, continue with:

11. `archive/README.md`
12. `archive/mapping/preservation-audit.md`
13. `archive/mapping/legacy-file-mapping.md`
14. the relevant archived file under `archive/verbatim/`

## Ownership rules

Each important truth should have one owning file:

- Main-app product behavior belongs in `product/main-app.md` or `product/review-workflow.md`.
- Main-app, eval, and optimizer shared file, artifact, schema, and metric rules belong in `contracts/`.
- Repo and tool boundaries belong in `architecture/`.
- Process rules for spec maintenance belong in `process/`.
- Implementation status belongs in `tasks.md` only.
- Historical or superseded material that may still be useful later belongs in `archive/`, not in deleted diff hunks.

Do not restate shared contracts in product or tool docs beyond a short pointer.

## Current-to-archive mapping model

- Normative owners define the current source of truth.
- Archive files preserve the pre-unification source material and other superseded but still-useful depth.
- Explicit file-level preservation mapping lives in `archive/mapping/legacy-file-mapping.md`.
- Preservation accounting lives in `archive/mapping/preservation-audit.md`.
- Concise restoration notes live in `archive/mapping/restoration-summary.md`.

## Legacy-to-current mapping summary

- Old `specs/spec.md` overview, goals, principles, run modes, and product behavior moved to `product/overview.md`, `product/main-app.md`, and `product/review-workflow.md`.
- Old `specs/spec.md` shared artifact and downstream-consumption rules moved to `contracts/run-bundle.md`, `contracts/proposals-and-evidence.md`, and `contracts/eval-summary.md`.
- Old `specs/plan.md` monorepo structure and cross-tool integration material moved to `architecture/monorepo-layout.md` and `architecture/integration.md`.
- Old `specs/plan.md` verification and workflow-maintenance expectations moved to `process/testing-strategy.md` and `process/change-policy.md`.
- Old `specs/spec.md`, `specs/plan.md`, `specs/research.md`, and `specs/tasks.md` are preserved verbatim under `archive/verbatim/main-app/`.
- Old eval spec-stack files are preserved verbatim under `archive/verbatim/eval/`.
- Old optimizer spec-stack files are preserved verbatim under `archive/verbatim/optimizer/`.
- Mapping from original path to verbatim archive path to current normative owners is recorded in `archive/mapping/legacy-file-mapping.md`.

No major legacy spec document is considered safely removed unless its content is either preserved under `archive/` or called out as exact duplicate/noise in the mapping notes.

## Duplicate or conflicting areas resolved

- Shared run-bundle shape previously appeared in both main-app and eval specs. It now lives only in `contracts/run-bundle.md`.
- Proposal, evidence, provenance, and anchor-validation expectations previously appeared in both main-app and eval materials. They now live only in `contracts/proposals-and-evidence.md` and `contracts/eval-summary.md`.
- Optimizer candidate and result semantics previously mixed tool-specific behavior with shared scorer outputs. Shared scorer outputs now live in `contracts/eval-summary.md`, while optimizer-owned candidate and decision rules live in `contracts/optimizer-candidate.md`.
- Monorepo role separation and tool boundaries previously appeared in several plan or spec files. They now live only in `architecture/monorepo-layout.md` and `architecture/integration.md`.
- Status tracking was split across three `tasks.md` files. It now lives only in `tasks.md`.

## How future changes should update specs

- Main-app behavior changes: update the owning file in `product/` and any affected shared contract in `contracts/`.
- Eval changes: update `tools/eval.md` only for tool-owned behavior, and update `contracts/` when the change affects shared artifact or metric contracts.
- Optimizer changes: update `tools/optimizer.md` only for tool-owned behavior, and update `contracts/` when the change affects shared scorer or candidate contracts.
- Cross-tool integration changes: update `architecture/integration.md` and the affected `contracts/` file together.
- When replacing or compressing older material, preserve it under `archive/` with a short status header instead of deleting it silently.
- If a section is intentionally removed as exact duplicate or noise, record that disposition in the mapping material and keep the file-level preservation audit current.
- Any behavior change must also follow `process/change-policy.md` and keep `tasks.md` truthful in the same pass.