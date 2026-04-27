# Outputs and artifacts

Main-app runs write bundles under `app/runs/{run_id}/` by default unless `output_dir` is overridden.

Key artifacts:

- `run.json`
- `config.snapshot.json`
- `proposals/proposals.jsonl`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `exports/workbook_*.xlsx`
- `exports/audit_log_*.json`

Use these artifacts as the audit and cross-tool contract surface for eval and optimizer.

Detailed structure: [`run-artifacts.md`](run-artifacts.md).
