# papers-to-table

The main product in this repository is a local-first paper-to-table review app.

It ingests scientific PDFs and a structured spreadsheet, proposes evidence-backed cell values, lets a human reviewer inspect the evidence in a browser UI, and exports an audited XLSX only after explicit review.

## What the main app does

- Runs extraction from a JSON config and a folder of PDFs.
- Keeps review, evidence inspection, and export in a browser workflow.
- Persists run bundles with diagnostics, evidence, and reviewer summaries.
- Produces explicit audited exports instead of silently modifying the source workbook.

## Install and run the main app

Run the main-app commands below from `app/`.

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later and npm
- LM Studio running locally for live proposal generation

### Backend install

```bash
git clone https://github.com/jjfroehlich/papers-to-table.git
cd papers-to-table/app
pip install -e ./backend
```

### Frontend install

```bash
cd frontend
npm install
```

### Start the backend

```bash
cd /path/to/repo/app
python -m uvicorn backend.app.main:app --reload --port 8000
```

### Start the frontend

```bash
cd /path/to/repo/app/frontend
npm run dev
```

Open `http://localhost:5173`.

Detailed setup, config, automation, and artifact documentation lives in [docs/main-app/README.md](docs/main-app/README.md).

## Review workflow

The browser UI is the primary operator surface.

1. Create a run from a JSON config.
2. Review proposals in the evidence-backed queue.
3. Accept, edit, reject, or confirm no data.
4. Export only after explicit reviewer action.

Screenshot-backed workflow details live in [docs/main-app/operator-workflow.md](docs/main-app/operator-workflow.md).

## Export workflow

Exports are always explicit.

- The reviewer clicks **Export reviewed workbook**.
- The app writes the workbook, audit log, and diagnostics under the run bundle.
- Only accepted decisions are written back.

Run-bundle structure and export artifact details live in [docs/main-app/run-artifacts.md](docs/main-app/run-artifacts.md).

## Trustworthiness and evidence

The app is designed to keep support visible rather than hiding fallback behavior.

- Evidence types stay distinct: exact highlights, approximate highlights, quote-plus-page fallback, reasoning, and figure evidence.
- Provider mode and degraded fallback states are recorded in run artifacts.
- Review remains manual; proposal presence is not treated as proof.
- Export is never automatic.

## Companion tools

This repository also includes two internal developer tools:

- Eval: benchmarking and scoring for run bundles. See [docs/eval/README.md](docs/eval/README.md).
- Optimizer: bounded calibration and orchestration for compare/optimize studies. See [docs/optimizer/README.md](docs/optimizer/README.md).

These tools support development and benchmarking. They are not the primary product surface.

## Documentation map

- Main app docs: [docs/main-app/README.md](docs/main-app/README.md)
- Eval docs: [docs/eval/README.md](docs/eval/README.md)
- Optimizer docs: [docs/optimizer/README.md](docs/optimizer/README.md)
- Contracts and monorepo notes: [docs/contracts/monorepo-layout.md](docs/contracts/monorepo-layout.md)