# Paper Table Agent

A local-first paper-to-table review system. Ingests scientific PDFs and a structured spreadsheet, matches papers to rows, proposes cell updates with evidence, supports human review, and exports audited spreadsheet updates.

## Repository layout

- `backend/` — FastAPI app, staged runner, parsing, matching, extraction, review logic, export
- `frontend/` — React+Vite review UI (run management + three-pane review workspace)
- `tests/` — backend unit + integration tests, fixtures
- `specs/` — spec/plan/tasks source of truth

## Requirements

- Python 3.11+
- Node.js 20+

## Install

### Backend

```bash
pip install -e ./backend[dev]
```

### Frontend

```bash
cd frontend
npm install
```

## Configure

Copy and edit the example config:

```bash
cp backend/config.example.json my_config.json
```

Key config fields:

```json
{
  "paths": {
    "table_path": "/absolute/path/to/table.xlsx",
    "schema_path": "/absolute/path/to/schema.csv",
    "pdf_dir": "/absolute/path/to/pdfs",
    "output_dir": "/absolute/path/to/output"
  },
  "verify_mode": false,
  "placeholders_treated_as_empty": ["N/A", "-", ""],
  "provider": {
    "name": "lmstudio",
    "model": "mistral-7b-instruct",
    "base_url": "http://127.0.0.1:1234/v1"
  }
}
```

- `verify_mode: true` — also proposes updates for filled cells (review confirms or corrects existing values)
- `provider` — points to a running LM Studio instance (see [LM Studio docs](https://lmstudio.ai))

## Run the app

### Start backend

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

### Start frontend

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

## Happy path

1. Open the **Run** tab.
2. Enter the absolute path to your config file.
3. Click **Create run**.
4. Watch lifecycle state: `ready` → `validating` → `running` → terminal.
5. When the run reaches `completed` or `completed with warnings`, the **Review** tab becomes active.
6. Switch to the **Review** tab.
7. Browse the **Proposals** pane (left). Proposals are ordered: pending first, then actionable before blocked, then stable row/column order.
8. Select a proposal to see **Detail** (center) and **Evidence** (right).
   - Text evidence renders in a PDF.js canvas with highlight overlay when coordinates are available.
   - When coordinates are missing, a quote + page reference fallback is shown.
   - Figure evidence shows the crop image with caption; a "View full page" link gives context.
9. Review actions:
   - **Accept** — accept the proposed value as-is.
   - **Reject** — reject the proposal.
   - **Save edit & accept** — type an edited value and accept with that value instead.
   - **Bulk accept visible undecided** — accept all currently visible undecided proposals (requires confirmation).
10. Use keyboard shortcuts: `←`/`p` prev, `→`/`n` next, `a` accept, `r` reject, `e` focus edit, `v` focus evidence.
11. Open the **Run summary** tab to view PDF/proposal counts, decisions, verify mode, and provider info.
12. Open the **Unresolved** tab to inspect unmatched, ambiguous, or duplicate-row-conflict PDFs (read-only in MVP).
13. When you have reviewed proposals, click **Export** in the Review tab to generate the updated workbook and audit log.
14. Download links for the exported workbook, audit log, run summary, and reviewer summary appear in the **Run summary** tab once the respective files are ready.

## Run lifecycle states

| State | Meaning |
|---|---|
| `ready` | Run created, waiting to start |
| `validating` | Validating config and input paths |
| `running` | Pipeline stages executing |
| `completed` | All stages finished successfully |
| `completed with warnings` | Finished with unresolved matches or warnings |
| `failed` | Run failed; inspect message in the Run tab |

Review is gated until a run reaches a terminal state (`completed`, `completed with warnings`, or `failed`). A `failed` run is not reviewable — fix the issue and start a new run.

## Verify mode

When `verify_mode: true`, the pipeline also generates proposals for already-filled cells. In the review workspace:
- The **Current value** field is shown alongside the proposed value.
- Accepted proposals overwrite filled cells in the exported workbook.
- Run summary flags `no_reviewed_verified_cells` if verify mode is on but none of the reviewed proposals target filled cells.

## Artifact layout

Each run writes to `<output_dir>/<run_id>/`:

```
run.json                          # run state
config.snapshot.json              # config at run time
inputs/input_summary.json         # eligibility counts
inputs/input_details.json         # per-row input data
parsed/<pdf_id>/                  # docling parse results + page images
matching/                         # match outcomes + unresolved records
proposals/proposals.jsonl         # extracted proposals
evidence/evidence.jsonl           # evidence records with anchors
review/decisions.jsonl            # reviewer decisions (append-only audit log)
summaries/run_summary.json        # aggregated run statistics
summaries/reviewer_summary.json   # reviewer outcome summary
exports/updated_workbook.xlsx     # exported workbook (after export)
exports/audit_log.csv             # audit log (after export)
exports/diagnostics.json          # diagnostics and warning details (after export)
```

## Export fidelity boundary

The exported workbook is **content-only**:
- Only explicitly accepted cell values are written.
- Formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, charts, shapes, and macros are **not** preserved.
- Changed cells are highlighted in yellow.
- Only accepted proposals appear in the audit log.
- If the source workbook contains unsupported features, warnings are recorded in `exports/diagnostics.json`.

## Export endpoint

To trigger export after review, call:

```
POST /api/runs/{run_id}/export
```

This writes `exports/updated_workbook.xlsx`, `exports/audit_log.csv`, and `exports/diagnostics.json` to the run artifact directory. The browser UI exposes an **Export** button in the Review tab that calls this endpoint.

## Known MVP limitations

- No reranking, HyDE, or query expansion in retrieval (BM25-lite only).
- No user-triggered figure fallback; figure fallback is applied automatically by the extraction stage.
- No rematch or reassignment actions for unresolved PDFs — inspection-only.
- No multi-user review or collaboration.
- LM Studio must be running and reachable at the configured `base_url` before a run is launched.
- Export is content-only: formulas, merged cells, and workbook formatting are not preserved.

## Testing

### Backend

```bash
python -m pytest tests/backend -v
```

### Frontend unit tests

```bash
cd frontend
npm run test -- --run
```

### Frontend e2e (Playwright)

Requires the backend and frontend dev server to be running:

```bash
cd frontend
npx playwright test
```

### Live provider smoke test (opt-in)

```bash
PAPER_TABLE_AGENT_LIVE_TEST=1 PAPER_TABLE_AGENT_LIVE_CONFIG_PATH=/path/to/config.json \
  python -m pytest tests/backend/test_smoke_live.py -v
```

## Development

### Lint

```bash
cd frontend
npm run lint
```

### Build

```bash
cd frontend
npm run build
```

