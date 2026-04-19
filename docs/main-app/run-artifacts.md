# Run artifacts reference

This document explains the run output bundle at `{output_dir}/{run_id}/`.

## Why there are many folders

The app stores launch inputs, parsing outputs, matching diagnostics, retrieval context, extraction proposals, review decisions, summaries, and explicit export outputs as separate artifact groups.

This separation is intentional:

- reviewer-facing outputs are easy to find
- diagnostics stay inspectable for debugging and trust
- eval-mode provenance can be preserved for downstream scoring

## Folder-level contract

### Always scaffolded run directories

These directories are created when a run bundle is initialized:

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

A directory can still be empty when its stage has no records.

### Root files

- `run.json`: live run status, stage, counters, provider mode truth, warnings, artifact pointers, and versioned artifact-contract fields.
- `config.snapshot.json`: frozen resolved run config.

## Detailed contents by section

### `inputs/`

- `input_summary.json`: normalized metadata about table, schema, PDFs, and run mode context.
- `gold_table*`: eval mode only.
- `masked_working_table*`: eval mode only.

### `style_profiles/`

- One JSON file per schema column with output-shape guidance.

### `parsed/`

Per PDF directory layout:

- `parsed/{pdf_id}/parsed_document.json`
- `parsed/{pdf_id}/page_text.json`
- `parsed/{pdf_id}/diagnostics.json`
- `parsed/{pdf_id}/pages/page_####.png`
- `parsed/{pdf_id}/figures/*.png` when figure crops are available
- `parsed/{pdf_id}/crops/*.png` for on-demand evidence crop rendering

### `matching/`

- `match_results.json`
- `match_summary.json`
- `unmatched.json`
- `ambiguous.json`
- `conflicts.json`

### `retrieval/`

- `retrieval/{pdf_id}/{column_name}.json` for retrieval results used by extraction.

### `proposals/`

- `proposals.jsonl`: append-only proposal records.
- `proposal_index.json`: lookup/index metadata.

### `evidence/`

- Per-proposal evidence JSON records.
- `evidence.jsonl`: append-only evidence sidecar for downstream tools.

### `review/`

- `decisions.jsonl`: append-only review decisions.
- `history/*.json`: per-proposal decision history files, created when decisions are recorded.

### `summaries/`

- `provider_mode.json`
- `run_summary.json`
- `reviewer_summary.json`
- `artifact_summary.json`

### `diagnostics/`

- `run_stats.json`
- `provider_diagnostics.json`
- `provider_probe.json`
- `provider_model_management.json`
- `provider_request_counts.json`
- `provider_trace.jsonl`

### `exports/`

- `workbook_{timestamp}.xlsx`
- `audit_log_{timestamp}.json`
- `diagnostics_{timestamp}.json`

Export files are written only after explicit export action from the review UI or export endpoint.

## Removed unused folder

`logs/` was previously scaffolded but never written or read by runtime paths. It has been removed from the run bundle scaffold so output directories reflect real artifact producers.

## Quick operator guidance

- Need user-facing outputs: check `exports/` and `summaries/`.
- Need run and provenance truth: check `run.json`, `config.snapshot.json`, and `summaries/provider_mode.json`.
- Need debugging detail: check `diagnostics/`, `matching/`, `parsed/`, and `retrieval/`.