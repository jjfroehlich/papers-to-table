# Browser Review

Browser review is the primary workflow where the user can inspect evidence, and accept or edit proposals. 

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
- Use the selected-run detail pane to confirm labeled runtime details such as run mode, provider mode, provider, models, warnings, and resolved input locators without relying on ambiguous chips.

![Run screen screenshot](../screenshots/run-screen-cleanup.png)

## Review Workspace

![Review workspace screenshot](../screenshots/review-workspace.png)

- The default review viewport: review list on the left, proposal detail and decisions in the middle, and evidence/PDF inspection on the right.
- The **left pane** opens in *As Table* mode and can switch to *By Paper* or *By Column* for grouped triage. The screenshot above uses *By Paper* mode so the set of extraction fields is immediately visible. 
- The **middle pane** shows the selected paper, field, proposed value, evidence list, and review actions. 
- The **right pane** holds the PDF viewer, and the evidence selected in the center is highlighted in the PDF.

## Evidence Semantics

- Proposal records use these semantics: `proposal_status`, `evidence_status`, derived/validated `review_bucket`, and `reason_codes`.
- `"Direct quote"`: exact highlight anchored to page text.
- `"Approximate highlight"`: region-level fallback when exact quote alignment fails.
- `"Quote plus page"`: text fallback with page reference when highlight geometry is unavailable.
- `"Inferred reasoning or calculation"`: reviewer-visible evidence statuses that stay distinct from direct quotes.
- `"Figure evidence"`, when present, is labeled separately from text evidence.

## Diagnostics Drawer

![Diagnostics screenshot](../screenshots/review-diagnostics-open.png)

## Scrollable Review Surfaces

![Queue scrolled screenshot](../screenshots/review-queue-scrolled.png)

![Evidence scrolled screenshot](../screenshots/review-evidence-scrolled.png)

## Explicit Export

![Export and diagnostics screenshot](../screenshots/export-diagnostics.png)

1. Review proposals in the browser.
2. Accept only the values you want recorded.
3. Click "Export reviewed workbook".
4. Download the workbook and JSON artifacts, or open them directly from `{output_dir}/{run_id}/exports/`.

Only explicitly accepted values are exported. Rejected, unreviewed, and confirmed-no-data outcomes are excluded.
