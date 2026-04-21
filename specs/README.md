# Monorepo Spec System

## Purpose

This directory is the canonical current spec source of truth for the monorepo.

The main app is the primary product. Eval and optimizer are internal companion tools that consume or extend main-app artifacts through shared contracts defined once in this tree.

## Reading order

Use this order for spec-driven work:

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

Anything under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/` is current.
Anything under `archive/verbatim/` is historical and non-normative background only.

Current files must be sufficient on their own for active work. Historical archive files may help with background or provenance, but they must not be required to understand the current product or justify current behavior.

## Ownership rules

Each important truth should have one owning file:

- Main-app product behavior -> `product/overview.md`, `product/main-app.md`, `product/review-workflow.md`
- Shared artifact, proposal, evidence, and summary contracts -> `contracts/`
- Repo and tool boundaries -> `architecture/`
- Maintenance and verification policy -> `process/`
- Implementation status -> `tasks.md` only
- Historical wording -> `archive/verbatim/` only

## Docs map by audience

- Product/repo entrypoint -> `../README.md`
- Operator docs -> `../docs/main-app/README.md`
- Contributor quickstart -> `../CONTRIBUTING.md`
- Coding-agent and maintainer rules -> `../AGENTS.md` and `AGENTS.md`
- Normative product/tool/contracts/process specs -> this directory

## Glossary and examples

### Key terms

- **Run preflight**: resolves inputs, checks readiness, and shows scope before launch.
- **Run bundle**: the filesystem artifact bundle under `{output_dir}/{run_id}/`.
- **Reviewable proposal**: belongs in the main queue and can receive an explicit review decision.
- **Diagnostics-only outcome**: important persisted context that stays out of the main queue unless specifically inspected.
- **Staged handle**: backend-readable reference created from browser-selected files.

### Concrete examples

- **Workflow example**: preflight -> start run -> live SSE updates -> queue-first review -> diagnostics drawer -> explicit export.
- **Payload example owner**: setup payloads and run-start behavior belong in `product/main-app.md`; shared artifact fields belong in `contracts/`.
- **State example**: `completed_with_warnings` means the run is reviewable, but warnings still matter.
- **File ownership example**: provider-token truth belongs in current product/docs/tests/UI, not in `archive/verbatim/`.

## Historical archive

The historical archive is intentionally narrow.

- Keep verbatim preserved legacy files under `archive/verbatim/`.
- Do not treat historical files as a second current spec surface.
- Do not reintroduce annotated archive copies, migration ledgers, or parallel summary layers unless there is a concrete temporary migration need.

## Update rule

Any behavior change must update the owning current spec file in the same work pass.
