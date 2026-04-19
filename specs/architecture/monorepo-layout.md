# Monorepo Layout

## Purpose

This file defines the normative layout and role boundaries for the monorepo.

## Product and tool roles

- `app/` contains the primary product: the main extraction, review, and export application.
- `tools/eval/` contains the internal scoring tool.
- `tools/optimizer/` contains the internal orchestration tool.
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