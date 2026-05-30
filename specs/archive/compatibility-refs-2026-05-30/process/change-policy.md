# Change Policy

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Do not treat this file as normative when it conflicts with the canonical files.

- Status: Compatibility reference
- Owner: Process
- Depends on: specs/README.md
- Consumed by: contributors, coding agents

## Purpose

This file defines how behavior changes must update the monorepo spec system and adjacent docs.

## Core rule

Any behavior change must update `spec.md`, `plan.md`, or `tasks.md` in the same work pass when the change affects durable behavior, direction, or status.

## Operational update checklists

### If you changed shared contracts

- update `spec.md` and any affected schema under `specs/contracts/schemas/`
- update any product/tool doc that points at renamed fields, directories, or semantics
- update tests for every impacted tool
- verify the affected runtime still emits or consumes the contract truthfully

### If you changed reviewer workflow

- update `specs/spec.md`
- update `docs/main-app/browser-review.md`
- update screenshots if the workflow UI changed materially
- update frontend tests and any relevant e2e coverage

### If you changed provider behavior or readiness

- update `specs/spec.md`
- update config docs/examples, UI labels, and tests
- verify runtime validation, persisted artifacts, summaries, and browser status surfaces agree
- confirm the live path either works or fails early with a clear readiness error

### If you changed run setup, launch, or automation behavior

- update `specs/spec.md`
- update `README.md` and `docs/main-app/browser-review.md`
- update wrapper-script guidance if the happy path changed
- update backend/frontend tests and any relevant automation tests

### If you changed repo structure or integration boundaries

- update `specs/spec.md` and `specs/plan.md` when the direction changes
- update repo maps in `README.md`, `AGENTS.md`, and any affected docs
- verify packaging, imports, scripts, and local startup commands together

## Anti-duplication rule

Do not solve drift by copying the same new truth into multiple files.

Move the truth to the canonical file, replace stale references, and leave short pointers elsewhere.

## Conflict rule

If two files disagree, resolve the conflict by using `spec.md`, `plan.md`, `tasks.md`, or JSON schemas as canonical and removing duplicated or conflicting text from compatibility references.

## Historical-material rule

Do not solve current-spec drift by adding a second semi-current archive layer.

Keep current truth in the canonical files and keep historical wording in `archive/verbatim/` only.
