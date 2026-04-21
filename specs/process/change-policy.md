# Change Policy

- Status: Normative
- Owner: Process
- Depends on: specs/README.md
- Consumed by: contributors, coding agents

## Purpose

This file defines how behavior changes must update the monorepo spec system and adjacent docs.

## Core rule

Any behavior change must update the owning current file in the same work pass.

## Operational update checklists

### If you changed shared contracts

- update the owning file under `specs/contracts/`
- update any product/tool doc that points at renamed fields, directories, or semantics
- update tests for every impacted tool
- verify the affected runtime still emits or consumes the contract truthfully

### If you changed reviewer workflow

- update `specs/product/review-workflow.md`
- update `docs/main-app/operator-workflow.md`
- update screenshots if the workflow UI changed materially
- update frontend tests and any relevant e2e coverage

### If you changed provider behavior or readiness

- update `specs/product/main-app.md`
- update config docs/examples, UI labels, and tests
- verify runtime validation, persisted artifacts, summaries, and browser status surfaces agree
- confirm the live path either works or fails early with a clear readiness error

### If you changed run setup, launch, or automation behavior

- update `specs/product/main-app.md`
- update `README.md`, `docs/main-app/README.md`, and `docs/main-app/operator-workflow.md`
- update wrapper-script guidance if the happy path changed
- update backend/frontend tests and any relevant automation tests

### If you changed repo structure or integration boundaries

- update `specs/architecture/*.md`
- update repo maps in `README.md`, `AGENTS.md`, and any affected docs
- verify packaging, imports, scripts, and local startup commands together

## Anti-duplication rule

Do not solve drift by copying the same new truth into multiple files.

Move the truth to its owning file, replace stale references, and leave short pointers elsewhere.

## Conflict rule

If two files disagree, resolve the conflict by identifying the owning file and removing duplicated or conflicting text from the non-owning file.

## Historical-material rule

Do not solve current-spec drift by adding a second semi-current archive layer.

Keep current truth in the owning current file and keep historical wording in `archive/verbatim/` only.