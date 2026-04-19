# Main App Documentation

The main app is the product surface of this repository.

It is a local-first review workflow for extracting structured information from scientific papers into a spreadsheet with explicit evidence inspection and explicit export.

## Start here

- Operator workflow: [operator-workflow.md](operator-workflow.md)
- Run artifact reference: [run-artifacts.md](run-artifacts.md)

## Install and run

Run these commands from `app/` unless noted otherwise.

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later and npm
- LM Studio for live proposal generation

### Backend install

```bash
pip install -e ./backend
```

### Frontend install

```bash
cd frontend
npm install
```

### Start the backend

```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

### Start the frontend

```bash
cd frontend
npm run dev
```

## Non-UI automation entrypoint

The browser UI remains the normal human workflow. For tooling, the backend also exposes a stable automation entrypoint:

```bash
python -m backend.app.automation start --config-path config.json
```

Useful variants:

```bash
python -m backend.app.automation start --config-path config.json --wait
python -m backend.app.automation status --run-id <run_id> --output-dir ./runs
python -m backend.app.automation wait --run-id <run_id> --output-dir ./runs
```

## Configuration

Copy the checked-in example and edit it for your table, schema, PDF directory, and model settings.

```bash
cp config.example.json config.json
```

Key config areas:

- input paths: `table_path`, `schema_path`, `pdf_dir`, `output_dir`
- runtime mode: `verify_mode`, `eval_mode`
- provider settings: `provider.*`
- parser settings: `parser.*`
- retrieval settings: `retrieval.*`
- diagnostics and style profiles: `diagnostics.*`, `style_profiles.*`

The canonical provider token is `lm_studio`.

## Review workflow summary

1. Create a run from a JSON config.
2. Review the queue of proposals in the browser.
3. Accept, edit, reject, or confirm no data.
4. Export only when the reviewed workbook is ready.

## Export workflow summary

Exports are manual and explicit.

- `workbook_{timestamp}.xlsx`
- `audit_log_{timestamp}.json`
- `diagnostics_{timestamp}.json`

These are written under `{output_dir}/{run_id}/exports/` only after explicit export.

## Trust and evidence overview

- Evidence types remain labeled rather than collapsed into one generic confidence signal.
- Provider mode and degraded fallback state remain visible in artifacts.
- The app preserves run-bundle provenance for downstream eval and optimizer tooling.
- Review is mandatory for trusted spreadsheet updates.

## Related docs

- Repository landing page: [../../README.md](../../README.md)
- Eval tool docs: [../eval/README.md](../eval/README.md)
- Optimizer docs: [../optimizer/README.md](../optimizer/README.md)
- Contracts: [../contracts/monorepo-layout.md](../contracts/monorepo-layout.md)
