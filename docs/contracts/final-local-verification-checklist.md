# Final Local Verification Checklist

Use this checklist from the monorepo root after dependency install.

## Minimum smoke verification

- Minimum smoke wrapper
  - Run: `bash scripts/verify-minimum-smoke.sh`
  - Verifies:
    - main app backend can start and answer `/api/health`
    - main app frontend production build succeeds
    - eval example run executes from `tools/eval/`
    - optimizer smoke compare run executes from `tools/optimizer/`

## Main app

- Backend health endpoint
  - Run: `bash scripts/check-main-backend-health.sh`
- Backend dev server
  - Run: `bash scripts/run-main-backend.sh`
- Frontend build
  - Run: `bash scripts/build-main-frontend.sh`
- Frontend dev server
  - Run: `bash scripts/run-main-frontend.sh`
- Backend test suite used by the full wrapper
  - Run: `bash scripts/test-main-backend.sh`
  - Verifies: backend pytest suite excluding opt-in `e2e` and `smoke` markers
- Frontend test suite used by the full wrapper
  - Run: `bash scripts/test-main-frontend.sh`
  - Verifies: frontend Vitest suite in `app/frontend`
- Full main app verification wrapper
  - Run: `bash scripts/verify-main-app-full.sh`
  - Verifies:
    - backend non-`e2e`, non-`smoke` pytest suite
    - frontend Vitest suite
  - Reporting behavior:
    - runs backend and frontend checks separately
    - prints PASS or FAIL for each surface
    - exits non-zero if either surface fails
- Legacy combined alias
  - Run: `bash scripts/test-main-app.sh`
  - Note: compatibility alias for `bash scripts/verify-main-app-full.sh`

## Eval tool

- Eval example or smoke run
  - Run: `bash scripts/run-eval-example.sh`
  - Verifies: example eval scoring run from `tools/eval/`
- Eval test suite
  - Run: `bash scripts/test-eval-tool.sh`
  - Verifies: eval pytest suite in `tools/eval`

## Optimizer tool

- Optimizer smoke compare or evaluate run
  - Run: `bash scripts/run-optimizer-smoke.sh`
  - Verifies: smoke compare run from `tools/optimizer/`
- Optimizer test suite
  - Run: `bash scripts/test-optimizer-tool.sh`
  - Verifies: optimizer pytest suite in `tools/optimizer`

## Intentionally excluded or environment-blocked checks

- Main app `e2e` and `smoke` pytest markers are intentionally excluded from the full main app wrapper because they are opt-in and require live services or browser-backed workflows.
- Manual browser review and export checks remain manual; they are not represented as a root wrapper.
- Live LM Studio availability and model readiness can still block proposal-generation paths and some smoke behavior outside the non-`smoke` backend suite.

## Repo hygiene

- Search for stale sibling-repo assumptions in active source files only
  - Exclude generated outputs, logs, caches, and historical migration notes when judging runtime readiness.
- Confirm canonical docs
  - Main app: `docs/main-app/`
  - Eval: `docs/eval/`
  - Optimizer: `docs/optimizer/`
  - Contracts: `docs/contracts/`

## Manual sign-off prompts

- Can a new contributor find the main app first from `README.md`?
- Can eval and optimizer be understood as secondary internal tools?
- Do wrapper scripts launch from monorepo-local paths without sibling-repo edits?
- Are any remaining old-repo references historical only, rather than required for current runtime behavior?