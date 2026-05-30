# AGENTS.md

## Purpose

Durable editing and verification rules for coding agents working in this repository.

## Scope boundaries

- Preserve strict role separation:
  - main app = execution
  - eval app = scoring
  - optimizer app = orchestration
- Do not move extraction/scoring logic into optimizer docs or code unless explicitly requested as a product change.

## Canonical spec roles

- `../../specs/spec.md`: integrated product and system truth.
- `../../specs/eval-and-optimizer.md`: stable eval and optimizer behavior, benchmark policy, suite/replicate behavior, and report semantics.
- `../../specs/contracts.md`: shared human-readable cross-tool contracts.
- `../../specs/contracts/schemas/`: machine-readable artifact contracts.
- `../../specs/architecture.md`: monorepo structure and integration boundaries.
- `../../specs/decisions.md`: durable decisions.
- `../../specs/improvement-ideas.md`: active untested or unresolved improvement ideas.
- `../../specs/experiment-results.md`: tested evidence and decisions for improvement ideas.
- `../../specs/tasks.md`: living current backlog/status only.
- `README.md`: operator-facing workflow and current behavior/limitations only.

## Editing rules for spec files

1. Preserve existing canonical section structure when editing spec files.
2. Prefer editing the correct existing section over appending ad hoc sections.
3. Do not insert pass-specific, temporary, or sequencing instructions into the unified root spec files or `../../specs/plan.md`.
4. Do not create new batch/phase frameworks unless explicitly requested.
5. Keep current implementation status in `../../specs/tasks.md` only.
6. Do not leave stale and new truths side by side; replace stale statements in the same pass.
7. If historical notes are useful, place them under `../../specs/archive/`, not in canonical body sections.
8. If a file accumulates scattered edits, reorganize it in the same pass instead of only appending.

## Editing rules for tasks

1. Keep one canonical checked/unchecked checklist in `../../specs/tasks.md`.
2. Keep each task listed exactly once.
3. Organize tasks by durable product area, not historical implementation order.
4. Keep only recently verified completed tasks visible.
5. Reclassify task status when repo truth changes.

## Verification requirements for truth edits

When editing status-bearing docs (`../../specs/tasks.md`, `README.md`):

1. Re-audit relevant implementation files and tests.
2. Verify command examples match real CLI arguments.
3. Verify artifact names/paths match current code.
4. Verify study-mode behavior matches current implementation.
5. Record known gaps explicitly rather than implying completion.

## Drift prevention checklist

Before finishing a spec/doc pass:

1. Confirm no `## Status` or similar transient banners remain in stable spec docs.
2. Confirm status truth appears in one canonical place (`../../specs/tasks.md`).
3. Confirm no duplicated policy statements are spread across all docs unnecessarily.
4. Confirm `README.md` remains truthful to current code behavior and limitations.

## Run-bundle relationship
Eval is a consumer of main-app contracts; it does not create or mutate run bundles.
Optimizer orchestrates main-app runs and eval scoring; it does not reimplement extraction or scoring logic.
