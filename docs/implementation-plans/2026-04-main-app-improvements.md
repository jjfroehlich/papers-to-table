# 2026-04 Main App Improvements

## Goals

- Clean up backend architecture so API, config, run execution, and review data loading have clearer boundaries.
- Improve the browser app so run launch is preflight-first, live updates are more reliable, and review feels more polished.
- Make current specs and contributor guidance stand on their own without active archive dependency.
- Keep docs, screenshots, tests, scripts, and specs aligned with the implemented workflow.

## Scope

In scope:
- backend packaging/layout, API modularization, config modularization, run execution abstraction, SSE transport, review lookup caching, explicit CORS
- frontend run setup, review workspace layout, diagnostics placement, visual design polish, SSE consumption
- current specs, AGENTS guidance, contributor docs, ADRs, docs map, glossary/examples, screenshot workflow, README alignment
- backend/frontend/e2e test updates and screenshot refreshes

Out of scope:
- changing the core product direction
- breaking run-bundle contracts for eval/optimizer
- redesigning `specs/tasks.md`

## Decisions Already Made

- Current specs must be sufficient on their own; archive links remain background only.
- `specs/tasks.md` stays structurally as-is.
- The UI should become preflight-first.
- Unresolved diagnostics move out of the evidence panel.
- Live run updates move to SSE.
- A `RunExecutor` abstraction is required.
- Packaging should move toward a more conventional layout.
- Root `AGENTS.md` should explicitly tell coding agents to continue independently through large bundles.
- Screenshots must be refreshed where UI changes make them stale.

## Implementation Batches

### Batch 1 — Backend foundation and package layout
- Move backend packaging to a conventional `src/` layout.
- Split API wiring into routers and shared dependencies.
- Split config concerns into models, loading/path resolution, and readiness/preflight.
- Add explicit app settings for CORS and runtime defaults.
- Introduce run event broadcasting and `RunExecutor` abstraction.

### Batch 2 — Run pipeline and review data efficiency
- Keep the pipeline behavior intact while extracting runner-adjacent services.
- Persist review lookup artifacts for row/column/paper context once per run.
- Reuse lookup artifacts in proposal list/detail endpoints.
- Surface SSE run updates from lifecycle changes.

### Batch 3 — Frontend workflow and design
- Redesign run launch around preflight context, readiness, and resolved input visibility.
- Switch active run updates from polling to SSE-backed state updates.
- Separate unresolved diagnostics into a dedicated diagnostics surface.
- Improve review hierarchy, spacing, badges, panel polish, and export visibility.

### Batch 4 — Specs, docs, contributor guidance, and screenshots
- Add concise metadata headers to current spec files.
- Remove current-spec dependence on archive wording.
- Strengthen process docs with executable update/verification checklists.
- Improve docs entrypoints, glossary/examples, AGENTS structure, wrapper-script guidance, contributor guide, and ADRs.
- Refresh README, operator docs, screenshots, and screenshot-capture instructions.

### Batch 5 — Verification and repo-truth pass
- Install missing local dependencies.
- Run backend/frontend tests, targeted e2e coverage, screenshot capture, and final validation.
- Update `specs/tasks.md` only where implementation truth changed.

## File-Level Targets

Backend/package targets:
- `/home/runner/work/papers-to-table/papers-to-table/app/backend/pyproject.toml`
- `/home/runner/work/papers-to-table/papers-to-table/app/backend/src/backend/app/**`
- `/home/runner/work/papers-to-table/papers-to-table/app/tests/backend/**`

Frontend targets:
- `/home/runner/work/papers-to-table/papers-to-table/app/frontend/src/App.tsx`
- `/home/runner/work/papers-to-table/papers-to-table/app/frontend/src/api/client.ts`
- `/home/runner/work/papers-to-table/papers-to-table/app/frontend/src/components/*.tsx`
- `/home/runner/work/papers-to-table/papers-to-table/app/frontend/src/types/index.ts`
- `/home/runner/work/papers-to-table/papers-to-table/app/frontend/src/*.css`
- `/home/runner/work/papers-to-table/papers-to-table/app/frontend/src/**/*.test.tsx`

Docs/spec targets:
- `/home/runner/work/papers-to-table/papers-to-table/README.md`
- `/home/runner/work/papers-to-table/papers-to-table/AGENTS.md`
- `/home/runner/work/papers-to-table/papers-to-table/CONTRIBUTING.md`
- `/home/runner/work/papers-to-table/papers-to-table/docs/main-app/*.md`
- `/home/runner/work/papers-to-table/papers-to-table/docs/screenshots/*`
- `/home/runner/work/papers-to-table/papers-to-table/docs/architecture-decisions/*.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/README.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/AGENTS.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/product/*.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/process/*.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/architecture/*.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/tasks.md`

## Test and Verification Plan

- Backend: `bash scripts/test-main-backend.sh`
- Frontend: `bash scripts/test-main-frontend.sh`
- Full wrapper: `bash scripts/verify-main-app-full.sh`
- Targeted e2e: doc screenshots and review workspace coverage
- Final code review/security validation with `parallel_validation`

## Screenshot and Doc Update Plan

- Refresh run setup, review workspace, and export screenshots from Playwright.
- Update operator workflow screenshots and captions to match the new preflight-first launch and review layout.
- Update README and main-app docs to point to wrapper scripts as the default happy path.

## Rollout Risks

- Packaging move can break imports or local startup commands if docs/tests are not updated together.
- SSE can introduce stale listener behavior if cleanup is incomplete.
- Review lookup caching must stay truthful to run artifacts and avoid hidden divergence.
- Screenshot capture can fail if demo fixtures or selectors drift.

## Completion Checklist

- [ ] Specs stand alone without active archive dependence.
- [ ] Process docs include operational update and verification checklists.
- [ ] Current spec files have concise metadata headers.
- [ ] Docs landing guidance is clearer by audience.
- [ ] Glossary/examples reduce ambiguity.
- [ ] Root and specs AGENTS guidance are stronger and clearer.
- [ ] Contributor guide exists and wrapper scripts are referenced.
- [ ] Backend API/config/runner concerns are modularized.
- [ ] CORS is explicit and config-driven.
- [ ] `RunExecutor` exists and SSE is the live update transport.
- [ ] Review lookup artifacts are persisted and reused.
- [ ] Backend packaging uses a more conventional layout.
- [ ] Run setup is preflight-first and review diagnostics placement is improved.
- [ ] Review workspace hierarchy and styling are more polished.
- [ ] Docs, ADRs, screenshots, and scripts match the implemented app.
- [ ] Tests and validations cover the changed behavior.
