# Paper Table Agent

Batch 1 implementation from the spec baseline is now in place.

## What works in Batch 1

- FastAPI backend run creation/list/inspection APIs.
- Config loading, validation, and resolved config snapshotting.
- Input summary generation (table/schema/pdf counts + eligibility counts).
- Deterministic run artifact bundle creation per run.
- In-process staged runner with lifecycle transitions (`ready`, `validating`, `running`, `completed`/`failed`).
- React frontend shell with:
  - **Run view** for config-path launch and setup context
  - **Review view** with explicit pre-review gating states
- Backend and frontend test scaffolding plus Batch-1 backend behavior tests.

## Repository layout

- `backend/` — FastAPI app, staged runner, config validation, artifact persistence
- `frontend/` — React run/review shell and test harness
- `tests/` — fixtures and backend tests
- `specs/` — product + architecture + implementation tasks

## Prerequisites

- Python 3.10+
- Node 20+

## Backend startup

```bash
python -m pip install -e backend[dev]
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend startup

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

## Run flow (Batch 1)

1. In **Run** view, enter a config path (default: `config.example.json`).
2. Click **Start run**.
3. Track lifecycle from `ready` → `validating` → `running` → terminal state.
4. Review resolved input summary after validation.
5. If run failed, use the explicit failure reason shown in UI and `artifacts/<run_id>/run.json`.

## Artifacts

Each run writes a bundle at `artifacts/<run_id>/` including:

- `run.json`
- `config.snapshot.json`
- `inputs/summary.json`
- directories for later batches (`parsed/`, `matching/`, `proposals/`, etc.)
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`

## Tests

```bash
pytest tests/backend/test_batch1.py
cd frontend && npm test
```

## Current limit

Batch 1 does **not** yet include parsing, matching, proposal generation, review queue actions, or export.
Those are intentionally left for later batches in `specs/tasks.md`.
