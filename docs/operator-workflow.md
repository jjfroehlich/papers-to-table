# Operator workflow and trust notes

This guide stays intentionally close to the implemented MVP. It documents the current browser workflow, what the screenshots show, and where the app is intentionally strict about trust.

## Screenshot-backed workflow

### 1. Run setup

![Run setup screenshot](screenshots/run-setup.png)

- Start from the **Run** tab.
- Enter the backend-readable config path in the text field.
- Use **Browse...** only as a filename prefill helper; confirm the real path before launch.
- Expand **optional path overrides** only when you need a one-run override for the table, schema, or PDF directory.

### 2. Highlighted-evidence review workspace

![Review workspace screenshot](screenshots/review-workspace.png)

- The queue defaults to actionable pending proposals and supports grouped triage by paper or column.
- The detail pane keeps the proposed value, schema description, and ordered evidence list together.
- The evidence viewer uses:
  - blue overlays for exact quote highlights
  - dashed orange overlays for approximate regions
  - a text fallback panel when only quote-plus-page evidence is available

### 3. Export and diagnostics artifacts

![Export and diagnostics screenshot](screenshots/export-diagnostics.png)

- Export stays manual: the reviewer must click **Export reviewed workbook**.
- Download links appear only after that explicit export.
- Diagnostics are written alongside the workbook and audit log in `{output_dir}/{run_id}/exports/`.

## Writing better schema descriptions

Treat the schema as the normal extraction contract, even when the table is mostly empty.

- Name the paper-facing fact, not the workflow step.
- Say what counts as evidence for the field.
- Add the unit, scope, or disambiguator when a short column name could mean multiple things.
- Prefer one extractable concept per column.
- For categorical fields, constrain the allowed values instead of relying on reviewer memory.

Concrete CSV example:

```csv
column_name,description,field_type,allowed_values
Species,Species used in the assay or model system.,categorical,"[""human"",""mouse"",""yeast""]"
Model system,Cell line or organism context used for the reported experiment.,text,
Number of Conditions,How many distinct experimental conditions were tested in the paper.,number,
Readout,Primary assay readout used to measure expression or activity.,categorical,"[""RNAseq"",""scRNAseq"",""FACS""]"
```

Notes:

- `field_type` is optional. Supported values are `text`, `number`, `categorical`, and `boolean`.
- `allowed_values` are only valid for `categorical` fields.
- Empty target columns are normal. Extraction does not require prefilled example values.

For numeric fields, reviewers may see answers that preserve the paper’s level of precision:

- `5` → exact
- `5-7` → range
- `~5` → approximate
- graph-estimated values should remain approximate rather than being rewritten as exact

## Evidence semantics

- **Direct quote**: exact highlight anchored to page text.
- **Approximate highlight**: region-level fallback when exact quote alignment fails.
- **Quote + page**: text fallback with page reference when highlight geometry is unavailable.
- **Inferred reasoning** / **Calculation**: reviewer-visible support types that stay distinct from direct quotes.
- Figure evidence, when present, is labeled separately from text evidence.

## Provider, parsing, and fallback truth

- The canonical live provider token is `lm_studio`.
- The UI surfaces provider mode directly (`live local`, `live cloud`, `unavailable`, `disabled`, or `stub/demo` when applicable).
- If the configured live provider is unavailable at startup, the run fails during readiness instead of pretending to complete.
- Parsing fallback, OCR fallback, duplicate conflicts, and evidence fallback stay visible through warnings and review summaries.
- The app does not silently relabel fallback evidence as exact evidence.

## Manual export flow

1. Review proposals in the browser.
2. Accept only the values you want written back.
3. Click **Export reviewed workbook**.
4. Download the workbook and JSON artifacts, or open them directly from `{output_dir}/{run_id}/exports/`.

Only explicitly accepted values are exported. Rejected, unreviewed, and confirmed-no-data outcomes are excluded.

## Lightweight trustworthiness checklist

- [ ] Confirm the provider mode shown in the UI matches your intended local/cloud path.
- [ ] Review fallback labels instead of treating every proposal as equally grounded.
- [ ] Inspect evidence before export; proposal presence is not proof.
- [ ] Use the explicit export step rather than assuming run completion wrote a workbook.
- [ ] Keep the audit log and diagnostics JSON with the exported workbook.

## Refreshing the screenshots

From the repo root:

```bash
pip install -e ./backend[test]
python -m playwright install chromium
cd frontend && npm install && cd ..
python -m pytest tests/e2e/test_doc_screenshots.py -m e2e --capture-doc-screenshots
```

The screenshot test spins up a deterministic local backend/frontend stack, captures the three README images, and writes them into `docs/screenshots/`.
