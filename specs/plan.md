# Technical direction

## Purpose

This file describes the current architecture direction and near-term roadmap for the monorepo.

## Current architecture

### Main app

- backend: FastAPI plus stable run-bundle artifact writing
- frontend: React review UI
- automation: stable terminal entrypoint for preflight, start, status, wait, and headless workflows

### Companion tools

- eval reads run bundles and writes score artifacts
- optimizer launches repeated main-app and eval studies from explicit configs

## Direction

### Usability and operability

- keep one obvious repo-level command surface
- keep install, review startup, headless mode, eval, and optimizer discoverable from one place
- keep browser-first human workflow and config authority intact

### Contract clarity

- keep run bundles consumable from files alone
- keep auto-accept and degraded-mode truth visible in summaries and audit artifacts
- keep config families clearly labeled by purpose and benchmark intent

### Documentation and specs

- keep README concise and task-oriented
- keep docs navigable from a single central index and local/static MkDocs Material site
- keep `spec.md` as the canonical product/system truth
- keep `plan.md` limited to roadmap and technical direction
- keep `tasks.md` limited to verified status and backlog
- keep JSON schemas under `contracts/schemas/` as the machine-readable contracts
- retire or pointer-replace older normative-looking markdown after downstream links have been updated
- keep external agent usage guidance compact through reusable skill packages:
  - a local-app skill for installed app/headless/LM Studio workflows
  - a portable agent kit for loose agent-native extraction with optional static review/export packaging

### Local model operations

- prefer stable serialized LM Studio use over parallel local throughput
- keep model load/unload/completion phases explicit across main app, eval, and optimizer
- keep timeout, lock, and model-management diagnostics visible in artifacts

## Near-term roadmap

- expand focused validation for docs-referenced commands and presets
- harden the portable agent kit around review/export helper boundaries without turning it into a second app
- keep screenshots aligned with UI truth when the review workflow changes
- continue reducing stale or personal-path assumptions inside benchmark presets
- finish archiving or pointer-replacing older scattered spec markdown once links are clean
