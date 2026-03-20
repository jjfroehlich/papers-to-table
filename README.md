# Paper Table Agent

Paper Table Agent is a local-first browser application for turning a spreadsheet plus a folder of scientific PDFs into reviewed spreadsheet updates.

The MVP in this repository uses:
- a **React** frontend for run inspection and queue-first review
- a small **FastAPI** backend with a synchronous staged runner
- **filesystem artifact bundles + JSON files** as the canonical state
- **LM Studio localhost API** as the live provider path, with a deterministic stub path for default tests
- **content-only XLSX export** with changed-cell highlighting and an audit log

## How to use it

In plain language, the workflow is:

**Input**
- a `.xlsx` or `.csv` table with one row per paper
- required row-matching columns named `Title`, `Authors`, and `Publication Year`
- one target column for each value you want extracted
- a schema file or workbook schema tab describing what each target column means
- a folder of paper PDFs
- one JSON config file telling the app where those inputs live and which runtime options to use

**What the app does**
1. Loads your config, table, schema, and PDF folder.
2. Matches each PDF to at most one spreadsheet row.
3. Extracts one best proposal per eligible cell, with evidence and support labels.
4. Lets you review proposals in the browser with a queue/detail/evidence workspace, run metrics, and export downloads.
5. Exports a new workbook containing only the changes you explicitly accepted.

**Typical review loop**
1. Prepare your table, schema, PDFs, and config.
2. Start the backend and frontend.
3. Create or inspect a run.
4. Review the queue of proposed cell updates.
5. Accept, edit, or reject proposals.
6. Download the updated workbook and audit log from the review workspace or the run artifacts.

## Repo structure

- `backend/` — FastAPI app, staged runner, parsing/matching/extraction/export logic
- `frontend/` — React review UI and Playwright/Vitest harness
- `tests/backend/` — backend unit/integration/smoke tests
- `tests/e2e/` — Playwright review-workflow coverage
- `tests/fixtures/` — deterministic tables, schema, PDFs, and parser sidecars
- `docs/engineering-lessons/` — compounding engineering notes
- `specs/` — spec, plan, research, and task checklist

## Clone and install from scratch

### 1. Clone the repo

```bash
git clone https://github.com/jjfroehlich/paper-table-agent
cd paper-table-agent
```

### 2. Install the backend

The backend uses the root Python project.

```bash
python -m pip install -e .[dev]
```

### 3. Install the frontend

```bash
cd frontend
npm install
cd ..
```

## Config file: what it does

The app is controlled by a single JSON config file such as `config.example.json`.

That config file tells the app:
- where the table lives
- where the schema lives
- where the PDFs live
- where output artifacts should be written
- which parser/OCR settings to use
- which retrieval and provider settings to use
- whether Verify mode and figure fallback are enabled
- how export highlighting should behave

The config is the main reproducibility surface for a run. At run start, the backend resolves defaults and writes a `config.snapshot.json` into the run artifact bundle so the run can be inspected later.

### Start from the example config

```bash
cp config.example.json my-config.json
```

Then edit the paths and provider/model settings to match your local files and LM Studio setup.

## LM Studio setup

The live provider path in this repository expects an **LM Studio localhost API** endpoint, typically at:

```text
http://127.0.0.1:1234/v1
```

Practical guidance:
- You need a **capable text/reasoning model** for extraction, matching adjudication, and schema-driven response generation.
- You need a **vision-capable model** only if scoped automatic figure fallback is enabled and actually needed for a run.
- The default test path uses the repository's deterministic stub provider, so LM Studio is not required for routine automated tests.

Helpful model categories/examples:
- reasoning / extraction: recent instruction-tuned models in the Qwen, Llama, or similar reasoning-capable families
- embeddings if you extend retrieval locally: local embedding models such as Nomic or BGE families can be reasonable choices
- vision fallback: multimodal/vision-capable variants of your chosen local model family

Do not overfit to one exact model name. The important requirement is that the configured model can reliably produce structured JSON responses for the app's extraction contracts, and that a separate vision-capable model is available if figure fallback is used.

Optional note: LM Studio can also proxy some cloud-backed providers if you configure that locally, but the repository's MVP architecture still assumes the LM Studio localhost API contract first.

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

## Sample workflow on the fixture corpus

Create a run against the deterministic fixture corpus:

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

## Backend/frontend development loop

A common local workflow is:

1. Prepare a config file.
2. Start the backend.
3. Start the frontend.
4. Open the browser UI.
5. Create or inspect a run.
6. Review proposals and export accepted changes.

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

The Playwright e2e harness uses a dedicated `artifacts/e2e/` output root so its fixture run data does not get mixed with normal local runs.

## Verify mode

Verify mode is enabled by default in the config. When enabled, already-filled cells are still sent through the same extraction path so the reviewer can compare the proposal to the existing value and record reviewer-outcome summaries.

## Export fidelity boundary

The MVP export guarantee is intentionally narrow:
- preserved cell contents
- accepted changes applied to a new XLSX workbook
- changed cells highlighted

The MVP does **not** guarantee preservation of workbook formatting or workbook behavior such as:
- formulas
- filters
- frozen panes
- hidden rows or columns
- merged cells
- comments
- charts
- shapes
- macros
- conditional formatting
- named ranges

This boundary is intentional. The app preserves content-level spreadsheet updates plus changed-cell highlighting; it does not promise full workbook fidelity.

## Testing

### Backend tests

```bash
bash scripts/test_backend.sh
```

### Frontend tests

```bash
bash scripts/test_frontend.sh
```

### Playwright e2e tests

```bash
bash scripts/test_e2e.sh
```

The e2e harness now prepares fixture run data separately and starts backend/frontend servers without shell heredocs or shell command chaining.

If the environment is missing a runnable Playwright browser, install one with:

```bash
cd frontend
npx playwright install chromium
cd ..
```

If browser execution is blocked by missing system libraries or container restrictions, the Playwright startup failure should report that as an environment limitation instead of presenting it as an application failure.

### Full test pass

```bash
bash scripts/test_all.sh
```
