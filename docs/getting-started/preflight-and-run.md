# Preflight And Run Commands

Use this page after installation and configuration.

Prerequisites:

- the repo is installed
- LM Studio is running
- `app/config.json` exists

## Preflight From Terminal

Run preflight to confirm the config and provider are ready.

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

Preflight checks:

- config path
- table, schema, and PDF directory
- output directory
- provider token and base URL
- configured model id
- provider/model readiness

## Start The Browser App

Use browser review when you want to inspect extracted values and review them in the UI.

```bash
python scripts/papers_to_table.py review
```

Then open `http://127.0.0.1:5173`.

## Headless Extraction

Use headless mode when you want unattended extraction and export.

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

`--accept-all` means extracted values are auto-accepted without human review.