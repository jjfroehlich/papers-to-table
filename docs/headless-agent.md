# Headless and agent usage

Use headless mode when a coding agent, batch script, or terminal-only workflow needs a run bundle and exported table without the browser UI.

## When an agent should use papers-to-table

Use papers-to-table when the task is:

- extract structured values from one spreadsheet plus a set of PDFs
- preserve evidence and diagnostics for later audit
- keep a full run bundle that eval can score later
- produce an updated table while making auto-accept explicit

Do **not** treat headless output as self-verifying. The artifacts must remain auditable.

## Required inputs

- table file
- schema file
- PDF directory
- main-app JSON config
- output directory from the config

You can keep paths in the config or override them on the command line.

## Recommended command

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

Optional path overrides:

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --table-path /absolute/path/to/table.xlsx \
  --schema-path /absolute/path/to/schema.csv \
  --pdf-dir /absolute/path/to/pdfs \
  --accept-all \
  --export
```

## Important safety rules

- `--accept-all` is required for unattended review bypass.
- `--export` without explicit review or `--accept-all` is rejected when reviewable proposals are still pending.
- Headless artifacts record that proposals were auto-accepted.
- Manual browser review remains the default human path.

## What headless mode returns

The command prints machine-readable JSON that includes:

- resolved config and inputs
- preflight summary
- run id and status
- artifact paths
- reviewer summary
- export paths when `--export` is used
- auto-accepted proposal count when `--accept-all` is used

## Where the audit truth lives

Inspect these files in the run bundle:

- `run.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `exports/audit_log_*.json`
- `exports/diagnostics_*.json`

Headless auto-accept records use `decision_source="automation_accept_all"` and a reviewer note stating that `--accept-all` was used.

## How to avoid over-trusting weak proposals

- inspect `reviewer_summary.json` and `run_summary.json` for degraded-mode or warning truth
- inspect `review/decisions.jsonl` and `exports/audit_log_*.json` before using exported values downstream
- inspect evidence and matching diagnostics inside the run bundle when values matter
- run eval if gold data exists

## If gold data exists

Run eval on the emitted run bundle:

```bash
python scripts/papers_to_table.py eval \
  --run /absolute/path/to/run_bundle \
  --gold /absolute/path/to/gold.csv \
  --schema /absolute/path/to/schema.json \
  --out /absolute/path/to/eval_out
```
