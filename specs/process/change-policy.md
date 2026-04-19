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
- If operator-facing workflow or terminology changes, update the relevant docs in the same pass so operator documentation does not drift behind the spec and app.

## Anti-duplication rule

Do not solve drift by copying the same new truth into multiple files.

Move the truth to its owning file, replace stale references, and leave short pointers elsewhere.

## Conflict rule

If two files disagree, resolve the conflict by identifying the owning file and removing duplicated or conflicting text from the non-owning file.

## Historical-material rule

Do not solve current-spec drift by adding a second semi-current archive layer.

Keep current truth in the owning current file and keep historical wording in `archive/verbatim/` only.