# Troubleshooting

## First diagnostic step

Run terminal preflight:

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

This is the fastest way to confirm resolved inputs, PDF scope, and provider readiness.

## Common issues

### LM Studio not reachable

Symptoms:

- preflight readiness fails
- run exits early with provider readiness errors

Checks:

- LM Studio is running locally
- the config uses `provider.token = "lm_studio"`
- `provider.base_url` points at the local OpenAI-compatible LM Studio endpoint
- the configured model ids are available in LM Studio
- if required test deps are missing, install with `cd app && python -m pip install -e ./backend[test]`

### Model unavailable or structured-output mismatch

Symptoms:

- readiness fails with model errors
- run artifacts show degraded or prompt-only behavior

Checks:

- inspect `run.json` and `summaries/reviewer_summary.json`
- inspect `diagnostics/provider_model_management.json`
- verify the configured model supports the expected structured-output path
- load/download the configured model in LM Studio, then rerun preflight

### Parser issues

Symptoms:

- preflight or run warnings mention parser availability
- PDFs parse poorly or fail early

Checks:

- inspect `parsed/{pdf_id}/diagnostics.json`
- inspect `matching/` and `diagnostics/run_stats.json`
- confirm parser dependencies are installed in the active environment

### Headless export refused

Symptoms:

- headless run ends with `review_required`

Cause:

- you asked for `--export` while reviewable proposals were still pending and `--accept-all` was not provided

Fix:

- use browser review, or
- rerun with `--accept-all --export` if unattended export is intentionally acceptable

### Eval confusion

Remember:

- eval scores run bundles; it does not run extraction
- missing or weak judge settings can change text-field scoring behavior
- comparison outputs are written under the eval `--out` directory

### Optimizer confusion

Remember:

- optimizer orchestrates main app + eval; it is not another extraction runtime
- smoke configs are only for contract checks
- real benchmark configs should not silently use fixture inputs