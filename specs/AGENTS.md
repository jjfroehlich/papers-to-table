# AGENTS.md

## Scope

Applies to all files under `specs/`.

Use this file together with the root `AGENTS.md`. When they differ, this file is more specific for spec work.

## Spec Workflow

For spec-driven work, use this order:

1. `README.md`
2. the owning file under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/`
3. `plan.md`
4. `tasks.md`

If these artifacts conflict, fix the smallest coherent set of docs first before changing code or task status.

## Source-of-Truth Roles

- `product/`: main-app product behavior and user-facing requirements
- `tools/`: companion-tool behavior and scope
- `contracts/`: shared cross-tool contracts
- `architecture/`: monorepo layout and integration boundaries
- `process/`: change policy and testing strategy
- `archive/`: preserved historical, superseded, exploratory, and implementation-detail-heavy spec material
- `plan.md`: supportive planning index
- `tasks.md`: canonical implementation checklist and verified progress state

## Documentation Sync Rules

- Keep current implementation truth in one canonical place. Prefer `tasks.md` for status, with any separate audit doc serving as supporting evidence rather than a second progress tracker.
- Update only the spec docs whose truth actually changed, in the same pass as the related code or status change.
- Remove stale text rather than leaving both old and new descriptions in place.
- Preserve the existing canonical section structure of each spec file when editing.
- Prefer editing the correct existing section over appending an ad hoc note or temporary section.
- Do not insert pass-specific instructions, temporary status banners, or execution-order notes into normative spec files or `plan.md`.
- If historical or temporary context is worth keeping, place it in a clearly labeled appendix or supporting audit doc rather than in the main body.
- If older detail is being removed from a current spec because it is superseded, exploratory, or too implementation-specific, preserve it under `archive/` instead of deleting it silently.
- No major old section should disappear without an explicit disposition in `archive/migration-notes/legacy-section-mapping.md`.

## Task Discipline

- Treat `tasks.md` as canonical for implementation progress.
- A checked task is not proof of quality; validate the current app against the owning normative files, `plan.md`, and the relevant task completion standard.
- Do not create new batch or phase overlays in `tasks.md` unless explicitly asked.
- Do not mark a task area complete if startup truth, run-state visibility, review readiness, warning or failure states, or docs truth for that slice are still weak.
- Do not let later task areas excuse a hollow provider path in an earlier polished-looking shell.
- Historical task trackers can live in `archive/`, but they must never replace `tasks.md` as the current owner.

## Quality Standard for Spec Work

Spec text in this repo should make shallow rebuilds harder, not easier.

Keep the following explicit when relevant:

- browser-first operator workflow
- config file as the authoritative advanced-control surface
- truthful provider mode and readiness state
- canonical provider token and config parity across runtime, docs, tests, and UI
- early failure for broken local setup or unreachable providers
- real live-path proof on the canonical fixture path, or explicit readiness failure
- review and export behavior that a normal operator can understand without reading code

## Editing Guidance

- Prefer moving text to the document that owns it over restating the same rule in multiple places.
- Keep product requirements in `product/`, tool behavior in `tools/`, shared rules in `contracts/`, integration in `architecture/`, process policy in `process/`, and progress in `tasks.md`.
- Keep older rationale, alternatives, detailed technical notes, and superseded requirement language in `archive/` when it remains future-useful.
- When a file has accumulated scattered edits that weaken structure, reorganize it in the same pass instead of appending another patchwork section.
- Do not turn spec docs into vague governance prose.
- Do not widen product scope just to make an architecture section sound more flexible.
- Keep optional future extensions clearly secondary to the current MVP.

## Lossless migration guardrail

When reorganizing specs:

- prefer preservation plus labeling over deletion
- prefer archival relocation over summary-only compression
- update cross-links and mapping notes so future contributors can find the old material quickly