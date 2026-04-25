# Final Monorepo Migration Summary

This note records the end-state of the monorepo migration for the repository root at `papers-to-table/`.

## Final structure

```text
repo/
  README.md
  docs/
    main-app/
    eval/
    optimizer/
    contracts/
  benchmarks/
  app/
  tools/
    eval/
    optimizer/
  scripts/
```

## What changed

- The main app runtime moved under `app/`.
- Eval moved in-repo under `tools/eval/`.
- Optimizer moved in-repo under `tools/optimizer/`.
- Product-facing docs were reorganized so the main app is primary and the two tools are secondary.
- Shared migration and contract notes now live under `docs/contracts/`.
- Repo-root wrapper scripts now launch the main app and tool workflows from monorepo-local paths.

## Old to new path mapping

| Old location | New location |
| --- | --- |
| `backend/` | `app/backend/` |
| `frontend/` | `app/frontend/` |
| `tests/` | `app/tests/` |
| `config.example.json` | `app/config.example.json` |
| `config.json` | `app/config.json` |
| `pyproject.toml` | `app/pyproject.toml` |
| `extract-structured-info-from-papers-eval/` | `tools/eval/` |
| `extract-structured-info-from-papers-optimizer/` | `tools/optimizer/` |
| `docs/operator-workflow.md` | `docs/main-app/operator-workflow.md` |
| `docs/run-artifacts.md` | `docs/main-app/run-artifacts.md` |

## Canonical commands

Run these from the repo root unless noted otherwise.

### Normal main app use

```bash
cd app
python -m pip install -e ./backend
cd frontend
npm install
```

```bash
cd app
python -m uvicorn backend.app.main:app --reload --port 8000
```

```bash
cd app/frontend
npm run dev
```

```bash
bash scripts/run-main-backend.sh
bash scripts/run-main-frontend.sh
bash scripts/check-main-backend-health.sh
bash scripts/build-main-frontend.sh
bash scripts/test-main-backend.sh
bash scripts/test-main-frontend.sh
bash scripts/verify-main-app-full.sh
bash scripts/verify-minimum-smoke.sh
```

### Eval tool use

```bash
cd tools/eval
python -m pip install -r requirements.txt
python -m paper_eval evaluate \
  --run tests/fixtures/example_eval/runs/run-a \
  --gold tests/fixtures/example_eval/gold.csv \
  --schema tests/fixtures/example_eval/schema.json \
  --out out/example-single-monorepo
```

```bash
bash scripts/run-eval-example.sh
bash scripts/test-eval-tool.sh
```

### Optimizer use

```bash
cd tools/optimizer
python -m pip install -e .[dev]
```

```bash
cd tools/optimizer
PAPER_OPTIMIZER_SKIP_HOLDOUT=1 bash scripts/run_study.sh compare configs/compare_models_contract_smoke.json monorepo_smoke
```

```bash
bash scripts/run-optimizer-smoke.sh
bash scripts/test-optimizer-tool.sh
```

## Known limitations

- `docs/contracts/monorepo-migration-prep.md` is intentionally historical and still mentions the old multi-repo layout.
- Some generated run artifacts and logs under `tools/eval/runs/`, `tools/eval/out/`, `tools/optimizer/runs/`, and `tools/optimizer/logs/` still embed old paths from earlier runs.
- Python import and CLI names remain tool-specific by design: `backend.app.*`, `paper_optimizer`, `paper_eval`, and `paper-optimizer` stay unchanged even though distribution metadata now uses the `papers-to-table-*` scheme.
- Live proposal generation and judge-backed scoring still depend on the local LM Studio setup and model availability.
- Main app `e2e` and `smoke` pytest markers remain opt-in and are intentionally excluded from the root full-verification wrapper.

## Final judgment rule

Treat the migration as ready only if:

- the main app launches from `app/`
- the frontend builds from `app/frontend/`
- main app tests run from `app/tests/`
- eval commands run from `tools/eval/`
- optimizer commands run from `tools/optimizer/`
- no active source files still require sibling-repo paths to function