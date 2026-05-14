# Monorepo Layout

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Do not treat this file as normative when it conflicts with the canonical files.

- Status: Compatibility reference
- Owner: Architecture
- Depends on: README.md, AGENTS.md
- Consumed by: contributors, coding agents, docs/README.md

## Purpose

This file preserves compatibility notes for monorepo layout and role boundaries. Canonical layout and role behavior lives in `../spec.md`.

## Product and tool roles

- `app/` contains the primary product: the main extraction, review, and export application.
- `app/backend/src/backend/app/` is the canonical Python package root for the backend runtime.
- `app/frontend/src/` is the canonical source root for the browser UI.
- `tools/eval/` contains the internal scoring tool.
- `tools/optimizer/` contains the internal orchestration tool.
- `docs/` contains the operator/developer manual source (Markdown + MkDocs navigation).
- `agent-skills/` contains reusable external agent operating procedures.
- `specs/` contains the canonical spec system for all three surfaces.

## Spec ownership model

There is one canonical spec root for the entire monorepo: `specs/`.

Per-tool nested `specs/` directories are not part of the canonical design.

## Directory responsibilities

- `product/`: main-app product behavior
- `tools/`: companion-tool behavior
- `contracts/`: shared cross-tool contracts
- `architecture/`: structure and integration boundaries
- `process/`: maintenance and verification policy
- `plan.md`: supportive planning index
- `tasks.md`: canonical implementation status

## Layout rule

If a truth applies across more than one tool, it must be owned once in `contracts/` or `architecture/`, not duplicated in multiple tool docs.
