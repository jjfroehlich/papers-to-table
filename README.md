# Paper Table Agent

Batch 6 implementation from the spec baseline is now in place.

## What works through Batch 6

- FastAPI backend run creation/list/inspection APIs plus review APIs, export trigger API, and download manifest endpoints.
- Config loading, validation, resolved config snapshotting, and deterministic run artifact bundle creation.
- In-process staged runner with lifecycle transitions and coarse stage progress (`current_stage` + `current_item`).
- Parse + matching + style-profile + retrieval + extraction pipeline with persisted proposal/evidence artifacts.
- Review decision persistence (`accept`, `accept_edited`, `reject`), decision history, bulk-accept-visible subset semantics, and recomputable run/reviewer summaries.
- Browser review workspace with queue/detail/evidence panes, unresolved-match inspection, keyboard shortcuts, and run/reviewer summary context.
- Content-only XLSX export (`updated.xlsx`) that applies only explicitly accepted decisions and highlights changed cells.
- Audit-log export (`audit_log.jsonl`) containing row id, column id, old/new value, proposal source, reviewer decision, and persisted decision timestamp.
- Unsupported-workbook feature detection (best effort) surfaced as run warnings and diagnostics while keeping the content-only boundary.
- Diagnostics JSON covering matching failures, blocked/unclear/skipped/error proposal outcomes, evidence quality indicators, unsupported workbook features, and completed-with-warnings state.

## Repository layout

- `backend/` — FastAPI app, staged runner, config validation, export/diagnostics services, artifact persistence
- `frontend/` — React run/review workspace and test harness
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

## Operator happy path

1. In **Run** view, enter a config path (default: `config.example.json`).
2. Click **Start run**.
3. Track lifecycle from `ready` → `validating` → `running` → terminal state.
4. Switch to **Review** when run is `completed` or `completed_with_warnings`.
5. Filter/select proposals, inspect row/column context, and inspect text/figure evidence.
6. Record decisions (`Accept`, `Save edited value`, `Reject`) or bulk-accept the visible subset.
7. Trigger final export (API: `POST /api/runs/{run_id}/export`) after review decisions are in place.
8. Download workbook, audit log, summaries, or artifacts bundle from the download surface.

## Artifacts

Each run writes a bundle at `artifacts/<run_id>/` including:

- `run.json`
- `config.snapshot.json`
- `inputs/summary.json`
- `parsed/documents.jsonl`
- `matching/summary.json`
- `style_profiles/profiles.json`
- `retrieval/chunks.jsonl`
- `proposals/proposals.jsonl`
- `proposals/diagnostics.json`
- `evidence/evidence.jsonl`
- `review/status_index.json`
- `review/decisions.jsonl`
- `review/decision_history.jsonl`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `exports/export_candidates.json`
- `exports/updated.xlsx`
- `exports/audit_log.jsonl`
- `logs/diagnostics.json`

## Export fidelity boundary (MVP contract)

Guaranteed:
- accepted cell values are written to exported XLSX
- unchanged cell content is carried forward
- changed cells are highlighted

Out of guarantee:
- formulas
- filters
- frozen panes
- hidden rows/columns
- merged cells
- conditional formatting
- comments
- named ranges
- charts/shapes/images/macros

The app warns when unsupported workbook features are detected and keeps export behavior content-only.

## Tests

```bash
pytest tests/backend/test_batch1.py
pytest tests/backend/test_batch2.py
pytest tests/backend/test_batch3.py
pytest tests/backend/test_batch4.py
pytest tests/backend/test_batch5.py
pytest tests/backend/test_batch6.py
cd frontend && npm test
cd frontend && npm run test:e2e
```

Optional live smoke (LM Studio running locally):

```bash
PTA_LIVE_SMOKE=1 pytest tests/backend/test_batch6.py -k live_smoke
```
