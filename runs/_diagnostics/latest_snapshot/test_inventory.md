# Test inventory

## tests/test_cli_entrypoint.py
- `test_console_script_entrypoint`: console script entrypoint

## tests/test_config.py
- `test_run_config_validation`: run config validation

## tests/test_context_plan_integration.py
- `test_fulltext_context_plan_and_extraction_with_spans`: fulltext context plan and extraction with spans
- `test_memory_context_payload_notes_only`: memory context payload notes only

## tests/test_context_planner.py
- `test_fulltext_trimming_drops_references_first`: fulltext trimming drops references first

## tests/test_eval_harness.py
- `test_eval_harness_metrics_and_run_report_update`: eval harness metrics and run report update
- `test_export_skips_audit_proposals`: export skips audit proposals

## tests/test_evidence_anchor.py
- `test_evidence_quotes_use_space_preserving_text`: evidence quotes use space preserving text
- `test_quote_locator_finds_span`: quote locator finds span
- `test_found_values_require_anchored_quote`: found values require anchored quote

## tests/test_evidence_finder.py
- `test_fallback_evidence_attached_when_missing`: fallback evidence attached when missing
- `test_rejects_too_short_highlight_quote`: rejects too short highlight quote

## tests/test_extraction.py
- `test_apply_evidence_rules_repairs_missing_chunk_id`: apply evidence rules repairs missing chunk id
- `test_apply_evidence_rules_accepts_valid_quote`: apply evidence rules accepts valid quote
- `test_apply_evidence_rules_accepts_normalized_quote`: apply evidence rules accepts normalized quote
- `test_apply_evidence_rules_accepts_chunk_id_unicode_dash`: apply evidence rules accepts chunk id unicode dash
- `test_apply_evidence_rules_salvages_quote_span`: apply evidence rules salvages quote span

## tests/test_highlight.py
- `test_locate_quote_finds_bbox_in_fixture_pdf`: locate quote finds bbox in fixture pdf
- `test_locate_quote_handles_ellipsis_fragments`: locate quote handles ellipsis fragments
- `test_salvage_quote_from_tokens_finds_span`: salvage quote from tokens finds span
- `test_rejects_page_spanning_rects`: rejects page spanning rects

## tests/test_integration.py
- `test_end_to_end_with_stub_llm_cli`: end to end with stub llm cli
- `test_registry_lists_runs`: registry lists runs
- `test_integration_run_report_and_validation`: integration run report and validation
- `test_end_to_end_with_mock_mode`: end to end with mock mode
- `test_mock_mode_backfills_missing_evidence`: mock mode backfills missing evidence

## tests/test_live_llm_e2e.py
- `test_live_llm_smoke_e2e`: live llm smoke e2e

## tests/test_llm_guided_json_fallback.py
- `test_guided_json_fallback_on_regex_error`: guided json fallback on regex error
- `test_constraints_off_for_lm_studio_disables_response_format`: constraints off for lm studio disables response format

## tests/test_llm_json_parsing.py
- `test_parse_json_with_leading_text`: parse json with leading text
- `test_parse_json_last_fenced_block`: parse json last fenced block
- `test_parse_json_array_span`: parse json array span
- `test_parse_json_with_think_block`: parse json with think block
- `test_parse_json_with_think_and_fence`: parse json with think and fence

## tests/test_llm_prompt_budget.py
- `test_extract_prompt_respects_token_budget`: extract prompt respects token budget
- `test_extract_prompt_batches_keep_chunks_and_cover_columns`: extract prompt batches keep chunks and cover columns

## tests/test_llm_provider.py
- `test_stub_llm_provider_returns_deterministic_json`: stub llm provider returns deterministic json
- `test_guided_json_fallback_on_regex_error`: guided json fallback on regex error
- `test_strip_regex_from_json_schema_removes_pattern_keys`: strip regex from json schema removes pattern keys

## tests/test_locks.py
- `test_single_space_is_empty`: single space is empty
- `test_nan_is_empty`: nan is empty

## tests/test_match_adjudication_parsing.py
- `test_adjudication_tolerates_string_candidates_and_evidence`: adjudication tolerates string candidates and evidence

## tests/test_matching.py
- `test_shortlist_candidates`: shortlist candidates
- `test_shortlist_candidates_prefers_doi_match`: shortlist candidates prefers doi match
- `test_deterministic_match_threshold`: deterministic match threshold
- `test_deterministic_match_margin`: deterministic match margin
- `test_adjudication_requires_row_id_only_for_matched`: adjudication requires row id only for matched

## tests/test_normalization.py
- `test_normalize_str_for_prompt_filters_nan`: normalize str for prompt filters nan
- `test_normalize_chunk_id_unifies_unicode_dash`: normalize chunk id unifies unicode dash
- `test_build_column_query_omits_empty_examples`: build column query omits empty examples

## tests/test_parsing_quality.py
- `test_parsing_preserves_spaces_and_token_lengths`: parsing preserves spaces and token lengths

## tests/test_retrieval.py
- `test_dense_retrieval_scores`: dense retrieval scores
- `test_retrieval_smoke_fixture_pdf`: retrieval smoke fixture pdf
- `test_chunk_pk_is_unique_across_pdfs`: chunk pk is unique across pdfs
- `test_hash_embedding_backend_retrieval`: hash embedding backend retrieval

## tests/test_run_report_capabilities.py
- `test_run_report_includes_llm_capabilities`: run report includes llm capabilities

## tests/test_runner.py
- `test_empty_extraction_groups_default_to_schema`: empty extraction groups default to schema
- `test_align_schema_columns_normalizes_nbsp`: align schema columns normalizes nbsp
- `test_matching_fallback_triggers_llm_adjudication`: matching fallback triggers llm adjudication
- `test_matching_fallback_invokes_llm`: matching fallback invokes llm

## tests/test_schema.py
- `test_load_schema`: load schema
- `test_validate_schema_columns_missing`: validate schema columns missing

## tests/test_snapshot.py
- `test_snapshot_command_creates_expected_files`: snapshot command creates expected files

## tests/test_stub_run_cli.py
- `test_stub_run_produces_evidence`: stub run produces evidence

## tests/test_ui_defaults.py
- `test_ui_defaults_from_config`: ui defaults from config

## tests/test_ui_smoke.py
- `test_ui_smoke_mode`: ui smoke mode

## tests/test_ui_streamlit.py
- `test_review_ui_loads_stub_proposals`: review ui loads stub proposals

## tests/test_verification_support.py
- `test_verify_proposals_downgrades_when_no_overlap`: verify proposals downgrades when no overlap
- `test_verify_proposals_requires_numeric_overlap`: verify proposals requires numeric overlap
- `test_verify_proposals_accepts_numeric_match`: verify proposals accepts numeric match
