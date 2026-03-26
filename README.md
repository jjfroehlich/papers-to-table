# Paper Table Agent

Batch 5 implementation from the spec baseline is now in place.

## What works through Batch 5

- FastAPI backend run creation/list/inspection APIs plus review APIs and download manifest endpoints.
- Config loading, validation, resolved config snapshotting, and deterministic run artifact bundle creation.
- In-process staged runner with lifecycle transitions and coarse stage progress (`current_stage` + `current_item`).
- Parse + matching + style-profile + retrieval + extraction pipeline with persisted proposal/evidence artifacts.
- Review decision persistence (`accept`, `accept_edited`, `reject`), decision history, bulk-accept-visible subset semantics, and recomputable run/reviewer summaries.
- Browser review workspace with:
  - queue pane
  - proposal detail pane
  - evidence viewer pane
  - run/reviewer summary context
  - unresolved match inspection data
  - keyboard shortcuts (`j`/`k`/`a`/`r`/`e`/`v`)
- Proposal filtering by review decision, evidence strength, match status, and figure-derived status.
- Quote + page fallback display when highlight geometry is unavailable.
- Figure evidence display when figure crop/full-page paths are present in evidence records.
- Download endpoints for run summary, reviewer summary, and run artifacts zip; workbook/audit endpoints are exposed and truthfully report not-ready before Batch 6 export writing.

## Repository layout

- `backend/` — FastAPI app, staged runner, config validation, artifact persistence
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

## Operator flow (Batch 5)

1. In **Run** view, enter a config path (default: `config.example.json`).
2. Click **Start run**.
3. Track lifecycle from `ready` → `validating` → `running` → terminal state and watch coarse stage updates.
4. Switch to **Review** when run is `completed` or `completed_with_warnings`.
5. Use queue filters and select proposals in the left pane.
6. Inspect row/column context and proposed value in center pane.
7. Inspect evidence in right pane (highlight metadata + page image, quote+page fallback, and figure assets when available).
8. Record decisions (`Accept`, `Save edited value`, `Reject`) or use **Bulk accept visible subset** with confirmation.
9. Download summaries or artifacts from run summary links.

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
- `evidence/evidence.jsonl`
- `review/status_index.json`
- `review/decisions.jsonl`
- `review/decision_history.jsonl`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `exports/export_candidates.json`

## Tests

```bash
pytest tests/backend/test_batch1.py
pytest tests/backend/test_batch2.py
pytest tests/backend/test_batch3.py
pytest tests/backend/test_batch4.py
pytest tests/backend/test_batch5.py
cd frontend && npm test
cd frontend && npm run test:e2e
```

## Current limit

Batch 5 does not yet write final updated workbook/audit-log exports (Batch 6 scope), so workbook/audit download endpoints can return not-ready.
