# Contributing

Thanks for contributing to papers-to-table.

## Start here

- Repo overview and happy path: [`README.md`](README.md)
- Docs map by audience: [`docs/README.md`](docs/README.md)
- Main app operator docs: [`docs/main-app/README.md`](docs/main-app/README.md)
- Repo operating rules for coding agents and maintainers: [`AGENTS.md`](AGENTS.md)
- Normative spec system: [`specs/README.md`](specs/README.md)

## Quick local setup

Run these from the repo root unless noted otherwise.

```bash
cd app
python -m pip install -e ./backend[test]
cd frontend
npm install
cd ../..
```

## Common commands

Use the wrapper scripts when possible:

```bash
bash scripts/run-main-backend.sh
bash scripts/run-main-frontend.sh
bash scripts/test-main-backend.sh
bash scripts/test-main-frontend.sh
bash scripts/verify-main-app-full.sh
```

These wrapper commands assume you start in the repository root.

## Main app workflow

1. Start the backend and frontend.
2. Open `http://localhost:5173`.
3. Run preflight from the **Run** tab to confirm resolved inputs and provider readiness.
4. Start a run only after the preflight is green or intentionally understood.
5. Review evidence-backed proposals in the browser.
6. Export explicitly after review.

## When you change code

- Update the owning docs/specs in the same pass when repo truth changes.
- Keep screenshots current when the UI changes materially.
- Prefer current files over archive material for active behavior.
- Run the relevant tests before you finish.

## Where things live

- Backend: `app/backend/src/backend/app/`
- Frontend: `app/frontend/src/`
- Backend tests: `app/tests/backend/`
- E2E tests and screenshot capture: `app/tests/e2e/`
- Main app docs: `docs/main-app/`
- Normative specs: `specs/`

## Screenshot refresh

Run this from the repository root:

```bash
python -m playwright install chromium
python -m pytest app/tests/e2e/test_doc_screenshots.py -m e2e --capture-doc-screenshots
```

This updates the images under `docs/screenshots/`.
