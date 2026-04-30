# AGENTS.md

## Scope

Applies to all files under `specs/`.

Use this file together with the root `AGENTS.md`. When they differ, this file is more specific for spec work.

## Non-negotiable invariant

- Specs are the canonical implementation truth for this repo.
- Specs must be rebuild-grade: a capable coding assistant should be able to rebuild a similar app from the current specs alone.
- Substantial behavior, architecture, config, artifact, UI, eval, optimizer, or CLI changes must update `spec.md` plus the owning supporting spec in the same pass, or the final response must state why no spec update was needed.
- README and MkDocs pages may summarize operator workflows, but they must not become the only source of implementation truth.
- If specs, code, docs, tests, config examples, screenshots, or run artifacts disagree, fix the disagreement before marking spec work done.

## Priority and conflicts

Within `specs/`, use this priority order:

1. Current user request, when it preserves truthful current behavior.
2. Root `AGENTS.md` and this file.
3. `specs/README.md` and `spec.md`.
4. Owning files under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/`.
5. `plan.md`, then `tasks.md`.
6. Archive material as historical context only.

When files conflict, update the smallest coherent set around the owning current spec. Do not let a README, manual page, task checkbox, or archived note override current implementation truth.

## Spec workflow

For spec-driven work, use this order:

1. `README.md`
2. `spec.md`
3. the owning file under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/`
4. `plan.md`
5. `tasks.md`

If these artifacts conflict, fix the smallest coherent set of docs first before changing code or task status.

Before changing normative spec text, inspect the current code path, relevant tests/fixtures, and run artifacts when they affect the claim. Distinguish current-code bugs from stale artifact mismatches.

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

- Keep current implementation truth in the owning spec, with `spec.md` carrying the integrated current picture.
- Update only the spec docs whose truth actually changed, in the same pass as the related code or status change.
- Remove stale text rather than leaving both old and new descriptions in place.
- Preserve the existing canonical section structure of each spec file when editing.
- Prefer editing the correct existing section over appending an ad hoc note or temporary section.
- Do not insert pass-specific instructions, temporary status banners, or execution-order notes into normative spec files or `plan.md`.
- If historical or temporary context is worth keeping, place it in a clearly labeled appendix or supporting audit doc rather than in the main body.
- When operator or developer workflow changes, ensure the related README/MkDocs manual page is updated by the same work pass.
- When manual pages are added, removed, or renamed, ensure `tools/docs/mkdocs.yml` navigation is updated outside `specs/`.

## Task discipline

- Treat `tasks.md` as canonical for implementation progress.
- A checked task is not proof of quality; validate the current app against the owning normative files, `plan.md`, and the relevant task completion standard.
- Do not create new batch or phase overlays in `tasks.md` unless explicitly asked.
- Historical task trackers can live in `archive/`, but they must never replace `tasks.md` as the current owner.

## Quality standard for spec work

Spec text in this repo should make shallow rebuilds harder, not easier. Prefer explicit contracts, states, commands, artifact paths, failure modes, and verification expectations over broad intent statements.

Keep the following explicit when relevant:

- browser-first operator workflow
- config file as the authoritative advanced-control surface
- truthful provider mode and readiness state
- canonical provider token and config parity across runtime, docs, tests, and UI
- early failure for broken local setup or unreachable providers
- real live-path proof on the canonical fixture path, or explicit readiness failure
- review and export behavior that a normal operator can understand without reading code

## Spec completion checklist

- Behavior was checked against current code, tests/fixtures, and relevant artifacts.
- `spec.md` and the owning supporting spec agree.
- README/manual docs are updated if workflow changed, and `tools/docs/mkdocs.yml` is updated if docs navigation changed.
- Config examples, commands, artifact paths, provider names, and task status remain current.
- Stale or contradictory text was removed rather than duplicated.
- Verification was run, or the remaining verification gap is stated.
- No secrets, machine-local absolute paths, or local-only assumptions were introduced.
