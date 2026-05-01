# Browser Review

Browser review is the primary workflow where the user can inspect evidence, and accept or edit proposals. The main app ingests PDFs and a spreadsheet that defines the required information, proposes evidence-backed values, supports review in a browser UI, and exports the results as a spreadsheet.

## Start The App

From the repository root:

```bash
python scripts/papers_to_table.py review
```

Then open `http://127.0.0.1:5173`.

## Before You Start

1. Confirm LM Studio is running with the configured model loaded or available.
2. Prepare a table and schema.
3. Keep `app/config.json` for provider, parser, retrieval, prompt, diagnostics, and figure-review settings.
4. Leave `table_path`, `schema_path`, `pdf_dir`, and `output_dir` blank if you prefer to select them in the browser.

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

## Run Setup

![Run setup screenshot](../screenshots/run-setup.png)

- Start from the Run tab.
- Select the table, schema, PDF files, and output directory in the interface, or type backend-readable paths.
- If those paths are already present in `app/config.json`, they are used as defaults and can still be overridden for a single run.
- Use **Check setup** when you want to preview resolved inputs, runtime locators, table/schema/PDF scope, and provider readiness.
- Use **Start run** to run preflight and, if it passes, continue directly into extraction.

## Review Workspace

![Review workspace screenshot](../screenshots/review-workspace.png)

- The queue defaults to actionable pending proposals and supports grouped triage by paper or column.
- The detail pane keeps the selected paper, field, proposed value, and ordered evidence list together.
- The evidence panel stays focused on the selected evidence item.
- Unmatched, ambiguous, duplicate-conflict, and warning context lives in diagnostics instead of competing with evidence in the same panel.
- The workspace preserves keyboard shortcuts and explicit review actions.

## Evidence Semantics

- Direct quote: exact highlight anchored to page text.
- Approximate highlight: region-level fallback when exact quote alignment fails.
- Quote plus page: text fallback with page reference when highlight geometry is unavailable.
- Inferred reasoning or calculation: reviewer-visible support types that stay distinct from direct quotes.
- Figure evidence, when present, is labeled separately from text evidence.

## Provider, Parsing, And Fallback Truth

- The canonical live provider token is `lm_studio`.
- The UI surfaces provider mode directly: `live local`, `live cloud`, `unavailable`, `disabled`, or `stub/demo` when applicable.
- If the configured live provider is unavailable at startup, the run fails during readiness check.
- Parsing fallback, OCR fallback, duplicate conflicts, and evidence fallback should stay visible through warnings, summaries, and the diagnostics surface.

## Explicit Export

![Export and diagnostics screenshot](../screenshots/export-diagnostics.png)

1. Review proposals in the browser.
2. Accept only the values you want recorded.
3. Click "Export reviewed workbook".
4. Download the workbook and JSON artifacts, or open them directly from `{output_dir}/{run_id}/exports/`.

Only explicitly accepted values are exported. Rejected, unreviewed, and confirmed-no-data outcomes are excluded.
