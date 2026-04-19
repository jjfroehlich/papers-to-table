# AGENTS.md

## Purpose

Durable editing and verification rules for coding agents working in this repository.

## Scope boundaries

- Preserve strict role separation:
  - main app = execution
  - eval app = scoring
  - optimizer = orchestration
- Do not move extraction/scoring logic into optimizer docs or code unless explicitly requested as a product change.

## Canonical spec roles

- `../../specs/tools/optimizer.md`: stable optimizer behavior and scope only.
- `../../specs/contracts/`: shared cross-tool contracts.
- `../../specs/architecture/`: monorepo structure and integration boundaries.
- `../../specs/process/`: change and testing policy.
- `../../specs/tasks.md`: canonical implementation checklist and status tracking only.
- `README.md`: operator-facing workflow and current behavior/limitations only.

## Editing rules for spec files

1. Preserve existing canonical section structure when editing spec files.
2. Prefer editing the correct existing section over appending ad hoc sections.
3. Do not insert pass-specific, temporary, or sequencing instructions into the unified root spec files or `../../specs/plan.md`.
4. Do not create new batch/phase frameworks unless explicitly requested.
5. Keep implementation status in `../../specs/tasks.md` only.
6. Do not leave stale and new truths side by side; replace stale statements in the same pass.
7. If historical notes are useful, place them in an appendix, not in canonical body sections.
8. If a file accumulates scattered edits, reorganize it in the same pass instead of only appending.

## Editing rules for tasks

1. Keep one canonical checked/unchecked checklist in `../../specs/tasks.md`.
2. Keep each task listed exactly once.
3. Organize tasks by durable product area, not historical implementation order.
4. Keep completed tasks visible.
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
