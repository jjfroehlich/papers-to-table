# Browser Review

Browser review is the primary workflow where the user can inspect evidence, and accept or edit proposals. 

## Start The App

From the repository root:

```bash
python scripts/papers_to_table.py review
```

Then open `http://127.0.0.1:5173`.

To open the app with another existing runs directory selected for this launch:

```bash
python scripts/papers_to_table.py review \
  --runs-dir "C:/path/to/project/runs"
```

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
- The **Runs directory** above the run list controls which existing run bundles are shown. Type a backend-readable path and press Enter or leave the field, or click **Browse...** for the native folder chooser on Windows or macOS. If a graphical chooser is unavailable, enter the path manually. The last successfully used directory is remembered; **Reset to default** returns to `app/runs/`.
- The Runs directory does not change the separate **Output directory** in Create Run. Existing bundles are read in place and are never copied into the repository.
- Use the selected-run detail pane to confirm labeled runtime details such as run mode, provider mode, provider, models, and resolved input locators without relying on ambiguous chips.
- Completed and completed-with-warnings runs expose **Start human review** in the selected-run header as a direct route to the existing Review workspace.

![Run screen screenshot](../screenshots/run-screen-cleanup.png)

## Review Workspace

![Review workspace screenshot](../screenshots/review-workspace.png)

- The default review viewport: review list on the left, proposal detail and decisions in the middle, and evidence/PDF inspection on the right.
- The **left pane** opens in *As Table* mode and can switch to *By Paper* or *By Column* for grouped triage. The screenshot above uses *By Paper* mode so the set of extraction fields is immediately visible. 
- Select several proposal cells with Ctrl/Command-click, use Shift-click for a contiguous queue range or table rectangle, or hold the primary mouse button and drag a rectangle across table cells. Only proposal-backed cells inside the rectangle become actionable. The selection bar can Accept, Reject, or mark No data after confirmation. It skips reviewed cells unless **Replace the existing decision** is explicitly checked.
- The **middle pane** leads with a centered pale-grey field header so the target column is clearly distinct from the proposed value without resembling an action button. Two separate disclosures follow Evidence: **Details** contains the field description and paper metadata, while **Diagnostics** keeps status and evidence flags plus reviewer-relevant exceptions. Competing or unclear candidates use readable source names; Selection appears for ambiguity or failure, Retrieval for exceptional outcomes or nonstandard evidence routes, and Metadata for conflicts or failure. Redundant evidence-item counts, routine single-candidate selection, normal zero counts, raw diagnostic tokens, provider timings, raw model responses, query strings, figure-planning internals, and similar development telemetry stay out of the primary review surface. Disclosure headers use the same compact uppercase label treatment as the other center-pane sections, with an adjacent triangle showing the collapsed or expanded state. Each disclosure keeps its open or closed state while moving between proposals; Value and Rationale are not repeated in either one.
- The **right pane** holds the PDF viewer, and the evidence selected in the center is highlighted in the PDF.
- The decision controls are centered beneath the proposal content so the primary review actions remain visually anchored in the middle pane.
- Keyboard shortcuts mirror spatial movement: `A`/left and `D`/right move between proposals, `W`/up accepts, `S`/down rejects, Ctrl/Command plus left/right switches evidence, and `E` focuses editing. Shift is reserved for range/rectangle selection. Shortcuts are disabled while typing in a form control.

## Evidence Semantics

- Proposal records use these semantics: `proposal_status`, `evidence_status`, derived/validated `review_bucket`, and `reason_codes`.
- `"Direct quote"`: exact highlight anchored to page text.
- `"Approximate highlight"`: region-level fallback when exact quote alignment fails.
- `"Quote plus page"`: text fallback with page reference when highlight geometry is unavailable.
- `"Inferred reasoning or calculation"`: reviewer-visible evidence statuses that stay distinct from direct quotes.
- `"Figure evidence"`, when present, is labeled separately from text evidence.

## Diagnostics Drawer

Run warnings appear only in Diagnostics, with their count, category, and message alongside the matching, proposal, review, and runtime summaries.

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
