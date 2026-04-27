# Headless and accept-all

Use headless mode for terminal/agent/batch workflows.

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

## Required clarity

- `--accept-all` is explicit review bypass.
- Auto-accepted proposals are **not human-reviewed**.
- Always inspect diagnostics and evidence before downstream trust.
- Export should write a new workbook; never silently overwrite source inputs.

## What to inspect after headless runs

- `run.json`
- `summaries/reviewer_summary.json`
- `summaries/run_summary.json`
- `review/decisions.jsonl`
- `exports/audit_log_*.json`
- `exports/diagnostics_*.json`

Full agent-oriented guidance: [`../headless-agent.md`](../headless-agent.md).
