# Main app: human-review workflow

The main app is the primary product surface.

Use it when a human needs to inspect evidence, accept or edit proposals, reject weak outputs, and export an audited workbook.

## Recommended command

From the repository root:

```bash
python scripts/papers_to_table.py review
```

This starts the backend and frontend together for the browser review workflow.

## Before you start

1. Copy `app/config.example.json` to `app/config.json` and point it at your table, schema, and PDF directory.
2. Confirm LM Studio is running if you want live proposal generation.
3. Run terminal preflight if you want a quick readiness check before opening the UI:

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

## Browser workflow

1. Open `http://127.0.0.1:5173`.
2. In the **Run** tab, choose the config and any staged overrides.
3. Run **Preflight** to confirm resolved inputs, scope, and provider readiness.
4. Start extraction.
5. Review the queue in the browser workspace.
6. Accept, edit, reject, or confirm no data for proposals.
7. Export the audited workbook explicitly.

## What the UI is responsible for

- launch and preflight clarity
- live run-state visibility
- evidence inspection
- decision recording
- export and artifact download

The UI is intentionally not the advanced-settings authority. Advanced runtime control stays in JSON config.

## Lower-level commands

These remain useful when you only want one process:

```bash
bash scripts/run-main-backend.sh
bash scripts/run-main-frontend.sh
bash scripts/test-main-backend.sh
bash scripts/test-main-frontend.sh
```

## Detailed references

- Screenshot-backed walkthrough: [`operator-workflow.md`](operator-workflow.md)
- Run-bundle layout: [`run-artifacts.md`](run-artifacts.md)
- Headless mode: [`../headless-agent.md`](../headless-agent.md)
- Config reference: [`../configuration.md`](../configuration.md)
