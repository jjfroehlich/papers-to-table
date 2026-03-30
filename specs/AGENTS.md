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
- `tasks.md`: canonical implementation checklist and batch structure

## Documentation Sync Rules

- Update only the spec docs whose truth actually changed, but do it in the same pass.
- If user-facing behavior changes, update `spec.md`.
- If architecture, runtime shape, parser strategy, UI stack, persistence strategy, or sequencing changes, update `plan.md`.
- If a decision changed because the tradeoff or rationale changed, update `research.md`.
- If spec-driven execution progress changed, keep `tasks.md` aligned.
- Remove stale text rather than leaving both old and new descriptions in place.

## Batch Discipline

- Treat `tasks.md` as canonical for implementation progress.
- A checked task is not proof of quality; validate the current app against `spec.md`, `plan.md`, and the active batch completion standard.
- Implement one batch deeply rather than many batches shallowly.
- Do not mark a batch complete if startup truth, run-state visibility, review readiness, warning or failure states, or docs truth for that slice are still weak.
- Do not let a later batch excuse a hollow provider path in an earlier polished-looking shell.

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

- Prefer additive sharpening over deleting useful repo-specific detail.
- Compress repetition when the same rule is already stated clearly once.
- Do not turn spec docs into vague governance prose.
- Do not widen product scope just to make an architecture section sound more flexible.
- Keep optional future extensions clearly secondary to the current MVP.