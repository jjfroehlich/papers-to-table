# Paper Table Agent

Paper Table Agent is a local-first browser application for turning a spreadsheet plus a folder of scientific PDFs into reviewed spreadsheet updates.

The MVP in this repository uses:
- a **React** frontend for run inspection and queue-first review
- a small **FastAPI** backend with an app-owned staged runner that the UI launches asynchronously
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
3. In the browser UI, point the app at your config file and start a run.
4. Review the queue of proposed cell updates.
5. Accept, edit, or reject proposals.
6. Download the updated workbook and audit log from the review workspace or the run artifacts.

## Primary happy path

The intended operator path for MVP is:

1. Edit `my-config.json` so it points at your table, schema, PDFs, and desired artifact output directory.
2. Start the backend.
3. Start the frontend.
4. Open the browser UI.
5. In the run launcher, enter the config path and click `Start run`.
6. Watch the run move through `validating` and `running` states.
7. Once the run is `completed` or `completed with warnings`, review the queue and export accepted changes.

If you switch from one run to another, the app may keep your queue filter, but it reloads proposal detail and evidence for the newly selected run instead of carrying over stale review state from the previous run.

The UI is the primary operational surface for starting and monitoring runs, while the config file remains the main control surface for advanced behavior and reproducibility.

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

Relative paths inside the config file are resolved relative to the config file's directory, not your shell's current working directory.

One exception exists for checked-in repository fixture configs: if a relative path already resolves as written from the repository root, the app preserves that repo-relative path so the bundled fixture configs keep working unchanged.

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

### Start a run from the UI

After the frontend loads:

1. Enter the path to your config file, usually `my-config.json`.
2. Click `Start run`.
3. Confirm the `Run setup` section shows the expected config path, table path, schema path, PDF directory, and artifact root.
4. Wait for the run status to move from `validating` to `running`, then to `completed` or `completed with warnings`.
5. Use the same screen to review proposals, inspect unresolved match warnings, and download the workbook, audit log, summaries, or config snapshot.

The config snapshot is available early in the run lifecycle. Workbook, audit-log, and summary downloads only become meaningful after the run has written those artifacts.

During `running`, expect coarse progress messages such as the current pipeline stage and current item when available, not a full resumable job monitor.

## Sample workflow on the fixture corpus

The normal fixture workflow should still go through the same browser-first operator path:

1. Copy `tests/fixtures/configs/test-config.json` to a local config file if you want to edit paths.
2. Start the backend and frontend.
3. In the browser UI, enter the fixture config path.
4. Start the run from the launcher.
5. Wait for the run to reach `completed` or `completed with warnings`.
6. Review proposals and download outputs from the same UI.

The backend `Runner` remains useful for developer debugging and targeted backend tests, but it is not the primary operator workflow for the product described in this repository.

Unresolved match warnings in the UI are inspect-only in MVP: they show which PDFs were unmatched, ambiguous, or blocked by duplicate-row conflicts and why, but they do not provide direct rematch actions from that screen.

## Backend/frontend development loop

A common local workflow is:

1. Prepare a config file.
2. Start the backend.
3. Start the frontend.
4. Open the browser UI.
5. Confirm the empty or pre-review state tells you what to do next.
6. Start a run from the run launcher using the config path.
7. Review proposals and export accepted changes.

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

If no verified cells have been reviewed yet, the reviewer summary may still show per-column evidence coverage lines. In that case, treat them as coverage context only, not as outcome scores.

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

## Troubleshooting

### The UI says the backend request failed

Make sure the FastAPI server is running on `http://127.0.0.1:8000` and the frontend can reach it.

### Starting a run fails immediately

The backend now returns actionable validation errors for common config problems, including:
- config file not found
- invalid JSON in the config file
- missing table or schema paths
- missing PDF directory
- PDF directory contains no `.pdf` files

Fix the config file first, then start the run again from the UI.

### The run stays in `validating` or `running`

Use the run status message plus the config/setup panel to confirm the right inputs were selected. If the run later fails, inspect the failure message in the UI and the `logs/diagnostics.json` file in the run artifacts.

### The run completed with warnings

This usually means at least one PDF was unmatched, ambiguous, or part of a duplicate-row conflict, or that export warnings were recorded. The run remains reviewable, but the warning surface should be checked before treating the output as clean.
