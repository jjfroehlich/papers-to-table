# AGENTS.md

## Purpose

Repository operating manual for Extract Structured Info from Papers.

This repo is building a local-first paper-to-table review app that ingests PDFs plus a structured spreadsheet, generates evidence-backed cell proposals, supports human review in a browser UI, and exports audited XLSX updates.

## Quick Reference

- Current repo state: spec-first rebuild. The implementation has not restarted yet in this snapshot.
- Current source of truth: `specs/spec.md`, `specs/plan.md`, `specs/tasks.md`, and this file.
- Preferred shell: Git Bash on Windows.
- Canonical fixture root: `tests/fixtures/`.
- Current fixture folders: `tests/fixtures/tables/` and `tests/fixtures/papers/`.
- Expected implementation shape: `backend/` for FastAPI services and pipeline logic, `frontend/` for the React review UI.
- No canonical backend, frontend, lint, or test commands exist yet in this repo snapshot. Do not invent them in docs. When Batch 1 introduces them, add them here and in `README.md` in the same pass.
- When working inside `specs/`, follow `specs/AGENTS.md` for the spec-specific workflow.

## Work Modes

### Normal work

If the user asks for non-spec work, do the work directly. Update specs only if repository truth actually changed.

### Spec-driven work

If the task is explicitly spec-driven or scoped to `specs/`, follow:

1. `spec.md`
2. `plan.md`
3. `data-model.md` or `contracts/` when relevant
4. `tasks.md`

If those artifacts conflict, fix the smallest coherent set of docs first.

## Quality Bar

For this repo, “smallest coherent implementation” means the smallest slice a normal local operator can actually use from install and startup through run launch, run-state visibility, review, and export.

Do not treat any of the following as done:

- a backend-complete but operator-confusing slice
- a browser shell with vague or misleading empty/loading/failure states
- provider scaffolding that never proves the documented LM Studio path works
- a nominally completed run that cannot produce reviewer-usable proposals on the canonical fixture path

Done means the operator can understand what to do next without reading source code, and the docs, UI, runtime behavior, and tests agree on the same workflow.

## Core Rules

- Prefer clear stage boundaries and narrow contracts over sprawling adaptive logic.
- Keep the browser UI as the primary operator surface for launch, status, review, and export.
- Keep the JSON config file as the authoritative advanced-control surface.
- Avoid broad settings UIs, speculative architecture, and unnecessary parameter bloat.
- Preserve the repo’s local-first identity even when optional cloud providers are supported.
- Keep the provider layer typed and explicit: LM Studio is the default live local path; optional cloud providers must stay behind the same contract.
- Keep provider naming and config semantics in parity across runtime validation, config examples, docs, tests, and UI labels.
- Unknown or obsolete provider identifiers must fail early and clearly.
- Silent fallback to demo, stub, disabled, or degraded proposal generation is not acceptable.
- Treat onboarding, run-state clarity, review readiness, and export truthfulness as first-class requirements.

## Documentation Rules

- Update only the docs whose truth changed, but do it in the same pass as the code or behavior change.
- Remove stale text rather than letting old and new descriptions coexist.
- Keep `README.md` aligned with the real happy path, not developer shortcuts or speculative workflows.
- If the user-facing workflow changes, update `README.md` and the relevant spec docs together.

## Verification Rules

- Verify behavior; do not stop at structural correctness.
- Prefer integration and end-to-end validation when the repo supports it.
- For UI-affecting work, browser-level verification or equivalent e2e coverage is part of done.
- Preflight and readiness checks are part of done, not polish.
- Provider-affecting work must verify parity across runtime validation, config examples, docs, tests, and UI summaries.
- A documented live path is not done unless it either:
	- produces at least one non-empty proposal with reviewer-usable evidence on the canonical checked-in fixture path, or
	- fails early with a clear readiness error explaining why proposal generation cannot proceed.

## Batch Discipline

- Implement one batch deeply rather than many batches shallowly.
- Do not claim a batch is complete if onboarding, startup, run-state visibility, review safety, or docs truth for that slice are still rough.
- Do not let later-batch work excuse a hollow provider path in an earlier polished-looking shell.

## Repo Map

- `AGENTS.md`: root repo instructions
- `README.md`: user and developer entrypoint
- `specs/`: product, technical, research, and execution docs
- `tests/fixtures/`: canonical workbook and PDF fixtures
- `backend/`: planned FastAPI app and pipeline code
- `frontend/`: planned React review UI

If the real structure changes, update this map.

## Platform Rules

- Primary environment is Windows.
- Use bash commands suitable for Git Bash or WSL bash in docs and scripts.
- Do not use PowerShell in repo docs unless there is a specific separate audience.
- Prefer relative paths.
- If absolute paths are required, document both `/d/...` and `D:\...` forms.

## Compounding Lessons

Write a compounding lesson only when a bug, edge case, or workflow mistake reveals a reusable repo-level lesson and the repo is actively using those notes. Keep them under a consistent location in `docs/`.

## Final Rule

Leave the repository more truthful than you found it:

- code aligned with behavior
- tests aligned with code
- docs aligned with reality
- no stale remnants from older app versions
