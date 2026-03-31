# Paper Table Agent

A local-first paper-to-table review app. Ingest scientific PDFs and a structured spreadsheet, generate evidence-backed cell proposals, review them in a browser UI, and export audited XLSX updates.

**Current status: Batch 5 — Review workspace.** The full review UI is implemented: proposal queue, detail pane with evidence, PDF viewer with highlights, and decision controls. Export (Batch 6) is not yet available.

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
pip install fastapi "uvicorn[standard]" "pydantic>=2" openpyxl pandas python-multipart httpx
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Start the backend

```bash
uvicorn backend.app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 4. Start the frontend (development)

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

The canonical provider token is `lm_studio`. Tokens such as `lmstudio`, `LMStudio`, or `openai` will produce a clear validation error.

### Key config fields

| Field | Description |
|---|---|
| `table_path` | Path to spreadsheet (XLSX or CSV) |
| `schema_path` | Path to schema CSV (column_name, description) |
| `pdf_dir` | Directory containing PDF files |
| `output_dir` | Where run artifacts are stored (default: `./runs`) |
| `verify_mode` | If `true`, already-filled cells are also extraction targets |
| `provider.token` | Must be `"lm_studio"` |
| `provider.base_url` | LM Studio API base URL (default: `http://localhost:1234`) |
| `provider.text_model.model_id` | ID of the text model loaded in LM Studio |
| `provider.vision_model.model_id` | ID of the vision model (optional) |

---

## Workflow

### 1. Create a run

1. Open `http://localhost:5173` in the browser
2. In the **Run** tab, enter your `config.json` path
3. Optionally expand **optional path overrides** for per-run path overrides
4. Click **Create Run**

The run progresses through: `created → validating → running → completed` (or `completed_with_warnings` / `failed`). Select any run from the list to see stage progress, warnings, and error details.

### 2. Review proposals

When a run reaches `completed` or `completed_with_warnings`, the **Review** tab becomes active.

The review workspace has three panes:

- **Left — Proposal Queue:** Browse proposals grouped by paper or column. Filter by decision status (All / Pending / Accepted / No Data / Rejected). Click a proposal to load it in the center.
- **Center — Proposal Detail:** Shows the proposed value, rationale, evidence list, and row context. Expand rationale to read the model's reasoning. Click an evidence item to jump to it in the PDF viewer.
- **Right — Evidence Viewer:** Renders the source PDF with PDF.js. Navigates automatically to the evidence page. Blue overlays show exact highlights; dashed orange overlays show approximate regions. A text fallback panel appears when exact highlighting is unavailable.

**Decision controls** (bottom of center pane):

| Button | Action |
|---|---|
| **Accept** | Accept the proposed value as-is |
| **Accept with Edit** | Accept with a corrected value |
| **No Data** | Confirm this cell has no data in this paper |
| **Reject** | Reject the proposal |
| **Next →** | Move to next proposal |

**Keyboard shortcuts:**

| Key | Action |
|---|---|
| `A` | Accept |
| `R` | Reject |
| `]` or `N` | Next proposal |
| `[` or `P` | Prev proposal |
| `E` | Focus edit input |
| `?` | Show shortcut help |

The **Unresolved** tab (top of right area) shows unmatched PDFs, ambiguous matches, and duplicate row conflicts for inspection.

### 3. Export / Download

After completing review, export is available in Batch 6 (not yet implemented). The backend download endpoints are in place at:

- `GET /api/runs/{run_id}/downloads/workbook` — updated XLSX workbook
- `GET /api/runs/{run_id}/downloads/audit-log` — decision audit log
- `GET /api/runs/{run_id}/downloads/run-summary` — run_summary.json
- `GET /api/runs/{run_id}/downloads/reviewer-summary` — reviewer_summary.json

These return 404 until export artifacts are generated (Batch 6).

---

## Run artifact layout

```
{run_id}/
  run.json                        # Live run state (status, stage, counts)
  config.snapshot.json            # Frozen config used for this run
  inputs/
    input_summary.json
  proposals/                      # Per-cell proposals
  evidence/                       # Per-proposal evidence
  review/                         # Review decisions
  summaries/
    run_summary.json
    reviewer_summary.json
  exports/                        # Exported workbooks (Batch 6)
```

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

### Frontend build

```bash
cd frontend
npm run build
```

### End-to-end tests (opt-in)

E2e tests require both backend and frontend running:

```bash
# Start backend and frontend first, then:
pytest tests/e2e -m e2e --base-url http://localhost:5173
```

---

## Fixtures

Canonical test fixtures are in `tests/fixtures/`:

- `tests/fixtures/tables/literature_fixture.xlsx` — example workbook
- `tests/fixtures/tables/literature_fixture_schema.csv` — column schema
- `tests/fixtures/papers/paper_1.pdf` … `paper_4.pdf` — matched PDFs
- `tests/fixtures/papers/unmatched_1.pdf` — intentionally unmatched PDF

---

## Known MVP limitations (Batch 5)

- **Export not yet available.** The Review tab supports full triage, but the XLSX export step requires Batch 6.
- **LM Studio must be running** at run start. The readiness check fails early with a clear error if unreachable.
- **PDF highlight coordinates** are shown when available from the extraction pipeline. When not available, quote text is shown as a text fallback.
- **Bulk accept** accepts all pending proposals in the current filtered view — use the filter to scope what you bulk-accept.

---

## Development commands reference

| Command | What it does |
|---|---|
| `uvicorn backend.app.main:app --reload` | Start backend (dev, auto-reload) |
| `cd frontend && npm run dev` | Start frontend dev server |
| `cd frontend && npm run build` | Build frontend for production |
| `cd frontend && npm run test -- --run` | Run frontend unit tests |
| `python -m pytest tests/backend -v` | Run backend tests |
| `python -m pytest tests/e2e -m e2e` | Run e2e tests (requires live stack) |


---

## Architecture

- **Backend:** Python 3.11+, FastAPI, Pydantic v2
- **Frontend:** React + TypeScript + Vite + Tailwind CSS
- **Storage:** Filesystem artifact bundles (JSON files), no database
- **Default provider:** LM Studio (local), via `http://localhost:1234`

---

## Prerequisites

- Python 3.11 or later
- Node.js 18 or later and npm
- [LM Studio](https://lmstudio.ai/) running locally with a model loaded (required for actual proposal generation; Batch 1 pipeline is a stub)

---

## Install and start

### 1. Clone and install backend dependencies

```bash
git clone <repo-url>
cd paper-table-agent
pip install fastapi "uvicorn[standard]" "pydantic>=2" openpyxl pandas python-multipart httpx
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Start the backend

```bash
uvicorn backend.app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 4. Start the frontend (development)

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Configuration

All run parameters are controlled by a JSON config file. See `config.example.json` for a complete example:

```bash
cat config.example.json
```

The canonical provider token is `lm_studio`. The following tokens are **not** accepted and will produce a clear validation error: `lmstudio`, `LMStudio`, `openai`, etc.

### Key config fields

| Field | Description |
|---|---|
| `table_path` | Path to spreadsheet (XLSX or CSV) |
| `schema_path` | Path to schema CSV (column_name, description) |
| `pdf_dir` | Directory containing PDF files |
| `output_dir` | Where run artifacts are stored (default: `./runs`) |
| `verify_mode` | If `true`, already-filled cells are also extraction targets |
| `provider.token` | Must be `"lm_studio"` |
| `provider.base_url` | LM Studio API base URL (default: `http://localhost:1234`) |
| `provider.text_model.model_id` | ID of the text model loaded in LM Studio |
| `provider.vision_model.model_id` | ID of the vision model (optional) |

---

## Running a run

1. Open the browser UI at `http://localhost:5173`
2. In the **Run** tab, enter the path to your config file (e.g. `config.example.json`)
3. Optionally expand **optional path overrides** to override individual paths
4. Click **Create Run**
5. The run moves through: `created → validating → running → completed` (or `failed`)
6. Select the run from the list to see details, stage progress, and any errors

The **Review** tab will be enabled when a run reaches `completed` or `completed_with_warnings` state. Proposal review is implemented in Batch 2.

---

## Run artifact layout

Each run creates a directory under `output_dir/{run_id}/`:

```
{run_id}/
  run.json                        # Live run state (status, stage, counts)
  config.snapshot.json            # Frozen config used for this run
  inputs/
    input_summary.json            # Table/schema/PDF metadata (written early)
  proposals/                      # Per-cell proposals (Batch 2+)
  evidence/                       # Per-proposal evidence (Batch 2+)
  review/                         # Review decisions (Batch 2+)
  summaries/
    run_summary.json              # Final run summary
    reviewer_summary.json         # Reviewer outcome counts
  exports/                        # Exported workbooks (Batch 2+)
  logs/                           # Diagnostic logs (Batch 2+)
```

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

### End-to-end tests (opt-in)

E2e tests require both backend and frontend running. They are skipped by default:

```bash
# Start backend and frontend first, then:
pytest tests/e2e -m e2e --base-url http://localhost:5173
```

---

## Fixtures

Canonical test fixtures are in `tests/fixtures/`:

- `tests/fixtures/tables/literature_fixture.xlsx` — example workbook
- `tests/fixtures/tables/literature_fixture_schema.csv` — column schema
- `tests/fixtures/papers/paper_1.pdf` … `paper_4.pdf` — matched PDFs
- `tests/fixtures/papers/unmatched_1.pdf` — intentionally unmatched PDF

See `tests/fixtures/README.md` for details.

---

## Known limitations (Batch 1)

- **Pipeline is a stub.** Running a run completes successfully but generates no proposals. Parsing, matching, retrieval, and extraction are planned for Batch 2.
- **Review workspace is a placeholder.** The Review tab shows a "coming in Batch 2" message.
- **LM Studio must be running.** The readiness check makes a real HTTP request to `provider.base_url/v1/models`. A run will fail with a clear error if LM Studio is not reachable.
- **No export yet.** Export functionality is planned for a later batch.

---

## Provider requirements

LM Studio must be running and have a model loaded before starting a run. The app checks reachability at run start and fails with an actionable error if LM Studio is unreachable.

Example model IDs (use as reference — any compatible GGUF model works):
- Text: `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF`
- Vision: `lmstudio-community/llava-v1.6-mistral-7b-gguf`

---

## Development commands reference

| Command | What it does |
|---|---|
| `uvicorn backend.app.main:app --reload` | Start backend (dev, auto-reload) |
| `cd frontend && npm run dev` | Start frontend dev server |
| `cd frontend && npm run build` | Build frontend for production |
| `cd frontend && npm run lint` | Run ESLint |
| `cd frontend && npm run test -- --run` | Run frontend unit tests |
| `python -m pytest tests/backend -v` | Run backend tests |
| `python -m pytest tests/e2e -m e2e` | Run e2e tests (requires live stack) |
