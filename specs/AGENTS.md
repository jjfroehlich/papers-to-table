# AGENTS.md

## Scope

Applies to all files under `specs/`.

Use this file together with the root `AGENTS.md`. When they differ, this file is more specific for spec work.

## Spec workflow

For spec-driven work, use this order:

1. `README.md`
2. the owning file under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/`
3. `plan.md`
4. `tasks.md`

If these artifacts conflict, fix the smallest coherent set of docs first before changing code or task status.

## Source-of-truth roles

- `product/`: main-app product behavior and user-facing requirements
- `tools/`: companion-tool behavior and scope
- `contracts/`: shared cross-tool contracts
- `architecture/`: monorepo layout and integration boundaries
- `process/`: change policy and testing strategy
- `archive/verbatim/`: preserved historical legacy material only
- `plan.md`: supportive technical-direction summary
- `tasks.md`: canonical implementation checklist and verified progress state

## Current-file rule

- Current files must be understandable without consulting archive material.
- Archive files may preserve history, superseded rationale, or verbatim legacy wording.
- Archive files must never justify current behavior unless the necessary truth has been promoted into the current owning file.
- If a current behavior still depends on an archived statement, promote that statement into the current owning file and then treat the archive copy as background only.

## Documentation sync rules

- Keep current implementation truth in one canonical place.
- Update only the spec docs whose truth actually changed, in the same pass as the related code or status change.
- Remove stale text rather than leaving both old and new descriptions in place.
- Preserve the existing canonical section structure of each spec file when editing.
- Prefer editing the correct existing section over appending an ad hoc note or temporary section.
- Do not insert pass-specific instructions, temporary status banners, or execution-order notes into normative spec files or `plan.md`.
- If historical or temporary context is worth keeping, place it in a clearly labeled appendix or supporting audit doc rather than in the main body.

## Task discipline

- Treat `tasks.md` as canonical for implementation progress.
- A checked task is not proof of quality; validate the current app against the owning normative files, `plan.md`, and the relevant task completion standard.
- Do not create new batch or phase overlays in `tasks.md` unless explicitly asked.
- Historical task trackers can live in `archive/`, but they must never replace `tasks.md` as the current owner.

## Quality standard for spec work

Spec text in this repo should make shallow rebuilds harder, not easier.

Keep the following explicit when relevant:

- browser-first operator workflow
- config file as the authoritative advanced-control surface
- truthful provider mode and readiness state
- canonical provider token and config parity across runtime, docs, tests, and UI
- early failure for broken local setup or unreachable providers
- real live-path proof on the canonical fixture path, or explicit readiness failure
- review and export behavior that a normal operator can understand without reading code
