# Run artifacts reference

A main-app run writes a bundle at `{output_dir}/{run_id}/`.

The run bundle is the auditable filesystem contract shared with eval and optimizer.

## Main directories

- `inputs/`
- `style_profiles/`
- `parsed/`
- `matching/`
- `retrieval/`
- `proposals/`
- `evidence/`
- `review/`
- `summaries/`
- `diagnostics/`
- `exports/`

## Files most operators need first

- `run.json`: current run status and high-level provenance
- `config.snapshot.json`: resolved config used for the run
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `exports/workbook_*.xlsx`
- `exports/audit_log_*.json`
- `exports/diagnostics_*.json`

## Review and export truth

- only explicitly accepted proposals become export candidates
- `review/decisions.jsonl` is append-only
- headless `--accept-all` records `decision_source="automation_accept_all"`
- headless auto-accept also adds a reviewer note stating that `--accept-all` was used
- `summaries/reviewer_summary.json` records whether automation review was applied and how many proposals were auto-accepted

## Eval and optimizer relevance

Eval and optimizer rely on this bundle without importing the main-app runtime.

That is why the bundle keeps run state, proposals, evidence, summaries, and exports in explicit directories instead of hiding important truth in transient logs.
