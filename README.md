# Paper Table Agent

Batch 1 implementation baseline for the Paper Table Agent rebuild.

This branch now ships a **working foundation** for the browser-first run-start workflow:
- FastAPI backend for run creation/listing/summaries
- app-owned staged runner with lifecycle transitions
- config validation + snapshotting
- table/schema ingest + eligibility classification (including Verify mode)
- filesystem artifact bundle persistence per run
- React Run/Review shell with explicit pre-review guidance

Later batches (parsing/matching/extraction/review queue/export) are intentionally not implemented yet.

## Repository layout

- `/home/runner/work/paper-table-agent/paper-table-agent/backend` — FastAPI app and staged runner foundation
- `/home/runner/work/paper-table-agent/paper-table-agent/frontend` — React+Vite UI shell (Run + Review baseline)
- `/home/runner/work/paper-table-agent/paper-table-agent/tests` — backend tests + fixtures
- `/home/runner/work/paper-table-agent/paper-table-agent/specs` — spec/plan/tasks source of truth

## Requirements

- Python 3.11+
- Node.js 20+

## Install

### Backend

```bash
cd /home/runner/work/paper-table-agent/paper-table-agent
python -m pip install -e ./backend[dev]
```

### Frontend

```bash
cd /home/runner/work/paper-table-agent/paper-table-agent/frontend
npm install
```

## Configure

Use the example config as a starting point:

- `/home/runner/work/paper-table-agent/paper-table-agent/backend/config.example.json`

Key fields used in Batch 1:
- `paths.table_path`
- `paths.schema_path`
- `paths.pdf_dir`
- `paths.output_dir`
- `verify_mode`
- `placeholders_treated_as_empty`

## Run the app

### Start backend

```bash
cd /home/runner/work/paper-table-agent/paper-table-agent
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Start frontend

```bash
cd /home/runner/work/paper-table-agent/paper-table-agent/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

## Batch 1 happy path

1. Open the **Run** view.
2. Enter an absolute config path.
3. Create a run.
4. Observe lifecycle states in UI (`ready` → `validating` → `running` → terminal).
5. Inspect setup summary (config path, table/schema/pdf/output paths, Verify mode, target columns).
6. If terminal and successful baseline, inspect input eligibility summary.

The **Review** view in Batch 1 is intentionally a guided pre-review state surface (no proposal queue yet).

## Artifact layout (Batch 1)

Each run writes to:

- `<output_dir>/<run_id>/run.json`
- `<output_dir>/<run_id>/config.snapshot.json`
- `<output_dir>/<run_id>/inputs/input_summary.json`
- `<output_dir>/<run_id>/inputs/input_details.json`
- `<output_dir>/<run_id>/summaries/run_summary.json`
- `<output_dir>/<run_id>/summaries/reviewer_summary.json`
- plus stable stage directories:
  - `inputs/`
  - `style_profiles/`
  - `parsed/`
  - `matching/`
  - `retrieval/`
  - `proposals/`
  - `evidence/`
  - `review/`
  - `summaries/`
  - `exports/`
  - `logs/`

## Test and verification commands

From repository root:

```bash
python -m pytest tests/backend -v
```

From frontend directory:

```bash
npm run lint
npm run test
npm run build
npm run test:e2e -- --list
```

## Current limitations (intentional in Batch 1)

- No PDF parsing pipeline yet.
- No PDF-to-row matching yet.
- No proposal/evidence generation yet.
- No actionable review queue/detail/evidence viewer yet.
- No export/audit generation yet.

These are planned for later batches in `specs/tasks.md`.
