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
- keep docs navigable from a single central index
- keep `spec.md` as the integrated current truth
- keep research, plan, and tasks separate from normative product behavior

## Near-term roadmap

- expand focused validation for docs-referenced commands and presets
- keep screenshots aligned with UI truth when the review workflow changes
- continue reducing stale or personal-path assumptions inside benchmark presets
