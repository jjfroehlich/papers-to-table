# Batch 5 lesson: Playwright webServer cwd must target repository root

## Context

During Batch 5, Playwright e2e startup failed because the backend webServer command in `frontend/tests/playwright.config.ts` used a `cwd` that resolved to the frontend directory instead of the repository root in this execution context.

## What failed

- `python -m uvicorn backend.app.main:app` could not import `backend`.
- The command itself was valid, but it depended on root-level module resolution.

## Fix

- Updated Playwright backend webServer `cwd` from `..` to `../..` so the process starts from the repository root consistently.
- Added a dedicated frontend script `test:e2e` to avoid ad hoc command drift.

## Preventive takeaway

When using Playwright `webServer` arrays, treat `cwd` as an explicit contract and verify module import assumptions in CI-like paths. Do not rely on the current shell location where Playwright was invoked.
