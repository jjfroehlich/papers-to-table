# Change Policy

## Purpose

This file defines how behavior changes must update the monorepo spec system.

## Policy

Any behavior change must update the relevant spec file or files in the same work pass.

## Required update rules

- Main-app behavior change: update the owning file in `product/` and any affected shared contract in `contracts/`.
- Eval change: update `tools/eval.md` for tool-owned behavior and update `contracts/` when the change affects shared artifact, metric, or provenance contracts.
- Optimizer change: update `tools/optimizer.md` for tool-owned behavior and update `contracts/` when the change affects shared scorer or candidate contracts.
- Integration change: update `architecture/integration.md` and any affected `contracts/` file together.
- Testing or verification policy change: update `process/testing-strategy.md`.
- Implementation status change: update `tasks.md`.

## Anti-duplication rule

Do not solve drift by copying the same new truth into multiple files.

Move the truth to its owning file, replace stale references, and leave short pointers elsewhere.

## Conflict rule

If two files disagree, resolve the conflict by identifying the owning file and removing duplicated or conflicting text from the non-owning file.