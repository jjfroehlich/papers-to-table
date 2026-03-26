# Paper Table Agent

Batch 3 implementation from the spec baseline is now in place.

## What works in Batch 1 + Batch 2 + Batch 3

- FastAPI backend run creation/list/inspection APIs.
- Config loading, validation, and resolved config snapshotting.
- Input summary generation (table/schema/pdf counts + eligibility counts).
- Deterministic run artifact bundle creation per run.
- In-process staged runner with lifecycle transitions (`ready`, `validating`, `running`, `completed`/`failed`).
- Parse pipeline with a normalized `ParsedDocument` contract and per-PDF diagnostics.
- Docling-registered parser adapter with PDFium (`pypdfium2`) page rendering/crop helpers.
- Narrow OCR fallback attempt path (`ocrmypdf`) for text-insufficient PDFs, including artifact diagnostics.
- Deterministic metadata-based PDF-to-row matching with explicit outcomes:
  - `matched`
  - `ambiguous`
  - `unmatched`
  - `duplicate_row_conflict`
- Matching issue API endpoint for unmatched/ambiguous/duplicate conflict inspection.
- Per-column style-profile generation persisted to `style_profiles/` with leakage-safe guidance only.
- Retrieval artifact generation with typed chunks, contextualized retrieval text, and source-preserving display text.
- Proposal/evidence generation across eligible target cells with:
  - proposal states (`found`, `inferred`, `unclear`, `blocked`, `error`, `skipped`)
  - separate proposal and evidence records
  - quote+page fallback behavior when highlight anchoring is unavailable
  - scoped automatic figure fallback labeling (`figure_based_evidence`)
  - verify-mode support for already-filled target cells
- React frontend shell with:
  - **Run view** for config-path launch and setup context
  - **Review view** with explicit pre-review gating states
- Backend and frontend test scaffolding plus Batch-1/2/3 backend behavior tests.

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

## Run flow (through Batch 3)

1. In **Run** view, enter a config path (default: `config.example.json`).
2. Click **Start run**.
3. Track lifecycle from `ready` → `validating` → `running` → terminal state.
4. Run advances through parsing + matching + style profile + retrieval + extraction automatically.
5. Review resolved input summary after validation.
6. If run failed, use the explicit failure reason shown in UI and `artifacts/<run_id>/run.json`.

## Artifacts

Each run writes a bundle at `artifacts/<run_id>/` including:

- `run.json`
- `config.snapshot.json`
- `inputs/summary.json`
- `parsed/documents.jsonl`
- `parsed/native/*.json`
- `parsed/diagnostics.json`
- `parsed/pages/<pdf_id>/page_*.png`
- `matching/summary.json`
- `style_profiles/profiles.json`
- `style_profiles/diagnostics.json`
- `retrieval/chunks.jsonl`
- `retrieval/diagnostics.json`
- `proposals/proposals.jsonl`
- `proposals/diagnostics.json`
- `evidence/evidence.jsonl`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`

## Tests

```bash
pytest tests/backend/test_batch1.py
pytest tests/backend/test_batch2.py
pytest tests/backend/test_batch3.py
cd frontend && npm test
```

## Current limit

Batch 3 still does **not** include review decision APIs, run/reviewer summary filtering surfaces, or accepted-only XLSX export/audit workflows.
Those remain intentionally scoped to later batches in `specs/tasks.md`.
