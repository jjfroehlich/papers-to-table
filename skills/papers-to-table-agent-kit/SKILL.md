---
name: papers-to-table-agent-kit
description: Standalone skill for extracting structured information from research publications, scientific PDFs, and technical documents into evidence-backed tables. Use when an agent needs to fill benchmark tables from table_template/schema/PDF folders, create structured literature-review tables, preserve source evidence, inspect proposed values in a local review UI, or export accepted results as CSV/report-ready tables. Prefer this skill over generic scientific-data-extraction for benchmark_datasets, *_filled.csv deliverables, and papers-to-table-agent-kit requests; after writing filled CSVs, the agent must ask the exact browser-review opt-in question.
---

# Papers-To-Table Agent Kit

Use this skill when an agent extracts structured information from research publications, scientific PDFs, or other technical documents into an evidence-backed table.

The default output is lean and extraction-first: one user-visible output folder with final CSV deliverables at the folder root and organized provenance/review artifacts under run subfolders. Human review is optional and should be offered after extraction.

## Default Contract

Do not stop at an unsupported CSV-only answer unless the user explicitly says "CSV only", "skip evidence", or equivalent. A request for `_filled.csv`, `completed_table.csv`, or `Return one completed CSV` still needs evidence-backed extraction records.

Before extracting values, create one output workspace and one run folder:

```text
OUTPUT_DIR/
  <requested_or_dataset>_filled.csv
  runs/
    RUN_ID/
      extraction/
        review_input.json
  scratch_delete_after_success/
    RUN_ID/
  logs/
```

`extraction/review_input.json` stores references to source inputs instead of copied files. Prefer absolute paths for PDFs, source tables, and schemas. Do not copy source PDFs, source tables, or schema files into `RUN_DIR`.

Keep the workspace tidy: final deliverables belong in `OUTPUT_DIR`; provenance and review files belong in `OUTPUT_DIR/runs/RUN_ID`; temporary extracted text, rendered page images, page crops, and helper scripts belong only in `OUTPUT_DIR/scratch_delete_after_success/RUN_ID`. Do not create ad hoc root folders such as `.git`, `.agents`, `tools`, `pdf_text_cache`, `rendered_pages`, or `completed_tables`.

After extraction and build, the canonical output is:

```text
OUTPUT_DIR/
  <requested_or_dataset>_filled.csv
  runs/
    RUN_ID/
      extraction/
        review_input.json
        proposals.jsonl
        evidence.jsonl
        validation_report.json
        extraction_summary.json
```

The filled CSV is agent-extracted and not human-reviewed unless a human review decision/export step has occurred.

## Completion Gate

A final answer is incomplete if it only reports completed CSV paths. Before the final response, run the handoff checker:

```bash
python skills/papers-to-table-agent-kit/scripts/finalize_extraction_handoff.py --output-dir OUTPUT_DIR --run RUN_DIR --json
```

For multiple datasets, pass one `--run` per run directory in the same command. If the checker reports missing artifacts, failed validation, generic-rationale warnings, or reused-evidence warnings, fix those problems before handing off.

The final response must report the output directory, run directory or directories, validation status, filled CSV path or paths, and that the values are agent-extracted and not human-reviewed. It must end with this exact line unless the user has already declined review:

```text
Do you want to review the results in the browser interface?
```

Do not replace that question with a vague offer such as "I can build the review UI later." No review question means the task handoff is not complete.

## Human Review

After producing the filled CSV and `extraction/` artifacts, ask the user:

```text
Do you want to review the results in the browser interface?
```

Only build or start the browser interface if the user says yes. Human review artifacts live in:

```text
OUTPUT_DIR/
  <requested_or_dataset>_reviewed.csv
  runs/
    RUN_ID/
      human_review/
        index.html
        assets/
        review_package.json
        decisions.jsonl
        reviewer_summary.json
        audit_log_*.json
        diagnostics_*.json
```

The reviewed table is written next to the filled CSV by appending `_reviewed.csv` to the filled-table stem. Example: `OUTPUT_DIR/genome_editing_tools_filled.csv` becomes `OUTPUT_DIR/genome_editing_tools_reviewed.csv`. Legacy runs without `output_table_path` still write filled/reviewed CSVs in `RUN_DIR`.

PDF rendering and quote highlighting require serving `human_review/` over localhost. Static `human_review/index.html` remains useful for proposal/evidence text and downloaded decisions, but source PDF rendering is a served-mode feature because inputs are referenced rather than copied.

The generated review UI keeps the shared main-app review interaction: Ctrl/Command-click toggles proposal cells, Shift-click selects a queue range or proposal-containing table rectangle, and primary-button dragging selects a rectangle in table mode. The guarded selection bar applies Accept, Reject, or No data to pending proposals after confirmation. Replacing reviewed decisions requires its explicit checkbox and records `decision_source=human_bulk_selection`. Field-before-Value hierarchy, persistent Details and exception-oriented Diagnostics disclosures after Evidence, centered decisions, and spatial keyboard controls (`A`/left previous, `D`/right next, `W`/up accept, `S`/down reject, Ctrl/Command plus left/right for evidence, and `E` to edit) remain aligned. Shift is reserved for selection. Portable static-download and localhost-writeback behavior remain unchanged.

When the user says yes to browser review, do not stop after building files or showing a server command. Start the localhost review server, verify the review URL responds, and complete the handoff in one of these ways:

- Open the review URL in the user's browser when the environment provides a browser-opening or browser-control tool and any required approval has been granted.
- Always include the exact clickable URL in the chat, even if the browser was opened, so the user can reload or reopen it.

Report the exact URL printed by `launch_review_servers.py`; it should end in `/human_review/index.html`. Do not shorten it to `/review`, because relative JS/CSS assets are resolved from the browser URL.

## Authoring Contract

### Dataset preflight and paper-to-row matching

Before scaffolding or extracting any cells:

1. Resolve the authoritative baseline before treating any cell as blank. Recursively inventory compatible CSV/XLSX tables in the dataset, including files in `archive`, `complete`, `original`, or similarly named folders. Compare schema target columns and overlapping row identities; filenames and the name `table_template.csv` do not establish authority. Never use protected benchmark gold such as `table_gold.csv` as an extraction baseline.
2. If a companion contains populated target values that the selected template lacks or contradicts, stop before creating the run. Ask which table is authoritative, or use the user's already explicit choice with `--authoritative-table PATH` and `--authoritative-sheet SHEET` when needed. Use `--allow-template-only` only after the user independently confirms that companion values should be disregarded. Do not infer that blanks are intentional.
3. Inspect the effective baseline headers, schema, row identifiers, populated target cells, and PDF inventory. Report the counts of blank and populated target cells and choose the extraction mode deliberately.
4. Match every input PDF to its table row from publication identity: use DOI when available, then normalized title, authors, and year from the PDF front matter. Account for preprint/published-title variants and filename abbreviations. A filename similarity or shared row/PDF order is not sufficient evidence of identity.
5. Write the canonical PDF stem into an explicit `pdf_id` column for each matched row before running the scaffold. Every input PDF must map to exactly one row. A larger source table may contain table-only rows with blank `pdf_id`; those rows remain preserved but are not extraction targets for the supplied PDF set.
6. Stop and surface unresolved or competing matches instead of assigning them. Use `--allow-positional-pdf-fallback` only as an explicit escape hatch when there are no explicit mappings, row and PDF counts are equal, and the one-to-one order was independently verified.

The scaffold enforces this contract and fails before creating a run when baseline authority is unresolved or a PDF is unused, unknown, or assigned more than once. It writes `extraction/baseline_manifest.json` with source paths, hashes, candidate assessments, preserved-cell counts, and any explicit template-only override. Its JSON result reports baseline status, mapping mode, mapped and table-only rows, extraction mode, and blank/populated/eligible target-cell counts for the PDF-mapped extraction scope, plus source-table and table-only target-cell totals. Schema CSVs may encode categorical `allowed_values` as either a JSON array or a pipe-delimited string; the scaffold normalizes both to arrays.

`extraction/review_input.json` must use:

```json
{
  "schema_version": "papers_to_table.review_input.v1",
  "extraction_mode": "fill_blanks",
  "run_id": "agent_review_001",
  "output_table_name": "agent_review_001_filled.csv",
  "output_table_path": "C:/path/to/output/agent_review_001_filled.csv",
  "source_table_path": "C:/path/to/source_table.csv",
  "baseline_manifest_path": "C:/path/to/run/extraction/baseline_manifest.json",
  "schema_path": "C:/path/to/schema.csv",
  "pdfs": [
    {"pdf_id": "paper_a", "path": "C:/path/to/paper_a.pdf", "label": "Paper A"}
  ],
  "columns": [
    {"column_name": "Finding", "description": "Main reported finding", "field_type": "text"}
  ],
  "rows": [
    {"row_id": "row_1", "pdf_id": "paper_a", "values": {"Title": "Paper A"}}
  ],
  "proposals": [
    {
      "row_id": "row_1",
      "column_name": "Finding",
      "proposed_value": "Example value",
      "rationale": "The Results sentence names Example value as the finding for this row, so it directly supports the Finding cell.",
      "evidence": [
        {
          "pdf_id": "paper_a",
          "source_type": "direct_quote",
          "page_number": 3,
          "quote_text": "The main finding was Example value."
        }
      ]
    }
  ]
}
```

Every non-empty `proposed_value` must include structured evidence at authoring time. Every value-bearing proposal should include a concise proposal-level `rationale`. The rationale is an evidence-grounded reasoning summary for audit and review: state the source fact, the extraction or inference, and any schema normalization or why the value/no-data conclusion is warranted. Do not write private step-by-step chain-of-thought.

`extraction_mode` is additive and optional. It defaults to `fill_blanks`, which rejects proposals for populated source cells. Use `fill_and_verify` only when the user explicitly requests auditing existing values. Verification proposals retain `existing_value`, appear in review with `is_verify_mode=true`, and do not alter the unreviewed filled CSV; only an accepted decision changes the reviewed CSV.

Treat partially populated tables as data, not instructions to imitate. In `fill_blanks`, preserve populated cells byte-for-byte, include them in `rows[].values` so the table view displays them, and extract only eligible blank target cells. Existing values are not source evidence and must not be copied into blank cells as semantic exemplars. In explicitly requested `fill_and_verify`, evaluate populated cells independently against the matched paper and schema; propose a replacement only with its own evidence and rationale. Do not reinterpret metadata columns such as title, DOI, authors, focus/category, notes, or manually curated identifiers as extraction targets unless the schema explicitly defines them as target fields. Describe a mixed output as preserved pre-existing human-reviewed values plus unreviewed agent proposals; do not label the entire filled table as agent-extracted.

Evidence should be column-specific and minimal for that cell. Do not copy the same evidence array across many columns in a row unless the same quoted or table passage directly supports every one of those values. A broad abstract, title, method summary, or tool-description quote is not enough support for unrelated performance, organism, parameter, or result columns.

Avoid boilerplate rationales such as `Extracted from the provided PDF evidence for <column>` or `The quoted sentence directly supports the proposed value.` Write what the evidence proves and, when relevant, how you normalized it to the schema.

## Evidence And Rationale Authoring Loop

Use a cell-by-cell loop. For each target cell, record provenance as you extract the value:

1. Confirm the row's source PDF before reading evidence. Evidence from one paper must not support another row.
2. Confirm present-study ownership. Do not classify the current assay from background, previous-study, comparison-only, or future-option passages.
3. Locate the narrowest source support for that column: a sentence, table row/cell, caption phrase, figure label plus caption, or page-local context.
4. Write only the evidence needed for that cell in the proposal's `evidence` array. Do not attach a paper-level evidence bundle to unrelated columns.
5. Write a concise `rationale` that names the source fact, proposed value, column, and extraction decision. If you mapped to an allowed schema value, say what source wording was normalized.
6. For no-data proposals, cite the source that establishes absence or scope, and make the rationale explain why the cell should stay blank or be marked no-data.

Use one explicit authoring path in `reason_codes`:

- `direct`: the value is stated directly.
- `calculation`: record the reviewer-readable formula in `calculation`; every operand must have evidence from compatible assay stages, populations, units, and QC states.
- `figure_estimate`: cite the rendered panel with `figure_ref`, page, caption and/or panel region, use `numeric_value_form="approximate"`, and keep the value approximate.
- `protocol_inference`: explain the protocol logic and route the proposal to reviewer attention.
- `absence_inference`: use only after a documented, field-specific audit of the relevant methods, protocol, supplement, primer/oligo tables, and figures. Record the audited scope in rationale/evidence. For schemas that request it, author `no (inferred)`; normalized proposals carry an `absence_inference` diagnostic and require review attention.

For numeric values, use `numeric_value_form` as `exact`, `range`, or `approximate`. A `number` field must receive a finite JSON number, not a formatted string. A categorical field must exactly match one of its `allowed_values`.

Before finalizing a paper, perform cross-field consistency checks across design category, delivery/integration, readout, reporter-barcode role, UMI role, scale, and construct count. Resolve contradictions with source evidence; do not let a method brand, background assay, lookup-sequencing depth, or reporter barcode silently determine a different field.

Before building, run authoring validation:

```bash
python skills/papers-to-table-agent-kit/scripts/validate_review_package.py --run RUN_DIR --mode authoring --json
```

Treat warnings about generic rationales or reused evidence sets as extraction defects, not harmless noise. Revise `extraction/review_input.json` and rerun validation until those warnings are gone, unless a shared table row/caption genuinely supports each flagged column; in that case, make each rationale value-specific so the reviewer can see why the reuse is justified.

Optional identity fields:

- `proposal_id`
- `evidence_id`
- `cell_id`
- `calculation`
- `created_at`

If IDs are absent, `build_review_package.py` generates stable deterministic IDs.

## Evidence Requirements

Strong evidence requires `pdf_id`, `page_number`, and at least one of `quote_text`, `table_text`, `evidence_text`, `caption_text`, exact/approximate highlight regions, or figure reference plus caption text.

Evidence tiers:

- Tier A: `pdf_id` plus `page_number` plus quote/table/caption/evidence text -> `direct_strong`
- Tier B: `pdf_id` plus `page_number` plus exact/approximate bbox regions -> `direct_strong` or `direct_weak`
- Tier C: `pdf_id` plus `page_number` plus `source_location` and/or `reasoning` -> `inferred_weak`
- Tier D: no structured evidence -> invalid for non-empty proposed values

Keep `rationale` separate from evidence text: evidence fields preserve source-grounded support, while `rationale` summarizes the extraction judgment. If two columns share one table row or figure caption, cite the shared passage only when each proposed value can be read from that passage, and make each rationale name the value-specific part.

## Script Workflow

For benchmark folders:

```bash
python skills/papers-to-table-agent-kit/scripts/prepare_output_workspace.py --output-dir OUTPUT_DIR --run-id RUN_ID --json
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --output-root OUTPUT_DIR --extraction-mode fill_blanks --json
```

Build the lean extraction outputs:

```bash
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR --json
python skills/papers-to-table-agent-kit/scripts/cleanup_scratch.py --output-dir OUTPUT_DIR --json
python skills/papers-to-table-agent-kit/scripts/finalize_extraction_handoff.py --output-dir OUTPUT_DIR --run RUN_DIR --json
```

After build, inspect `RUN_DIR/extraction/validation_report.json`. If it still reports generic-rationale or reused-evidence warnings, fix the authored proposals and rebuild before handing results to the user. Run scratch cleanup only after successful build/validation and only for `OUTPUT_DIR/scratch_delete_after_success`.

If the user wants browser review, build and serve the optional review UI:

```bash
python skills/papers-to-table-agent-kit/scripts/launch_review_servers.py --run RUN_DIR --build --start-port 8761 --quiet --json
```

For multiple independent run directories, pass `--run` once per directory in one launcher call:

```bash
python skills/papers-to-table-agent-kit/scripts/launch_review_servers.py --run RUN_1 --run RUN_2 --run RUN_3 --build --start-port 8761 --quiet --json
```

`launch_review_servers.py` starts detached localhost servers, probes each `/human_review/index.html`, prints the verified `review_url` values, and exits. Prefer it over handwritten shell loops. Do not run `serve_review.py` in the foreground when the next user-visible step is giving review links, and do not improvise long-running PowerShell `Start-Process` loops; those can leave the agent turn waiting without returning URLs.

Apply downloaded or server-written decisions:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --decisions RUN_DIR/human_review/downloaded_decisions.json
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --use-existing-decisions
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --accept-all
```

`apply_review_decisions.py` writes the root `<stem>_reviewed.csv` and `human_review/` audit files.

## Final Handoff

Before reporting completion, verify:

- `OUTPUT_DIR/<requested_or_dataset>_filled.csv`
- `RUN_DIR/extraction/review_input.json`
- `RUN_DIR/extraction/proposals.jsonl`
- `RUN_DIR/extraction/evidence.jsonl`
- `RUN_DIR/extraction/validation_report.json`
- `RUN_DIR/extraction/extraction_summary.json`

Report the output directory, run directory, validation status, the filled CSV path, and whether the values are unreviewed agent-extracted values. Then ask whether the user wants browser review.

Run `finalize_extraction_handoff.py` before sending the final answer. For multi-dataset work, pass all run directories in one command. Do not send a final answer while the handoff checker reports errors.

End the final answer with the exact question `Do you want to review the results in the browser interface?` unless the user has already declined review. If review is requested, the final response must include either "opened in browser" plus the exact URL, or a direct clickable `http://127.0.0.1:PORT/human_review/index.html` link for the user to open. After export, report the root `<stem>_reviewed.csv`.

## References

- `references/extraction_workflow.md`: agent extraction and optional review workflow.
- `references/review_export_normalization.md`: generated artifact and decision semantics.
- `templates/extraction_to_review_prompt.md`: reusable external-agent prompt for evidence-first extraction.
