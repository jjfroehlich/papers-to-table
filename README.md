# Paper Table Agent

A local-first paper-to-table review app. Ingest scientific PDFs and a structured spreadsheet, generate evidence-backed cell proposals, review them in a browser UI, and export audited XLSX updates.

---

## Architecture

- **Backend:** Python 3.11+, FastAPI, Pydantic v2
- **Frontend:** React + TypeScript + Vite + Tailwind CSS + PDF.js
- **Storage:** Filesystem artifact bundles (JSON files), no database
- **Default provider:** LM Studio (local), via `http://localhost:1234`

---

## Prerequisites

- Python 3.11 or later
- Node.js 18 or later and npm
- [LM Studio](https://lmstudio.ai/) running locally with a model loaded (required for actual proposal generation)

---

## Install and start

### 1. Clone and install backend dependencies

```bash
git clone <repo-url>
cd paper-table-agent
pip install -e ./backend
```

> **Note:** This installs all required backend packages including `docling` (the PDF parser) and `pypdfium2`. `docling` downloads ML models on first use and may take a minute.

### 2. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Start the backend

```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 4. Start the frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Configuration

All run parameters are controlled by a JSON config file. Copy the example to get started:

```bash
cp config.example.json config.json
# Edit config.json with your paths and model settings
```

The canonical provider token is `lm_studio`. Tokens such as `lmstudio`, `LMStudio`, or `openai` will produce a clear validation error at run start.

### Key config fields

| Field | Description |
|---|---|
| `table_path` | Path to spreadsheet (XLSX or CSV) |
| `schema_path` | Path to schema CSV (`column_name`, `description`, optional `field_type`, optional `allowed_values`) |
| `pdf_dir` | Directory containing PDF files |
| `output_dir` | Where run artifacts are stored (default: `./runs`) |
| `verify_mode` | If `true`, already-filled cells are also extraction targets |
| `provider.token` | Must be `"lm_studio"` |
| `provider.base_url` | LM Studio API base URL (default: `http://localhost:1234`) |
| `provider.text_model.model_id` | ID of the text model loaded in LM Studio |
| `provider.vision_model.model_id` | ID of the vision model (optional) |
| `retrieval.top_k` | Focused retrieval passage count for the first pass (default: `6`) |
| `retrieval.recall_rescue_enabled` | Retry `unclear` results with deterministic expanded retrieval (default: `true`) |
| `retrieval.whole_document_mode` | Opt-in whole-document rescue context for short parsed papers (default: `false`) |

When `field_type` is provided in the schema, extraction honors it without requiring prefilled table examples. `allowed_values` are only valid for `categorical` fields. Numeric fields preserve `exact`, `range`, or `approximate` answer forms internally.

The config file is the authoritative control surface for all run parameters. Path overrides entered in the browser UI apply to a single run only and do not change the config file.

---

## Primary workflow

### 1. Create a run

1. Open `http://localhost:5173` in the browser.
2. In the **Run** tab, enter the path to your config file (e.g. `config.json`).
3. Optionally expand **optional path overrides** to override `table_path`, `schema_path`, or `pdf_dir` for this run.
4. Click **Create Run**.

The run progresses through: `created → validating → running → completed` (or `completed_with_warnings` / `failed`). Select any run from the list to see stage progress, warnings, and error details.

A run reaches `completed_with_warnings` when it finished but encountered non-fatal issues (for example, matching ambiguity or fallback evidence quality warnings). The run is still reviewable and exportable.

### 2. Review proposals

When a run reaches `completed` or `completed_with_warnings`, the **Review** tab becomes active.

The review workspace has three panes:

- **Left — Proposal Queue:** Browse proposals grouped by paper or column. Filter by decision status (All / Pending / Accepted / No Data / Rejected). Click a proposal to load it.
- **Center — Proposal Detail:** Shows the proposed value, rationale, evidence list, and row context. Click an evidence item to jump to it in the PDF viewer.
- **Right — Evidence Viewer:** Renders the source PDF with PDF.js. Blue overlays show exact highlights; dashed orange overlays show approximate regions. A text fallback panel appears when exact highlighting is unavailable.

**Decision controls:**

| Button | Action |
|---|---|
| **Accept** | Accept the proposed value as-is |
| **Accept with Edit** | Accept with a corrected value |
| **No Data** | Confirm this cell has no data in this paper |
| **Reject** | Reject the proposal |

**Keyboard shortcuts:**

| Key | Action |
|---|---|
| `A` | Accept |
| `R` | Reject |
| `]` or `N` | Next proposal |
| `[` or `P` | Prev proposal |
| `E` | Focus edit input |
| `?` | Show shortcut help |

The **Unresolved** tab shows unmatched PDFs, ambiguous matches, and duplicate row conflicts for inspection.

### 3. Export

After completing review, trigger export from the **Review** tab (or via the API):

```bash
POST /api/runs/{run_id}/export?output_dir=./runs
```

Export generates three files in `{run_id}/exports/`:

- `workbook_{timestamp}.xlsx` — updated XLSX with accepted changes and yellow cell highlighting
- `audit_log_{timestamp}.json` — decision log (row, column, old value, new value, timestamp)
- `diagnostics_{timestamp}.json` — matching failures, blocked proposals, unsupported-feature warnings

Only explicitly **accepted** (as-is or with edit) proposals are written to the workbook. Unreviewed, confirmed-no-data, and rejected proposals are excluded by construction.

### 4. Download

Use the download endpoints or the browser UI download buttons:

| Endpoint | Returns |
|---|---|
| `GET /api/runs/{run_id}/downloads/workbook` | Updated XLSX workbook |
| `GET /api/runs/{run_id}/downloads/audit-log` | Audit log JSON |
| `GET /api/runs/{run_id}/downloads/run-summary` | `run_summary.json` |
| `GET /api/runs/{run_id}/downloads/reviewer-summary` | `reviewer_summary.json` |

Download endpoints return 404 if the export has not been triggered yet.

---

## Export fidelity boundary

The exported workbook is **content-only**. The following are explicitly **not** preserved:

- Formulas (stripped; export contains values only)
- Conditional formatting
- Filters (auto-filter)
- Frozen panes
- Hidden rows or columns
- Merged cells
- Cell comments
- Named ranges
- Charts, shapes, and macros

When any of these features are detected in the source workbook, warnings are recorded in `diagnostics_{timestamp}.json` under `unsupported_workbook_features`. The export still proceeds; unsupported features are warned about and ignored rather than silently corrupted.

The exported XLSX always contains all rows and columns from the source workbook, with accepted-change cells highlighted in yellow. Other cells retain their original values.

---

## Run artifact layout

```
{output_dir}/{run_id}/
  run.json                        # Live run state (status, stage, counts)
  config.snapshot.json            # Frozen config used for this run
  inputs/
    input_summary.json            # Table/schema/PDF metadata
  proposals/
    proposals.jsonl              # Append-only proposal records
    proposal_index.json          # Proposal lookup metadata
  provider_mode.json             # Persisted provider/mode/readiness truth
  evidence/                       # Per-proposal evidence (JSON files)
  review/
    decisions.jsonl               # Append-only review decision log
  summaries/
    run_summary.json              # Final run summary
    reviewer_summary.json         # Reviewer outcome counts
  exports/
    workbook_{ts}.xlsx            # Updated workbook (after export triggered)
    audit_log_{ts}.json           # Decision audit log
    diagnostics_{ts}.json         # Diagnostics and warnings
  logs/                           # Diagnostic logs
```

---

## Provider requirements

LM Studio must be running and have a model loaded before starting a run. The app checks reachability at run start and fails early with a clear error if LM Studio is unreachable.

The canonical provider token is `lm_studio`. No other token is accepted.

Example model IDs (any compatible model may be used):
- Text: `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF`
- Vision: `lmstudio-community/llava-v1.6-mistral-7b-gguf` (optional)

If the provider is unavailable at startup (or the configured model IDs are not available), readiness fails and the run ends in `failed` with an explicit startup error.

---

## Testing

### Backend tests

```bash
python -m pytest tests/backend -v
```

### Frontend tests

```bash
cd frontend
npm run test -- --run
```

### Frontend lint + build

```bash
cd frontend
npm run lint && npm run build
```

### End-to-end tests (opt-in, requires live stack)

```bash
# Start backend and frontend first, then:
pytest tests/e2e -m e2e
```

### Live LM Studio smoke test (opt-in)

```bash
LM_STUDIO_TEXT_MODEL=<model-id> PAPER_TABLE_SMOKE=1 python -m pytest tests/backend/test_smoke_lmstudio.py -v -m smoke
```

---

## Fixtures

Canonical test fixtures are in `tests/fixtures/`:

- `tests/fixtures/tables/literature_fixture.xlsx` — example workbook
- `tests/fixtures/tables/literature_fixture_schema.csv` — column schema
- `tests/fixtures/papers/paper_1.pdf` … `paper_4.pdf` — matched PDFs
- `tests/fixtures/papers/unmatched_1.pdf` — intentionally unmatched PDF

---

## Known MVP limitations

- **LM Studio must be running** at run start. The readiness check fails early with a clear error if unreachable.
- **Content-only export.** Formulas, conditional formatting, filters, frozen panes, merged cells, charts, and macros are not preserved. Changed cells are highlighted in yellow; other formatting is stripped.
- **Partial review is allowed.** Export may proceed with only a subset of proposals reviewed. Only explicitly accepted proposals are written.
- **PDF highlight coordinates** are shown when available. When not available, quote text is shown as a text fallback.
- **No in-place workbook patching.** The export always writes a new XLSX file; the source workbook is never modified.

---

## Development commands reference

| Command | What it does |
|---|---|
| `python -m uvicorn backend.app.main:app --reload` | Start backend (dev, auto-reload) |
| `cd frontend && npm run dev` | Start frontend dev server |
| `cd frontend && npm run build` | Build frontend for production |
| `cd frontend && npm run lint` | Run ESLint |
| `cd frontend && npm run test -- --run` | Run frontend unit tests |
| `python -m pytest tests/backend -v` | Run backend tests |
| `python -m pytest tests/e2e -m e2e` | Run e2e tests (requires live stack) |
