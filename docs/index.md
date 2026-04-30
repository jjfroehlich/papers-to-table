# Home

papers-to-table is a local-first system for extracting information from scientific PDFs into structured tables. It combines a browser review app for human review, auditable run bundles, and companion tools for evaluation and optimization.

## What The System Does

- Reads one spreadsheet, one schema, and a directory of PDFs.
- Runs preflight checks before extraction starts.
- Parses and matches PDFs to table rows.
- Proposes evidence-backed values for eligible cells.
- Lets a reviewer accept, edit, reject, or confirm no data.
- Exports a content-only workbook copy plus audit artifacts.

## Primary Workflow

1. Browser mode is the regular workflow which includes human-review or accept-all options.

## Secondary Workflows

1. Command-line interface usage without human-review for agent use or other programmatic use-cases. 
2. Eval tool scores run bundles against benchmark "gold" data.
3. Optimizer tool compares model, prompt, and retrieval studies.