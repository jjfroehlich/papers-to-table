# Headless And Accept-All

Use headless mode when a terminal workflow or coding agent needs to run the app. This is without reviewing the extracted values and browser UI. 

## Recommended Command

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

## Optional Path Overrides

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --table-path /absolute/path/to/table.xlsx \
  --schema-path /absolute/path/to/schema.csv \
  --pdf-dir /absolute/path/to/pdfs \
  --accept-all \
  --export
```

## Required Inputs

- table file
- schema file
- PDF directory
- main-app JSON config
- output directory from the config

You can keep paths in the config or override them on the command line.

## Accept-All

- `--accept-all` is just to make it explicit that review is bypassed. Auto-accepted proposals are obviously not human-reviewed.
- `--export` without explicit review or `--accept-all` is rejected when reviewable proposals are still pending.
- The output artifacts will record that extracted information was auto-accepted.

## Machine-Readable Result

The command prints JSON that includes:

- resolved config and inputs
- preflight summary
- run id and status
- artifact paths
- reviewer summary
- export paths when `--export` is used
- auto-accepted proposal count when `--accept-all` is used

## Audit Files To Inspect

- `run.json`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `exports/audit_log_*.json`
- `exports/diagnostics_*.json`

## Avoiding Over-Trust

- Inspect `reviewer_summary.json` and `run_summary.json` for degraded-mode or warning truth.
- Inspect `review/decisions.jsonl` and `exports/audit_log_*.json` before using exported values downstream.
- Inspect evidence and matching diagnostics inside the run bundle when values matter.

## Decision Sources

- `human_individual`: manually reviewed proposal decisions.
- `human_bulk_accept`: UI bulk-accept decisions across multiple pending proposals.
- `automation_accept_all`: headless or agent `--accept-all` decisions without individual human review.