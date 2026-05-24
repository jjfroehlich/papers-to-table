# AGENTS.md

## Scope

Applies to all files under `specs/`.

Use this file together with the root `AGENTS.md`. When they differ, this file is more specific for spec work.

## Non-negotiable invariant

- `spec.md`, `plan.md`, and `tasks.md` are the canonical markdown truth for this repo; `contracts/schemas/*.json` are the canonical machine-readable contracts.
- Specs must be rebuild-grade: a capable coding assistant should be able to rebuild a similar app from the canonical specs alone.
- Substantial behavior, architecture, config, artifact, UI, eval, optimizer, or CLI changes must update the relevant canonical file in the same pass, or the final response must state why no spec update was needed.
- README and MkDocs pages may summarize operator workflows, but they must not become the only source of implementation truth.
- If specs, code, docs, tests, config examples, screenshots, or run artifacts disagree, fix the disagreement before marking spec work done.

## Priority and conflicts

Within `specs/`, use this priority order:

1. Current user request, when it preserves truthful current behavior.
2. Root `AGENTS.md` and this file.
3. `spec.md`, `plan.md`, and `tasks.md`.
4. JSON schemas under `contracts/schemas/`.
5. Compatibility references under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/`.
6. Archive material as historical context only.

When files conflict, update the smallest coherent canonical set. Do not let a README, manual page, compatibility reference, task checkbox, or archived note override current implementation truth.

## Spec workflow

For spec-driven work, use this order:

1. `spec.md`
2. `plan.md`
3. `tasks.md`
4. compatibility references under `product/`, `tools/`, `contracts/`, `architecture/`, or `process/` only when they are still linked from active docs or needed to avoid stale claims

If these artifacts conflict, fix the smallest coherent set of docs first before changing code or task status.

Before changing canonical spec text, inspect the current code path, relevant tests/fixtures, and run artifacts when they affect the claim. Distinguish current-code bugs from stale artifact mismatches.

## Source-of-truth roles

- `product/`: compatibility references for older focused product slices
- `tools/`: compatibility references for older companion-tool behavior notes
- `contracts/`: compatibility references plus current machine-readable `schemas/`
- `architecture/`: compatibility references for older layout and integration notes
- `process/`: compatibility references for older change and testing notes
- `archive/verbatim/`: preserved historical legacy material only
- `plan.md`: supportive technical-direction summary
- `tasks.md`: canonical implementation checklist and verified progress state

## Experiment and improvement docs

- `experiment-results.md` owns tested evidence, eval results, dev-check outcomes that changed a decision, and kept, partially kept, rejected, or superseded idea decisions. It should not become a broad run log or current-recommendation page.
- `improvement-ideas.md` owns prioritized untested or not-yet-resolved ideas.
- Do not recreate `extraction-improvement-backlog.md`, `extraction-experiment-results.md`, or `extraction-improvement-ideas.md`; they are superseded by the more general filenames above.
- When recording optimizer or eval results, include model IDs or source labels alongside candidate IDs. Do not write only `cand_0001`; write a form like `cand_0001 / google/gemma-4-e4b`.
- Keep result and idea entries within the length bands documented in those files unless a longer entry is needed for a broad benchmark comparison.
- When an idea is implemented, benchmarked, rejected, or ruled out conceptually, move the evidence to `experiment-results.md` and update or remove the corresponding idea.
- Update stale references when extraction improvement files are renamed, consolidated, or split.
- Updates and improvements to the app still must be reflected by the specs, if necessary update specs. 

## Current-file rule

- Current files must be understandable without consulting archive material.
- Archive files may preserve history, superseded rationale, or verbatim legacy wording.
- Archive files must never justify current behavior unless the necessary truth has been promoted into the current owning file.
- If a current behavior still depends on an archived statement, promote that statement into the current owning file and then treat the archive copy as background only.

## Documentation sync rules

- Keep current implementation truth in `spec.md`, with `plan.md` for direction and `tasks.md` for verified status.
- Update only the spec docs whose truth actually changed, in the same pass as the related code or status change.
- Remove stale text rather than leaving both old and new descriptions in place.
- Preserve the existing canonical section structure of each spec file when editing.
- Prefer editing the correct existing section over appending an ad hoc note or temporary section.
- Do not insert pass-specific instructions, temporary status banners, or execution-order notes into canonical spec files or `plan.md`.
- When operator or developer workflow changes, ensure the related README/MkDocs manual page is updated by the same work pass.
- When manual pages are added, removed, or renamed, ensure `tools/docs/mkdocs.yml` navigation is updated outside `specs/`.

## Task discipline

- Treat `tasks.md` as canonical for implementation progress.
- A checked task is not proof of quality; validate the current app against the canonical files and the relevant task completion standard.
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
- `spec.md`, `plan.md`, and `tasks.md` agree with the current implementation and with any touched compatibility references.
- README/manual docs are updated if workflow changed, and `tools/docs/mkdocs.yml` is updated if docs navigation changed.
- Config examples, commands, artifact paths, provider names, and task status remain current.
- Stale or contradictory text was removed rather than duplicated.
- Verification was run, or the remaining verification gap is stated.
- No secrets, machine-local absolute paths, or local-only assumptions were introduced.
