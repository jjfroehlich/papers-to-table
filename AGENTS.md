# AGENTS.md

## Purpose

Repository operating manual for papers-to-table.

The main product is a local-first paper-to-table review app that ingests PDFs plus a structured spreadsheet, generates evidence-backed cell proposals, supports human review in a browser UI, and exports audited XLSX updates.

## Must-follow rules

- Keep the browser UI as the primary operator surface for launch, status, review, and export.
- Keep the JSON config file as the authoritative advanced-control surface.
- Preserve the repo's local-first identity even when optional cloud providers exist.
- Keep provider naming, readiness behavior, and degraded-mode truth aligned across runtime, tests, docs, specs, and UI labels.
- Unknown or obsolete provider identifiers must fail early and clearly.
- Silent fallback to demo, stub, disabled, or misleadingly "successful" behavior is not acceptable.
- Update docs, specs, tests, and screenshots in the same pass when repo truth changes.
- If code, specs, docs, tests, config examples, screenshots, or run artifacts disagree, fix the disagreement before calling the task done.
- Keep archive material historical only; current behavior must be justified by current owning files.

## Spec-driven development invariant

The specs are canonical implementation truth, not after-the-fact notes.

For any substantial change of: behavior, architecture, workflow, config, artifact, provider, UI, eval, optimizer, or CLI:

- update `specs/spec.md` plus the owning supporting spec in the same pass, or explicitly state why no spec update was needed
- keep specs detailed enough that a capable coding assistant could rebuild a similar app from the specs alone
- do not let implementation behavior exist only in code, tests, README, run artifacts, screenshots, or chat history
- do not add temporary notes to normative specs; promote durable truth into the correct owning spec section
- if current code and specs disagree, either fix the code or fix the specs before calling the work done

## Rebuild standard

Every current spec file should be written as rebuild-grade implementation guidance.

A reader should be able to understand:

- what the subsystem does
- its inputs and outputs
- its contracts and artifacts
- failure modes and diagnostics
- operator-visible behavior
- relevant config fields
- testing expectations

Do not accept vague descriptions like "handles extraction" when the real behavior has structured phases, artifacts, or contracts.

## Rule priority

If instructions conflict, use this order while honoring the most specific applicable `AGENTS.md`:

1. Safety and data integrity.
2. Correctness and truthful behavior.
3. Specs as source of truth.
4. Tests and verification.
5. Minimal, maintainable changes.
6. Consistency with repo conventions.
7. Performance and polish.

When sources conflict, identify the owning current spec, update code/docs/tests to match it, or update the owning spec first if the intended behavior has changed.

## Evidence-first workflow

1. Read `README.md`, `specs/README.md`, `specs/spec.md`, and the owning supporting spec before behavior changes.
2. Prefer the existing wrapper scripts in `scripts/` for install, run, test, and verification flows.
3. Trace the current code path before editing; do not rely on filenames or older docs alone.
4. Inspect relevant tests, fixtures, config examples, and run artifacts before changing behavior or declaring artifacts stale.
5. Distinguish a current-code bug from a stale artifact, stale screenshot, or stale doc mismatch.
6. Implement the smallest coherent slice a normal operator can actually use.
7. Verify behavior, not only structure.
8. Leave the repository more truthful than you found it.

Do not fabricate paths, config keys, commands, test results, model behavior, or run outcomes.

### Continue independently on large task bundles

When a task bundle is large but coherent:

- keep going independently through the full bundle
- solve adjacent issues revealed by the work when they are required for a coherent result
- do not stop after the first batch if the repo is still obviously mid-migration
- only stop for a true blocker, contradiction, missing secret, or safety issue
- prefer documenting the decision you made and continuing over asking for clarification on normal ambiguity

## Wrapper-script workflow

Use these as the default happy path unless the task specifically needs lower-level commands:

- repository-root wrapper scripts:
  - start backend: `bash scripts/run-main-backend.sh`
  - start frontend: `bash scripts/run-main-frontend.sh`
  - backend tests: `bash scripts/test-main-backend.sh`
  - frontend tests: `bash scripts/test-main-frontend.sh`
  - combined verification: `bash scripts/verify-main-app-full.sh`
  - minimum smoke pass: `bash scripts/verify-minimum-smoke.sh`
- install backend deps: `cd app && python -m pip install -e ./backend[test]`
- install frontend deps: `cd app/frontend && npm install`

## Definition of done

For this repo, "smallest coherent implementation" means the smallest slice a normal local operator can actually use from install and startup through run launch, run-state visibility, review, and export.

Do not treat any of the following as done:

- a backend-complete but operator-confusing slice
- a browser shell with vague or misleading empty/loading/failure states
- provider scaffolding that never proves the documented LM Studio path works
- a nominally completed run that cannot produce reviewer-usable proposals on the canonical fixture path
- a UI change that leaves screenshots and operator docs stale

Done means the operator can understand what to do next without reading source code, and the docs, UI, runtime behavior, tests, and screenshots agree on the same workflow.

### Completion checklist

- Behavior was changed or deliberately reviewed against the owning specs.
- `specs/spec.md` and the owning supporting spec were updated, or the final response states why no spec update was needed.
- README/manual docs were updated if operator or developer workflow changed.
- Config files, examples, fixtures, screenshots, and run-artifact expectations were updated if relevant.
- Tests were added or updated for changed behavior.
- The narrowest relevant verification command was run, or the final response states the exact gap.
- Stale paths, commands, provider names, and obsolete behavior claims were removed.
- No secrets, machine-local absolute paths, or local-only assumptions were introduced.

## Verification expectations

- Verify behavior; do not stop at structural correctness.
- Prefer integration and end-to-end validation when the repo supports it.
- For UI-affecting work, browser-level verification or equivalent e2e coverage is part of done.
- Preflight and readiness checks are part of done, not polish.
- Provider-affecting work must verify parity across runtime validation, config examples, docs, tests, and UI summaries.
- A documented live path is not done unless it either:
  - produces at least one non-empty proposal with reviewer-usable evidence on the canonical checked-in fixture path, or
  - fails early with a clear readiness error explaining why proposal generation cannot proceed.

## Documentation and spec rules

- Current source of truth: `specs/README.md` for the spec-system guide, `specs/spec.md` for integrated current product/system truth, `specs/product/` for main-app product requirements, `specs/tools/` for companion-tool behavior, `specs/contracts/` for shared cross-tool rules, `specs/architecture/` for monorepo boundaries, `specs/process/` for maintenance policy, `specs/plan.md` for supportive planning, `specs/tasks.md` for verified implementation status, and this file for repo-level operating rules.
- When working inside `specs/`, follow `specs/AGENTS.md` for the spec-specific workflow.
- `README.md` is the short repo entry point. `docs/` is the MkDocs manual for operators, agents, and developers. `specs/` is canonical implementation truth. 
- Update only the docs whose truth changed, but do it in the same pass as the behavior change.
- When adding, removing, or renaming manual pages, update `tools/docs/mkdocs.yml` navigation in the same pass.
- Remove stale links when moving docs pages.
- Keep docs/test tooling optional or dev-scoped when possible; do not make manual-building dependencies part of the runtime path unless the app requires them.
- Remove stale text rather than letting old and new descriptions coexist.
- Preserve the existing canonical section structure when editing `README.md`, `AGENTS.md`, and files under `specs/`.
- Prefer editing the correct existing section over appending ad hoc notes.
- If `agent-skills/` procedures change, update the corresponding manual page under `/docs/tools/papers-to-table-skill.md` and keep skill references aligned with current CLI/config/artifact truth.

## Dependency policy

- Keep runtime dependencies minimal and local-first.
- Before adding a dependency, check whether an existing dependency or standard-library solution is enough.
- Prefer optional/dev dependencies for docs, tests, diagnostics, and one-off tooling.
- Document why every new dependency exists in the relevant install docs, requirements/package file, and owning spec when behavior depends on it.
- Update lockfiles/configs consistently when dependency metadata changes.
- Validate the narrowest relevant install/build/test path affected by dependency changes.

## Git and change safety

- Do not commit, push, rebase, reset, clean, force-update branches, or rewrite history unless explicitly asked.
- Do not run destructive commands or delete/rename unexpected generated, historical, or user-owned files without explicit permission.
- Treat unrecognized worktree changes as possibly belonging to another user or agent; work around them and keep edits scoped.
- Prefer editing the owning file over adding duplicate new files.
- Do not hide behavior changes in formatting churn or unrelated cleanup.

## Repo map

- `README.md`: repo landing page and happy-path operator/developer entrypoint
- `docs/main-app/`: main app operator and artifact docs
- `docs/screenshots/`: browser screenshots referenced by docs
- `specs/`: canonical normative/supportive spec system
- `agent-skills/`: agent operating procedures for installed skill workflows
- `app/tests/fixtures/`: canonical workbook and PDF fixtures
- `app/backend/src/backend/app/`: FastAPI app, pipeline logic, and runtime services
- `app/frontend/`: React review UI
- `tools/eval/`: evaluator tool
- `tools/optimizer/`: optimizer tool

## Platform and conventions

- Primary environment is Windows.
- Preferred shell is Git Bash on Windows; use bash-friendly commands in docs and scripts.
- Do not use PowerShell in repo docs unless there is a separate audience that truly needs it.
- Prefer relative paths in docs. If absolute paths are required, document both `/d/...` and `D:\...` forms.
- Canonical fixture root: `app/tests/fixtures/`.

## Commit Message Helper

When making or planning code changes, keep the draft commit message in
`D:\code\notes\git_commit_-_papers-to-table.sh` up to date.

Rules:
- Update the draft `git commit -m "..."` message so it accurately summarizes the current uncommitted changes.
- Keep the commit subject concise, preferably under ~72 characters.
- Limit the subject line to 50 characters.
- Capitalize only the first letter in the subject line.
- Insert a blank line between the subject line and the body.
- Don't put a period at the end of the subject line.
- Use a conventional prefix when practical, e.g. `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, or `chore:`.
- Use `!` for intentional breaking changes, e.g. `refactor!: replace legacy proposal semantics`.
- Keep the commit body short: usually 3–6 bullet points.
- If the existing draft message has grown too long or stale, summarize/edit it instead of appending indefinitely.
- Use the imperative mood.
- Describe what was done and why, but not how.
- Do not commit automatically unless explicitly asked; only keep the script ready for the user to run.

## Final rule

Leave the repository more truthful than you found it:

- code aligned with behavior
- tests aligned with code
- docs aligned with reality
- no stale remnants from older app versions
