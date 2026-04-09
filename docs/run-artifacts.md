# Run artifacts reference

This document explains the run output bundle at:

- `{output_dir}/{run_id}/`

It is based on actual backend artifact writes and API reads.

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

A directory can still be empty when its stage has no records (for example, no accepted proposals means `exports/` has no workbook yet).

### Root files

- `run.json`: live run status, stage, counters, provider mode truth, warnings, artifact pointers, and versioned artifact-contract fields such as `artifact_schema_version`, `proposal_schema_version`, and `evidence_schema_version`.
- `config.snapshot.json`: frozen resolved run config.

## Detailed contents by section

### `inputs/`

- `input_summary.json`: normalized metadata about table/schema/pdfs and run mode context.
- `gold_table*`: eval mode only.
- `masked_working_table*`: eval mode only.

Condition notes:

- Eval-mode table snapshots are present only when `eval_mode=true`.

### `style_profiles/`

- One JSON file per schema column with output-shape guidance.

Condition notes:

- Produced during the style-profile stage.
- Files may be sparse for unusual schemas but the folder is part of the normal pipeline.

### `parsed/`

Per PDF directory layout:

- `parsed/{pdf_id}/parsed_document.json`
- `parsed/{pdf_id}/page_text.json`
- `parsed/{pdf_id}/diagnostics.json`
- `parsed/{pdf_id}/pages/page_####.png`
- `parsed/{pdf_id}/figures/*.png` (when figure crops are available)
- `parsed/{pdf_id}/crops/*.png` (on-demand evidence crop rendering)

Condition notes:

- Figure and crop subfolders depend on parser outputs and evidence/figure workflows.

### `matching/`

- `match_results.json`
- `match_summary.json`
- `unmatched.json`
- `ambiguous.json`
- `conflicts.json`

Condition notes:

- These files are written each run (lists may be empty).

### `retrieval/`

- `retrieval/{pdf_id}/{column_name}.json` for retrieval results used by extraction.

Condition notes:

- Populated per processed (pdf, column) pair.
- A run with zero eligible cells can leave this section empty.

### `proposals/`

- `proposals.jsonl`: append-only proposal records.
- `proposal_index.json`: lookup/index metadata.

Condition notes:

- Proposal index presence depends on pipeline completion state.

### `evidence/`

- Per-proposal evidence JSON records.
- `evidence.jsonl`: append-only evidence sidecar for downstream tools.

Condition notes:

- Populated when extraction produces evidence items.

### `review/`

- `decisions.jsonl`: append-only review decisions.
- `history/*.json`: per-proposal decision history files, created when decisions are recorded.

Condition notes:

- Empty until reviewers act.

### `summaries/`

- `provider_mode.json`
- `run_summary.json`
- `reviewer_summary.json`
- `artifact_summary.json`

Condition notes:

- Summary files are persisted as the pipeline and review flow progress.
- `reviewer_summary.json` can be provisional when little or no review has been completed.

### `diagnostics/`

- `run_stats.json`
- `provider_diagnostics.json`
- `provider_probe.json`
- `provider_model_management.json`
- `provider_request_counts.json`
- `provider_trace.jsonl`

Condition notes:

- `provider_trace.jsonl` is most useful when verbose provider diagnostics are enabled.
- Some diagnostics can be absent on early failure paths; `artifact_summary.json` reports expected/present status.

### `exports/`

- `workbook_{timestamp}.xlsx`
- `audit_log_{timestamp}.json`
- `diagnostics_{timestamp}.json`

Condition notes:

- Export files are written only after explicit export action from review/API export endpoint.

## Removed unused folder

`logs/` was previously scaffolded but never written/read by runtime paths. It has been removed from the run bundle scaffold so output directories now reflect real artifact producers.

## Quick operator guidance

- Need user-facing outputs: check `exports/` and `summaries/`.
- Need run/provenance truth: check `run.json`, `config.snapshot.json`, `summaries/provider_mode.json`.
- Need debugging detail: check `diagnostics/`, `matching/`, `parsed/`, and `retrieval/`.
