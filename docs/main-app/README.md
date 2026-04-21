# Main App Documentation

The main app is the product surface of this repository.

It is a local-first review workflow for extracting structured information from scientific papers into a spreadsheet with explicit evidence inspection and explicit export.

## Start here

- Operator workflow and screenshots: [operator-workflow.md](operator-workflow.md)
- Run artifact reference: [run-artifacts.md](run-artifacts.md)
- Contributor quickstart: [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
- Normative spec owner: [../../specs/product/main-app.md](../../specs/product/main-app.md)

## Install and run

Run these commands from the repo root unless noted otherwise.

### Install

```bash
cd app
python -m pip install -e ./backend[test]
cd frontend
npm install
cd ../..
```

### Start backend and frontend

```bash
bash scripts/run-main-backend.sh
bash scripts/run-main-frontend.sh
```

## Wrapper-script verification

Run these commands from the repository root:

```bash
bash scripts/test-main-backend.sh
bash scripts/test-main-frontend.sh
bash scripts/verify-main-app-full.sh
```

## Current operator workflow summary

1. Use the **Run** tab to point at a config and any one-run staged overrides.
2. Run preflight to inspect resolved inputs, provider readiness, and scope.
3. Start the run when the preflight context is acceptable.
4. Follow live status updates in the browser while the backend runs.
5. Review proposals in the queue-first workspace.
6. Open the diagnostics surface for unresolved matching issues and warnings when needed.
7. Export explicitly after review.

## Non-UI automation entrypoint

The browser UI remains the normal human workflow. For tooling, the backend also exposes a stable automation entrypoint:

```bash
cd app
python -m backend.app.automation start --config-path config.json
```

Useful variants:

```bash
cd app
python -m backend.app.automation start --config-path config.json --wait
python -m backend.app.automation status --run-id <run_id> --output-dir ./runs
python -m backend.app.automation wait --run-id <run_id> --output-dir ./runs
```

## Configuration

Copy the checked-in example and edit it for your table, schema, PDF directory, and model settings.

```bash
cd app
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

## Related docs

- Repository landing page: [../../README.md](../../README.md)
- Docs map: [../README.md](../README.md)
- Eval tool docs: [../eval/README.md](../eval/README.md)
- Optimizer docs: [../optimizer/README.md](../optimizer/README.md)
