# Testing Strategy

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Do not treat this file as normative when it conflicts with the canonical files.

- Status: Compatibility reference
- Owner: Process
- Depends on: process/change-policy.md
- Consumed by: contributors, coding agents

## Purpose

This file defines the cross-monorepo testing strategy that keeps the unified spec system truthful.

## Main-app testing expectations

Main-app changes should preserve:

- backend unit and integration coverage
- frontend test coverage
- Playwright coverage for key reviewer workflows where the repo already supports it
- readiness and live-path truth for provider-sensitive changes
- screenshot capture coverage when operator screenshots are part of the docs

## Operational verification checklists

### If you changed shared contracts

- run the impacted main-app tests
- run eval tests if run-bundle, proposal/evidence, or summary contracts changed
- run optimizer tests if eval-summary or candidate contracts changed
- verify changed docs and examples still match emitted artifacts

### If you changed backend runtime or API behavior

- run `bash scripts/test-main-backend.sh`
- run targeted tests for changed endpoints/modules
- verify startup commands and automation entrypoints if those changed

### If you changed frontend workflow or styling

- run `bash scripts/test-main-frontend.sh`
- run or update e2e coverage for materially changed flows when available
- refresh screenshots when docs images became stale

### If you changed provider behavior

- verify config validation and readiness tests
- verify UI/provider summary parity
- verify persisted artifacts and summaries reflect the same provider truth

### If you changed packaging or startup layout

- verify install commands
- verify backend startup, frontend startup, and wrapper scripts together
- verify imports and editable installs on the new layout

### If you changed documentation structure or docs tooling

- run `python scripts/papers_to_table.py docs build`
- fix broken nav links or missing pages before finalizing
- verify README and docs command examples still match the real CLI surface

## Cross-tool regression rule

Any change that affects a shared contract in `contracts/` must verify all impacted tools, not only the tool where the change was implemented.

At minimum, that means validating:

- main-app artifact emission when run-bundle or proposal-evidence contracts change
- eval loading and scoring when run-bundle or summary contracts change
- optimizer ingestion and reporting when eval-summary or candidate contracts change

## Documentation-verification rule

Operator docs, spec docs, commands, artifact names, screenshots, and persisted fields should be verified together when a change touches operator-facing or cross-tool behavior.
