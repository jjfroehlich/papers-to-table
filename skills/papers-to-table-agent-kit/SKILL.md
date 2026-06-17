---
name: papers-to-table-agent-kit
description: Standalone skill for extracting structured information from research publications, scientific PDFs, and technical documents into evidence-backed tables. Use when an agent needs to fill benchmark tables, create structured literature-review tables, preserve source evidence, inspect proposed values in a local review UI, or export accepted results as CSV/report-ready tables.
---

# Papers-To-Table Agent Kit

Use this skill when an agent extracts structured information from research publications, scientific PDFs, or other technical documents and needs a reviewable table with source evidence.

The skill is self-contained: it gives lightweight extraction guidance, defines the review-package input format, validates evidence-backed proposals, builds a local browser review interface, and exports accepted results. The agent still decides how to read documents and infer proposed values using the tools available in the current environment.

## Hard Gate: Evidence And Review UI

Fail closed on the review workflow. CSV filenames, `_filled.csv`, `completed_table.csv`, or instructions such as `Return one completed CSV` do not mean CSV-only. A request for CSV outputs is not a CSV-only request. Treat CSV outputs as draft convenience artifacts unless the user explicitly says "CSV only", "skip review", "do not build the review UI", or equivalent.

Before extracting any value, scaffold a run directory and create `review_input.json`. Every non-empty proposal must be written with structured evidence at authoring time, not reconstructed after filling a CSV. The task is incomplete until `build_and_serve_review.py` has produced the required review artifacts and the agent has made the review UI usable: open a live localhost review page in the agent app/browser when browser control is available, or provide clickable localhost links that have been verified to return HTTP 200. Do not stop at an exact `serve_review.py` command unless active serving is genuinely blocked; if blocked, state the blocker and provide the exact command as a fallback.

Common failure trap: benchmark folders with PDFs plus a schema/template and requested files like `genome_editing_tools_filled.csv` still require a review package. Produce optional draft `_filled.csv` files only alongside `review_input.json`, validation outputs, and the review UI handoff.

Default workflow: build a formal review package. Do not stop at `_filled.csv` or `completed_table.csv` outputs unless the user explicitly requests CSV-only extraction. A request for CSV outputs is not a CSV-only request. Treat the task as CSV-only only when the user says "CSV only", "skip review", "do not build the review UI", or equivalent. Draft filled CSVs are optional secondary artifacts; the reviewable deliverable is `review_input.json` plus PDFs, validation, generated review files, and a live localhost review URL opened in an available browser surface or returned as a clickable, verified link.

Before extracting values for any table-completion task:

1. Create a `RUN_DIR` for the review handoff.
2. Copy source PDFs into `RUN_DIR/pdfs/`.
3. Copy the empty table/template to `RUN_DIR/source_table.csv` when present.
4. Copy the task schema to `RUN_DIR/schema.json` or `RUN_DIR/schema.csv` when present.
5. Create a `review_input.json` skeleton with `pdfs`, `columns`, `rows`, and an initially empty `proposals` array.
6. Append one proposal with structured evidence as each non-empty target cell is authored.
7. Optionally maintain a draft CSV in parallel, but keep the review package as the controlling artifact.

External agents author only:

```text
RUN_DIR/
  review_input.json
  pdfs/
  source_table.csv  # optional
  schema.json       # optional
  schema.csv        # optional
```

The kit scripts derive all normalized artifacts, review-package JSON, indexes, summaries, decisions, and exports. Agents should not hand-author `normalized/`, `summaries/`, `exports/`, compatibility outputs, or generated review files.

When extracting from PDFs, capture structured evidence while authoring each proposed value. Every non-empty `proposed_value` in `review_input.json` must include Tier A, B, or C evidence at extraction time. Do not defer evidence capture to a later cleanup pass.

## Product Scope

The kit provides:

- light schema-first and row-aware extraction guidance
- proposal queue/table review
- PDF.js page and quote evidence inspection
- bundled PDF.js runtime assets so copying `skills/papers-to-table-agent-kit/` keeps quote highlighting working
- visible weak-evidence labels
- accept, accept-with-edit, reject, and confirmed-no-data decisions
- decision download or localhost writeback
- accepted-only `exports/final_table.csv`
- report-ready reviewed values that can be summarized in research reports when the task benefits from prose or table synthesis
- optional future XLSX export

The kit is not a full extraction service. It does not provide a model provider, OCR engine, citation manager, batch scheduler, benchmark evaluator, or document-ingestion backend. It keeps the handoff portable: author `review_input.json` with evidence, then let the bundled scripts validate, build, review, and export.

## Authoring Contract

`review_input.json` must use:

```json
{
  "schema_version": "papers_to_table.review_input.v1",
  "run_id": "agent_review_001",
  "pdfs": [
    {"pdf_id": "paper_a", "path": "pdfs/paper_a.pdf", "label": "Paper A"}
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
      "evidence": [
        {
          "pdf_id": "paper_a",
          "source_type": "direct_quote",
          "page_number": 3,
          "quote_text": "Exact supporting sentence from the PDF."
        }
      ]
    }
  ]
}
```

`templates/review_input.schema.json` is the local schema and `templates/review_input.example.json` is the compact example.

Optional fields in `review_input.json`:

- `proposal_id`
- `evidence_id`
- `cell_id`
- `created_at`

If IDs are absent, `build_review_package.py` generates stable deterministic IDs. If IDs are present, validation checks uniqueness and references.

## Evidence Requirements

Every non-empty `proposed_value` must have at least one structured evidence record. Prefer `pdf_id`, `page_number`, and text evidence.

Evidence source-type inference:

- If `source_type` is absent and `quote_text`, `table_text`, `evidence_text`, or `caption_text` is present, direct evidence is inferred.
- If `source_type` is absent and only `page_number` plus `reasoning` and/or `source_location` is present, `inferred_reasoning` is inferred.
- Generated evidence normalizes `source_type` to a stable review/export vocabulary and preserves the authored evidence kind separately in `authored_evidence_kind` when the input used kit-specific text kinds.

Evidence tiers:

- Tier A: `pdf_id` plus `page_number` plus quote/table/caption/evidence text -> `direct_strong`
- Tier B: `pdf_id` plus `page_number` plus exact/approximate bbox regions -> `direct_strong` or `direct_weak`
- Tier C: `pdf_id` plus `page_number` plus `source_location` and/or `reasoning` -> `inferred_weak`, visible attention label
- Tier D: no structured evidence -> invalid for non-empty `proposed_value`

Strong evidence requires `pdf_id`, `page_number`, and at least one of `quote_text`, `table_text`, `evidence_text`, exact/approximate bbox regions, or `figure_ref` plus `caption_text`.

Highlight regions and bboxes must use finite numeric coordinates, a positive page reference, and nonzero area. Validation also checks normalized coordinates and warns about ambiguous coordinate conventions.

## Script Workflow

For benchmark folders with a table template and schema, scaffold the handoff before extraction:

```bash
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --run RUN_DIR
```

Default one-step build and serve:

```bash
python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR
```

This is useful for manual use, but it starts a long-running foreground server. For agent handoff, prefer the build-only plus detached-serving pattern below so the agent can finish with verified links instead of waiting on the server process.

For non-interactive validation or tests, build without starting the long-running server:

```bash
python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR --build-only --json
```

The wrapper validates author-authored inputs, builds the rich review bundle, validates generated artifacts, starts the localhost review UI by default, and prints `review_url`.

## Serving And Opening The Review UI

Make the review UI directly usable before reporting completion. The preferred handoff is an active localhost URL, not a command the user must run.

Use this pattern when the current environment supports a browser or browser-like app surface:

1. Build and validate first:
   ```bash
   python skills/papers-to-table-agent-kit/scripts/build_and_serve_review.py --run RUN_DIR --build-only --json
   ```
2. Start `serve_review.py` as a background process on localhost. When starting from an agent shell, pass `--no-open --quiet`; the script's default browser-opening behavior can hang or disappear in desktop, sandboxed, or headless contexts.
3. Verify the URL returns HTTP 200 before giving it to the user.
4. Open the URL directly in the agent app/browser when browser control is available. In Codex Desktop or similar agent apps, use the available browser-control tool to show the page to the user. If direct browser control is unavailable, return the verified localhost URL as a clickable Markdown link.

On Windows, prefer `pythonw.exe` next to the Python interpreter when available so the server starts detached without tying up the agent command:

```powershell
$runDir = "RUN_DIR"
$pyw = "pythonw.exe"
$script = "skills\papers-to-table-agent-kit\scripts\serve_review.py"
$port = 8761
Start-Process -FilePath $pyw -ArgumentList @($script, "--run", $runDir, "--host", "127.0.0.1", "--port", "$port", "--no-open", "--quiet") -WindowStyle Hidden -PassThru
Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/" -TimeoutSec 3
```

On macOS/Linux:

```bash
nohup python skills/papers-to-table-agent-kit/scripts/serve_review.py \
  --run "$RUN_DIR" --host 127.0.0.1 --port "$PORT" --no-open --quiet \
  > "$RUN_DIR/review_server.log" 2>&1 &
curl -fsS "http://127.0.0.1:$PORT/" >/dev/null
```

For multiple benchmark datasets or multiple run directories, serve each review package independently on a distinct free localhost port and report all verified links with dataset labels. Open at least the first review in the in-app browser when available; open all of them if the browser surface supports multiple usable tabs.

If active serving fails because of sandbox restrictions, missing browser capabilities, port binding failures, or unavailable long-running processes, do not silently downgrade to commands-only. Report the blocker, include any generated `review/index.html` path as a static fallback if it can be opened safely, and include the exact `serve_review.py` command the user can run manually.

Equivalent explicit steps:

```bash
python skills/papers-to-table-agent-kit/scripts/validate_review_package.py --run RUN_DIR --mode authoring
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR
python skills/papers-to-table-agent-kit/scripts/serve_review.py --run RUN_DIR --host 127.0.0.1 --port PORT --no-open --quiet
```

For download-only review, open `RUN_DIR/review/index.html` directly when browser security allows it. Localhost serving is the default path because it permits decision writeback and export.

Apply downloaded or server-written decisions:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --decisions RUN_DIR/review/downloaded_decisions.json
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --use-existing-decisions
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --accept-all
```

## Generated Artifacts

MVP build artifacts:

```text
review/
  index.html
  assets/*
  review_package.json
normalized/
  proposals.jsonl
  evidence.jsonl
summaries/
  validation_report.json
```

Generated only after review/export:

```text
review/decisions.jsonl
exports/final_table.csv
exports/audit_log_*.json
summaries/reviewer_summary.json
```

Optional future artifacts:

```text
exports/final_table.xlsx
normalized/proposal_index.json
normalized/review_lookup.json
assets/pages/
assets/figures/
```

Compatibility artifacts are optional generated outputs, never required agent-authored inputs.

## Report Handoff

You may use extracted values internally for a literature review or research report. If the task calls for it, render accepted values as a concise summarizing table in addition to writing CSV outputs. If values were not human-reviewed, do not imply that they were. Label information as human-reviewed, auto-accepted, agent-extracted, or draft/unreviewed where relevant.

Final artifact gate: before reporting completion, verify that all required review artifacts exist:

- `RUN_DIR/review_input.json`
- `RUN_DIR/normalized/proposals.jsonl`
- `RUN_DIR/normalized/evidence.jsonl`
- `RUN_DIR/summaries/validation_report.json`
- `RUN_DIR/review/index.html`
- a live `review_url` that was opened in an available browser surface or returned as a clickable verified link

If any required review artifact is missing, or if no live review URL is available, and the user did not explicitly request CSV-only extraction, do not call the task complete. Create the missing artifact, start and verify the review server, or report the specific blocker and provide the manual command only as a fallback.

For benchmark tasks, it is acceptable to produce both a draft CSV and a review package:

- `draft_completed_table.csv` or another clearly named draft CSV: agent-extracted, not human-reviewed
- `review_input.json` plus the generated review UI: evidence-backed review package
- `exports/final_table.csv`: accepted-only output after human review or after an explicit `--accept-all` decision

Final agent response after extraction should include:

- `RUN_DIR`
- validation status
- verified clickable `review_url` links for each served review UI
- whether the UI was opened directly in the agent app/browser
- the exact wrapper or `serve_review.py` command only if the UI could not be kept running, with the blocker stated
- paths to any optional draft `_filled.csv` outputs

## References

- `references/extraction_workflow.md`: agent extraction and review-input workflow.
- `references/review_export_normalization.md`: generated review/export artifact and decision semantics.
- `templates/extraction_to_review_prompt.md`: reusable external-agent prompt for evidence-first extraction to review.
