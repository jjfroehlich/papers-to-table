# Paper Table Agent

Paper Table Agent is a local-first browser application for turning a spreadsheet plus a folder of scientific PDFs into reviewed spreadsheet updates.

The MVP in this repository uses:
- a **React** frontend for run inspection and queue-first review
- a small **FastAPI** backend with a synchronous staged runner
- **filesystem artifact bundles + JSON files** as the canonical state
- **LM Studio localhost API** as the live provider path, with a deterministic stub path for default tests
- **content-only XLSX export** with changed-cell highlighting and an audit log

## MVP workflow

1. Load a config that points to a table, schema, and PDF directory.
2. Create a run bundle under `artifacts/run-.../`.
3. Normalize the table and compute eligible cells, including Verify mode targets.
4. Parse PDFs into normalized parsed-document artifacts.
5. Match each PDF to at most one row, preserving unmatched, ambiguous, and duplicate-row-conflict records.
6. Generate one best proposal per eligible target cell with linked evidence records.
7. Review proposals in the browser UI.
8. Export only explicitly accepted changes to a new XLSX workbook plus an audit log.

## Repo structure

- `backend/` — FastAPI app, staged runner, parsing/matching/extraction/export logic
- `frontend/` — React review UI and Playwright/Vitest harness
- `tests/backend/` — backend unit/integration/smoke tests
- `tests/e2e/` — Playwright review-workflow coverage
- `tests/fixtures/` — deterministic tables, schema, PDFs, and parser sidecars
- `docs/engineering-lessons/` — compounding engineering notes
- `specs/` — spec, plan, research, and task checklist

## Installation

### Backend

```bash
python -m pip install -e .[dev]
```

### Frontend

```bash
cd frontend
npm install
cd ..
```

## Run the app

Create or edit a config based on `config.example.json`, then start the backend and frontend.

### Start the backend

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Start the frontend

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 4173
```

Open `http://127.0.0.1:4173` in your browser.

## Sample workflow

Create a run against the fixture corpus:

```bash
python - <<'PY'
from pathlib import Path
from backend.app.config import load_config
from backend.app.runner import Runner
config = load_config('tests/fixtures/configs/test-config.json')
config.paths.output_dir = 'artifacts'
run = Runner(Path('artifacts')).execute(config)
print(run.run_id)
PY
```

Then use the UI to review proposals for that run.

## Where artifacts and exports go

Each run is written to `artifacts/<run_id>/` with these important paths:

- `run.json`
- `config.snapshot.json`
- `inputs/`
- `style_profiles/`
- `parsed/`
- `matching/`
- `retrieval/`
- `proposals/`
- `evidence/`
- `review/`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `exports/updated_workbook.xlsx`
- `exports/audit_log.csv`
- `logs/diagnostics.json`

## Verify mode

Verify mode is enabled by default in the config. When enabled, already-filled cells are still sent through the same extraction path so the reviewer can compare the proposal to the existing value and record reviewer-outcome summaries.

## Export fidelity boundary

The MVP export guarantee is intentionally narrow:
- preserved cell contents
- accepted changes applied to a new XLSX workbook
- changed cells highlighted

The MVP does **not** preserve formulas, filters, frozen panes, hidden rows/columns, merged cells, comments, charts, shapes, macros, or conditional formatting.

## Testing

### Backend

```bash
bash scripts/test_backend.sh
```

### Frontend

```bash
bash scripts/test_frontend.sh
```

### Playwright e2e

```bash
bash scripts/test_e2e.sh
```

If the environment blocks browser downloads or browser execution, the Playwright suite remains present but may be skipped operationally.

### Full test pass

```bash
bash scripts/test_all.sh
```
