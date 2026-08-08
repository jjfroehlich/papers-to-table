# Papers-To-Table Agent Kit

`skills/papers-to-table-agent-kit/` is a standalone workflow for agents that extract structured information from scientific PDFs and technical documents. It produces an evidence-backed filled CSV and can add a local browser review interface when requested.

The kit does not run the main app, LM Studio, or its extraction pipeline. The agent performs extraction. The kit validates provenance, normalizes artifacts, and handles review and export. Evidence shows where a value came from; it does not prove that a publication's claim is scientifically correct.

![Comparison of the local-app and agent-kit skills](../diagrams/refined_svg/04_agent_skills_refined.svg)

## Default Workflow

1. Create one output workspace and one run directory.
2. Author `RUN_DIR/extraction/review_input.json` with rows, fields, proposals, rationales, and evidence.
3. Validate and build the extraction artifacts.
4. Run the handoff checker and fix all reported errors or provenance warnings.
5. Deliver the root `_filled.csv` as agent-extracted and not human-reviewed.
6. Ask whether the user wants browser review.
7. Build and serve `human_review/` only if the user opts in.

The required review question is:

```text
Do you want to review the results in the browser interface?
```

## Workspace Layout

Agents reference source inputs by path. They do not copy PDFs, source tables, or schemas into the run directory.

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
  scratch_delete_after_success/
    RUN_ID/
  logs/
```

Keep temporary text, page images, crops, and helper files under `scratch_delete_after_success/RUN_ID`. Clean that directory only after a successful build and validation.

## Authoring Contract

`extraction/review_input.json` uses schema version `papers_to_table.review_input.v1`.

```json
{
  "schema_version": "papers_to_table.review_input.v1",
  "run_id": "agent_review_001",
  "output_table_name": "results_filled.csv",
  "output_table_path": "C:/path/to/output/results_filled.csv",
  "source_table_path": "C:/path/to/source_table.csv",
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
      "rationale": "The Results sentence reports Example value as the main finding.",
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

`proposal_id`, `evidence_id`, `cell_id`, `calculation`, and `created_at` are optional. The builder generates stable IDs when needed and validates supplied identities.

## Evidence And Rationales

Every non-empty proposed value needs structured evidence and a concise rationale.

- Use the narrowest passage, table cell, caption, figure reference, or page context that supports the specific field.
- Keep evidence tied to the correct PDF, row, and column.
- Reuse evidence only when the same source passage directly supports each affected value.
- Explain the source fact, extracted value, and any schema normalization in the rationale.
- Do not use generic rationale templates or private step-by-step reasoning.

Evidence strength:

| Tier | Required support | Review label |
| --- | --- | --- |
| A | PDF, page, and quote/table/caption/evidence text | `direct_strong` |
| B | PDF, page, and exact or approximate highlight region | `direct_strong` or `direct_weak` |
| C | PDF, page, and source location or reasoning | `inferred_weak` |
| D | No structured evidence | Invalid for non-empty values |

Highlight coordinates must be finite, have nonzero area, and reference a positive page. Normalized coordinates must remain within `[0, 1]`.

Generated evidence uses `evidence_schema_version="main_evidence"` and normalized source types. Kit-specific authored kinds remain available in `authored_evidence_kind`.

## Build The Extraction Output

For a benchmark or table-completion task, prepare and scaffold the workspace:

```bash
python skills/papers-to-table-agent-kit/scripts/prepare_output_workspace.py --output-dir OUTPUT_DIR --run-id RUN_ID --json
python skills/papers-to-table-agent-kit/scripts/scaffold_benchmark_run.py --dataset-dir DATASET_DIR --output-root OUTPUT_DIR --json
```

After adding evidence-backed proposals, validate and build:

```bash
python skills/papers-to-table-agent-kit/scripts/validate_review_package.py --run RUN_DIR --mode authoring --json
python skills/papers-to-table-agent-kit/scripts/build_review_package.py --run RUN_DIR --json
python skills/papers-to-table-agent-kit/scripts/cleanup_scratch.py --output-dir OUTPUT_DIR --json
python skills/papers-to-table-agent-kit/scripts/finalize_extraction_handoff.py --output-dir OUTPUT_DIR --run RUN_DIR --json
```

Treat generic-rationale and reused-evidence warnings as extraction defects. Fix them before handoff unless shared evidence genuinely supports each value and each rationale explains that support.

For multiple datasets, pass one `--run RUN_DIR` argument per run to `finalize_extraction_handoff.py`.

## Optional Browser Review

Build and launch review only after the user opts in:

```bash
python skills/papers-to-table-agent-kit/scripts/launch_review_servers.py --run RUN_DIR --build --start-port 8761 --quiet --json
```

For several runs, repeat `--run`. The launcher starts detached localhost servers, verifies each URL, and prints links ending in `/human_review/index.html`.

Always give the user the exact URL. Localhost mode supports source-PDF rendering, quote highlighting, decision writeback, and accepted-only export. Static `human_review/index.html` can show proposal and evidence text but cannot reliably load referenced PDFs.

Review artifacts live under:

```text
RUN_DIR/
  human_review/
    index.html
    assets/
    review_package.json
    decisions.jsonl
    reviewer_summary.json
    audit_log_*.json
    diagnostics_*.json
```

## Apply Review Decisions

Apply downloaded decisions, server-written decisions, or an explicit trusted auto-accept:

```bash
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --decisions RUN_DIR/human_review/downloaded_decisions.json
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --use-existing-decisions
python skills/papers-to-table-agent-kit/scripts/apply_review_decisions.py --run RUN_DIR --accept-all
```

The reviewed CSV is written beside the filled CSV with `_reviewed.csv` replacing `_filled.csv`. Only accepted and accepted-with-edit values populate it. Rejected, confirmed-no-data, pending, and undecided proposals remain in the audit artifacts.

Auto-accepted decisions use `decision_source="automation_accept_all"`.

## Benchmark Result

In one benchmark, Codex with GPT-5.5 xhigh produced similar score distributions with its default workflow and with the Agent Kit. This result is specific to that benchmark and configuration.

![Codex benchmark score distributions with its default workflow and with the papers-to-table agent-kit skill](../plots/20260615_004637_compare_models_plots_v2/20260615_004637_compare_models_plots_v2_agent_kit.jpg)

*Content-correctness [Eval scores](eval.md) from three replicates across 15 papers and 31 target columns in optimizer run `20260615_004637_compare_models`. Labels above the boxes show mean scores to one decimal percentage point.*

## Installation

Tell the agent to install the skill from:

```text
https://github.com/jjfroehlich/papers-to-table/tree/main/skills/papers-to-table-agent-kit/
```

Alternatively, copy the complete `skills/papers-to-table-agent-kit/` directory into the agent system's skill directory. Keep its `assets/`, `references/`, `scripts/`, and `templates/` directories together.

Use `templates/extraction_to_review_prompt.md` when an external agent should perform extraction and produce the evidence-backed handoff in one pass.
