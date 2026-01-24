# Repo audit (current)

## Current entrypoints

- CLI entrypoint: `paper_table_agent/cli.py`
- Commands: `ui`, `run`, `resume`, `stop`, `export`, `bundle`, `init-db`, `init-config`, `snapshot`.
- Streamlit UI entrypoint: `paper_table_agent/ui/app.py`
- LangGraph initialization: `paper_table_agent/graph/workflow.py`

## Current UI screens (Streamlit)

- **Run** tab
  - Inputs: table path + PDF folder path
  - Start run button
  - Run status (current PDF + open run folder link)
- **Review** tab
  - Run picker for completed runs
  - Row/column step-through review UI

## What is persisted (SQLite schema)

Tables defined in `paper_table_agent/store/schema.sql`:

- `pdfs`: pdf_id, path, sha1, n_pages, status, error, parse_source, created_at
- `rows`: row_id, row_index, title, authors, year, status
- `locks`: row_id, column, locked, reason
- `matches`: match_id, pdf_id, row_id, confidence, status, evidence_json, rationale, created_at
- `pdf_metadata`: pdf_id, title, authors, year, confidence, evidence_json, created_at
- `match_candidates`: candidate_id, pdf_id, row_id, score, title, authors, year, rank, source, created_at
- `proposals`: proposal_id, pdf_id, row_id, column, proposed_value, status, confidence, evidence_json, reasoning, flags_json, created_at
- `retrieval_chunks`: pdf_id, chunk_id, text, text_raw, page_start, page_end, source, created_at
- `debug_extraction`: pdf_id, payload_json, created_at
- `reviews`: review_id, proposal_id, decision, final_value, note, reviewed_at
- `events`: event_id, level, event_type, payload_json, created_at

## Run artifacts actually produced

Run directories are created in `runs/<timestamp>__<table>/` with:

- `run_config.json` (captured config + prompt versions + git commit)
- `proposals.sqlite`
- `run_report.json`
- `logs/run.log`
- `checkpoints.sqlite`
- `artifacts/parsed/*` (parsed PDF text + tokens)
- `artifacts/retrieval_indexes/*`
- `artifacts/ocr/*`
- `artifacts/thumbnails/*`
- `exports/updated_table.xlsx`
- `exports/audit_log.csv`
- Debug-only (when `output.debug_reports=true`):
  - `exports/pdf_row_matches.csv`
  - `exports/mapping_report.html`
  - `exports/proposals.jsonl`

## Docs map

- `README.md`: product overview + install + quickstart + config + troubleshooting.
- `specs/spec.md`: product specification (canonical).
- `specs/plan.md`: short plan for remaining work.
- `specs/tasks.md`: task checklist.
- `docs/compounding/*`: lessons learned and debugging notes.

## Dead/unused candidates (with evidence)

- None identified after removing unreferenced helper scripts.

## Redundancy candidates

- None identified beyond the normal README/spec separation (specs are canonical; README is shorter).
