# Testing Strategy

## Purpose

This file defines the cross-monorepo testing strategy that keeps the unified spec system truthful.

## Main-app testing expectations

Main-app changes should preserve:

- backend unit and integration coverage
- frontend test coverage
- Playwright coverage for key reviewer workflows where the repo already supports it
- readiness and live-path truth for provider-sensitive changes

## Eval testing expectations

Eval changes should preserve:

- loader and contract tests for run-bundle compatibility
- scorer tests for deterministic structured fields
- judge-path tests for text scoring
- end-to-end CLI coverage for one-run and many-run workflows

## Optimizer testing expectations

Optimizer changes should preserve:

- config and contract validation tests
- launch-contract tests for main-app and eval integration
- compare and optimize orchestration tests
- summary and regeneration coverage for persisted artifacts

## Cross-tool regression rule

Any change that affects a shared contract in `contracts/` must verify all impacted tools, not only the tool where the change was implemented.

At minimum, that means validating:

- main-app artifact emission when run-bundle or proposal-evidence contracts change
- eval loading and scoring when run-bundle or summary contracts change
- optimizer ingestion and reporting when eval-summary or candidate contracts change

## Documentation-verification rule

Operator docs, spec docs, commands, artifact names, and persisted fields should be verified together when a change touches operator-facing or cross-tool behavior.