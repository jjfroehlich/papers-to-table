# Project Snapshot

        ## 1. What the app is
        Paper Table Agent is a local-first PDF → table proposal pipeline that reads a spreadsheet of papers and a
        folder of PDFs, matches each PDF to a row, and proposes values for missing cells with evidence. It keeps
        an audit trail of matches, retrieval hits, extraction proposals, and evidence highlights while avoiding
        overwriting existing data.

        The system is designed for batch processing with resumable runs, and stores its state in a local SQLite
        DB plus file-based artifacts under a run directory. The workflow is optimized for offline/LM-studio style
        inference but can also point at OpenAI-compatible backends.

        After a run completes, the Streamlit review UI lets you review only matched rows, approve or reject each
        proposal, and export a final spreadsheet plus audit logs. Evidence quotes and highlight metadata are
        surfaced alongside each proposed value.

        ## 2. Current repo entrypoints
        - CLI entrypoint: `paper_table_agent/cli.py` (commands: `ui`, `run`, `resume`, `stop`, `export`, `bundle`,
          `init-db`, `init-config`, `snapshot`).
        - Streamlit app entry: `paper_table_agent/ui/app.py` (`paper-table-agent ui`).
        - LangGraph initialization: `paper_table_agent/graph/workflow.py` (StateGraph + SqliteSaver checkpoints).

        ## 3. End-to-end data flow diagram
        ```text
        table load
          → schema parse
          → pdf parse
          → header/meta extract
          → matching
          → chunking/index
          → retrieval
          → extraction
          → evidence validation
          → persistence
          → review decisions
          → export
        ```

        ## 4. Key modules map (with paths)
        - `paper_table_agent/graph/matching.py`: Header extraction + match adjudication between PDFs and table rows.
- `paper_table_agent/pdf/parser.py`: PDF parsing with text extraction and metadata handling.
- `paper_table_agent/pdf/ocr.py`: OCR fallback for low-text PDFs.
- `paper_table_agent/retrieval/pipeline.py`: Query expansion/HyDE and retrieval pipeline for evidence chunks.
- `paper_table_agent/graph/extraction.py`: Group extraction, proposal verification, and evidence validation.
- `paper_table_agent/store/db.py`: SQLite persistence for PDFs, matches, proposals, reviews, and events.
- `paper_table_agent/ui/app.py`: Streamlit run + review UI.
- `paper_table_agent/graph/runner.py`: Pipeline orchestration + health checks + report generation.

        ## 5. Configuration overview
        `run_config.json` is the single source of truth for runs. The CLI requires a config path
(`paper-table-agent run --config <path>`). The UI loads defaults from `run_config.json` in the repo
root and overrides `table_path`/`pdf_folder` with the UI-selected values before launching a run.

**Top-level fields**
- `table_path` (required): input spreadsheet path.
- `pdf_folder` (required): folder of PDFs.
- `schema_sheet_name` (default: `schema`)
- `schema_mode` (default: `sheet`), `schema_path` (optional)
- `run_name` (optional), `title_col`, `authors_col`, `year_col` (optional)
- `treat_single_space_as_empty` (default: True)
- `verify_mode` (default: False)
- `fast_mode` (default: False)
- `max_success_mode` (default: True)
- `max_workers` (default: 1)

**Provider defaults**
- `provider.mode`: `openai`
- `provider.base_url`: `http://localhost:1234/v1`
- `provider.model_header`/`model_match`/`model_extract`/`model_query_helper`: `gpt-oss-20b`
- `provider.max_prompt_chars`: 64000
- `provider.mock_mode`: False
- `provider.fallback_enabled`: False

**Matching defaults**
- `top_k`: 10, `confidence_threshold`: 0.75,
  `confidence_margin`: 0.05, `year_tolerance`: 1

**Extraction defaults**
- `examples_per_col`: 3, `max_chunks`: 20,
  `retry_on_unclear`: True, `retry_extra_chunks`: 10
- `whole_text_enabled`: True, `whole_text_max_tokens`: 6000
- `paper_memory_enabled`: True, `paper_memory_max_tokens`: 1200

**Retrieval defaults**
- `top_k`: 20, `rerank_k`: 20, `max_context_chunks`: 24
- `max_context_tokens`: 2400, `context_window`: 1
- `include_section_chunks`: True, `section_chunk_limit`: 6
- `summary_enabled`: True, `summary_max_chunks`: 12
- `summary_max_tokens`: 1000, `query_variants`: 6
- `use_query_expansion`: True, `use_hyde`: True
- `embedding_backend`: tfidf, `reranker_backend`: tfidf
- `use_reranker`: True

**OCR defaults**
- `enable_ocr`: True, `ocr_trigger_min_chars_per_page`: 400

**Grobid defaults**
- `enable_grobid`: False, `server_url`: http://localhost:8070

**Output defaults**
- `debug_reports`: False

        ## 6. Database schema summary
        - `EXISTS`: event_id, level, event_type, payload_json, created_at

        ## 7. Prompt templates index
        - `paper_table_agent/prompts/match_header_extract.md` → `HeaderExtractionResult` (paper_table_agent/graph/matching.py)
- `paper_table_agent/prompts/match_adjudicate.md` → `AdjudicationResult` (paper_table_agent/graph/matching.py)
- `paper_table_agent/prompts/match_adjudicate_repair.md` → `AdjudicationResult` (paper_table_agent/graph/matching.py)
- `paper_table_agent/prompts/extract_group.md` → `GroupExtractionResult` (paper_table_agent/graph/extraction.py)
- `paper_table_agent/prompts/query_expand.md` → `QueryExpansionResult` (paper_table_agent/retrieval/pipeline.py)
- `paper_table_agent/prompts/hyde.md` → `HydeResult` (paper_table_agent/retrieval/pipeline.py)
- `paper_table_agent/prompts/verify_cell.md` → `VerifyResult` (paper_table_agent/graph/extraction.py)
- `paper_table_agent/prompts/verify_proposal.md` → `ProposalVerificationResult` (paper_table_agent/graph/extraction.py)

        ## 8. Output artifacts
        Runs live under `runs/<run_id>/` and include:
- `run_config.json`: captured config + prompt versions + git commit.
- `proposals.sqlite`: primary DB (matches, proposals, evidence, reviews, events).
- `run_report.json`: summary metrics + sanity/health checks.
- `logs/run.log`: run-time log output.
- `checkpoints.sqlite`: LangGraph checkpoints for resumability.
- `artifacts/parsed/`: parsed PDF text.
- `artifacts/retrieval_indexes/`: retrieval indexes/chunks.
- `artifacts/ocr/`: OCR outputs when enabled.
- `artifacts/thumbnails/`: PDF thumbnails for UI review.
- `exports/updated_table.xlsx`: exported table with decisions.
- `exports/audit_log.csv`: decision log.
- `exports/pdf_row_matches.csv`: debug-only row↔PDF match summary.
- `exports/mapping_report.html`: debug-only HTML mapping report.

        ## 9. Testing status
        Tests are in `D:/code/local/paper-table-agent/tests` and cover config validation, matching, retrieval,
extraction, UI defaults, and an integration run using stub providers. Run them with:

```bash
pytest
```

Coverage gaps: none currently tracked in tasks.md.

        ## 10. Known limitations / TODOs
        - (none listed)

        ## 11. How to reproduce a run
        ```bash
paper-table-agent run --config run_config.json
```

For offline testing, set `provider.mock_mode=true` or use the stub fixture config
(`tests/fixtures/stub_run_config.json`).
