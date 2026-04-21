# AGENTS.md

## Purpose

Repository operating manual for papers-to-table.

The main product is a local-first paper-to-table review app that ingests PDFs plus a structured spreadsheet, generates evidence-backed cell proposals, supports human review in a browser UI, and exports audited XLSX updates.

## Must-follow rules

- Keep the browser UI as the primary operator surface for launch, status, review, and export.
- Keep the JSON config file as the authoritative advanced-control surface.
- Preserve the repo’s local-first identity even when optional cloud providers exist.
- Keep provider naming, readiness behavior, and degraded-mode truth aligned across runtime, tests, docs, specs, and UI labels.
- Unknown or obsolete provider identifiers must fail early and clearly.
- Silent fallback to demo, stub, disabled, or misleadingly “successful” behavior is not acceptable.
- Update docs, specs, tests, and screenshots in the same pass when repo truth changes.
- Keep archive material historical only; current behavior must be justified by current owning files.

## Default workflow

1. Read `README.md`, then the relevant docs/specs for the area you are changing.
2. Prefer the existing wrapper scripts in `scripts/` for install, run, test, and verification flows.
3. Implement the smallest coherent slice a normal operator can actually use.
4. Verify behavior, not only structure.
5. Leave the repository more truthful than you found it.

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

For this repo, “smallest coherent implementation” means the smallest slice a normal local operator can actually use from install and startup through run launch, run-state visibility, review, and export.

Do not treat any of the following as done:

- a backend-complete but operator-confusing slice
- a browser shell with vague or misleading empty/loading/failure states
- provider scaffolding that never proves the documented LM Studio path works
- a nominally completed run that cannot produce reviewer-usable proposals on the canonical fixture path
- a UI change that leaves screenshots and operator docs stale

Done means the operator can understand what to do next without reading source code, and the docs, UI, runtime behavior, tests, and screenshots agree on the same workflow.

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

- Current source of truth: `specs/README.md` for the spec-system guide, `specs/product/` for main-app product requirements, `specs/tools/` for companion-tool behavior, `specs/contracts/` for shared cross-tool rules, `specs/architecture/` for monorepo boundaries, `specs/process/` for maintenance policy, `specs/plan.md` for supportive planning, `specs/tasks.md` for verified implementation status, and this file for repo-level operating rules.
- When working inside `specs/`, follow `specs/AGENTS.md` for the spec-specific workflow.
- Update only the docs whose truth changed, but do it in the same pass as the behavior change.
- Remove stale text rather than letting old and new descriptions coexist.
- Preserve the existing canonical section structure when editing `README.md`, `AGENTS.md`, and files under `specs/`.
- Prefer editing the correct existing section over appending ad hoc notes.

## Repo map

- `README.md`: repo landing page and happy-path operator/developer entrypoint
- `CONTRIBUTING.md`: human-friendly contributor quickstart
- `docs/README.md`: docs map by audience
- `docs/main-app/`: main app operator and artifact docs
- `docs/screenshots/`: browser screenshots referenced by docs
- `docs/architecture-decisions/`: lightweight ADRs for durable repo decisions
- `specs/`: canonical normative/supportive spec system
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

## Compounding lessons

- Write a compounding lesson only when a bug, edge case, or workflow mistake reveals a reusable repo-level lesson.
- Keep them under `/docs/engineering-lessons`.
- Check existing lessons when you hit a suspicious repeat issue.

## Final rule

Leave the repository more truthful than you found it:

- code aligned with behavior
- tests aligned with code
- docs aligned with reality
- no stale remnants from older app versions
