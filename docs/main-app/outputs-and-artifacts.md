# Outputs And Artifacts

Main-app runs write bundles under `app/runs/{run_id}/` by default unless `output_dir` is overridden. A run bundle is the auditable filesystem contract shared with eval and optimizer.

## Main Directories and Files

- `run.json`: current run status and high-level provenance.
- `config.snapshot.json`: config that was used for the run.
- `inputs/`
- `style_profiles/`
- `parsed/`
- `matching/`
- `retrieval/`
- `proposals/`
- `proposals/proposals.jsonl`: persisted proposals.
- `evidence/`
- `review/`
- `review/decisions.jsonl`: append-only review decisions.
- `summaries/`
- `summaries/run_summary.json`: run-level status and warning summary.
- `summaries/reviewer_summary.json`: review queue and decision summary. Records whether automation review was applied and how many proposals were auto-accepted.
- `diagnostics/`
- `exports/`
- `exports/workbook_*.xlsx`: exported workbook copy.
- `exports/audit_log_*.json`: export audit log.
- `exports/diagnostics_*.json`: export diagnostics.

Eval and optimizer companion tools rely on run bundles without importing the main-app runtime, thats why much of the output stays in explicit directories.

## Review Records

- Only explicitly accepted proposals become export candidates.
- Decision sources are recorded: `human_individual`, `human_bulk_accept`, and `automation_accept_all`.
- Headless auto-accept also adds a reviewer note stating that `--accept-all` was used.
