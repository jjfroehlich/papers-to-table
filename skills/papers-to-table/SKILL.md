# papers-to-table (headless extraction) skill

## Purpose

Use this skill when a user wants structured table values extracted from scientific PDFs using the installed papers-to-table app, without browser review.

## When to use

- one spreadsheet/table + schema + PDF folder extraction tasks
- agent/batch workflows that need run bundles and exported tables
- workflows that require auditable evidence and diagnostics artifacts

## When not to use

- when the user expects human-reviewed acceptance but no reviewer is available
- when the app is not installed and installation is out of scope
- when LM/provider readiness is broken and cannot be fixed in-session

## Preconditions

- papers-to-table repo or installed command surface is available
- config JSON exists and points to valid table/schema/PDF inputs
- provider is configured (typically local LM Studio for current default path)

## Setup check

1. Run preflight:
   `python scripts/papers_to_table.py preflight --config app/config.json`
2. Confirm readiness success and resolved paths.
3. If readiness fails, report clear blocker details before extraction.

## Required inputs

- config path (`--config`)
- table file (config or `--table-path` override)
- schema file (config or `--schema-path` override)
- PDF directory (config or `--pdf-dir` override)

## Schema guidance

Schema descriptions are converted into extraction prompts. Before running, inspect descriptions for vague wording, missing units, overloaded concepts, or unclear evidence criteria. If needed, use an LLM to improve the descriptions, then verify that each description states exactly what should be extracted and what evidence is acceptable.

## Headless command pattern

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  [--table-path /abs/table.xlsx] \
  [--schema-path /abs/schema.csv] \
  [--pdf-dir /abs/pdfs] \
  [--accept-all] \
  [--export]
```

Use `--accept-all` only when explicitly requested or clearly appropriate for unattended automation.

## Expected outputs

- machine-readable terminal JSON summary
- run bundle directory under configured output root
- optional exported workbook and audit artifacts when `--export` is used

## Diagnostics to inspect before reporting

At minimum inspect:

- `run.json`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `exports/diagnostics_*.json` (if exported)

Explicitly report:

- unmatched or ambiguous paper matching outcomes
- missing proposals or high no-data/unclear rates
- invalid anchors or weak evidence warnings
- provider/model/degraded-mode warnings
- whether decisions were auto-accepted

## Reporting checklist

Return:

1. exported table path (or explain why no export path exists)
2. run bundle path
3. acceptance mode used (human-reviewed vs auto-accepted)
4. reliability caveats from diagnostics
5. recommended next step (manual review, rerun with fixed config/provider, or eval)

## Safety and trust caveats

- Auto-accepted values are **not human-reviewed**.
- Evidence quality and warnings must be inspected before trust.
- Do not silently overwrite original input tables; export to new artifacts.
- Treat provider-readiness failures as blockers, not soft warnings.
- Treat vague schema descriptions as extraction-risk blockers when the requested fields are ambiguous.

## References

- `references/headless-usage.md`
- `references/diagnostics.md`
- `references/config-template.md`
- manual page: `docs/agents/agent-usage.md`
