# AGENTS.md

## Scope

Applies to all files under `specs/`.

Use this file together with the root `AGENTS.md`. When they differ, this file is more specific for spec work.

## Spec Workflow

For spec-driven work, use this order:

1. `spec.md`
2. `plan.md`
3. `tasks.md`

If these artifacts conflict, fix the smallest coherent set of docs first before changing code or task status.

## Source-of-Truth Roles

- `spec.md`: product behavior, user-facing requirements, acceptance criteria
- `plan.md`: technical architecture and implementation direction
- `research.md`: decisions, tradeoffs, evidence, deferred questions
- `tasks.md`: canonical implementation checklist and verified progress state

## Documentation Sync Rules

- Keep current implementation truth in one canonical place. Prefer `tasks.md` for status, with any separate audit doc serving as supporting evidence rather than a second progress tracker.
- Update only the spec docs whose truth actually changed, in the same pass as the related code or status change.
- Remove stale text rather than leaving both old and new descriptions in place.
- Preserve the existing canonical section structure of each spec file when editing.
- Prefer editing the correct existing section over appending an ad hoc note or temporary section.
- Do not insert pass-specific instructions, temporary status banners, or execution-order notes into `spec.md`, `plan.md`, or `research.md`.
- If historical or temporary context is worth keeping, place it in a clearly labeled appendix or supporting audit doc rather than in the main body.

## Task Discipline

- Treat `tasks.md` as canonical for implementation progress.
- A checked task is not proof of quality; validate the current app against `spec.md`, `plan.md`, and the relevant task completion standard.
- Do not create new batch or phase overlays in `tasks.md` unless explicitly asked.
- Do not mark a task area complete if startup truth, run-state visibility, review readiness, warning or failure states, or docs truth for that slice are still weak.
- Do not let later task areas excuse a hollow provider path in an earlier polished-looking shell.

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
- Keep product requirements in `spec.md`, architecture in `plan.md`, rationale in `research.md`, and progress in `tasks.md`.
- When a file has accumulated scattered edits that weaken structure, reorganize it in the same pass instead of appending another patchwork section.
- Do not turn spec docs into vague governance prose.
- Do not widen product scope just to make an architecture section sound more flexible.
- Keep optional future extensions clearly secondary to the current MVP.