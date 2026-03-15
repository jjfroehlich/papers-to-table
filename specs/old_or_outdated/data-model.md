# Paper Table Agent — `data-model.md`

## Purpose

This document defines the core domain model for Paper Table Agent.

It translates the product behavior in `spec.md` and the implementation choices in `plan.md` into explicit entities, relationships, enums, invariants, and storage expectations.

This is the source of truth for the main application objects. Lower-level transport schemas may be generated from or aligned with this model in `contracts/`.

---

## Modeling principles

* Domain objects should reflect the **paper-to-table review workflow**, not a generic chat/RAG system.
* Objects should separate **canonical records** from **derived diagnostics**.
* Evidence must remain **source-linked and reviewable**.
* Review decisions must be **auditable and non-destructive**.
* Parser- and provider-specific details should not leak into the top-level product model unless they affect user-visible behavior or reproducibility.
* Filesystem artifacts are the canonical run bundle; the operational database stores queryable state derived from and linked to those artifacts.

---

## Entity overview

The core entities are:

1. `Run`
2. `InputTable`
3. `SchemaColumn`
4. `TableRow`
5. `TableCell`
6. `PdfDocument`
7. `ParsedDocument`
8. `ParsedElement`
9. `Chunk`
10. `RowMatch`
11. `ExtractionTarget`
12. `Proposal`
13. `EvidenceItem`
14. `HighlightAnchor`
15. `ReviewDecision`
16. `ExportBundle`
17. `EvalResult`
18. `RunArtifact`
19. `ProviderProbe`
20. `RunDiagnostic`

---

## Relationship map

### High-level relationships

* One `Run` has one `InputTable`.
* One `Run` has many `SchemaColumn` records.
* One `Run` has many `TableRow` records.
* One `TableRow` has many `TableCell` records.
* One `Run` has many `PdfDocument` records.
* One `PdfDocument` has one `ParsedDocument` per parser backend used.
* One `ParsedDocument` has many `ParsedElement` records.
* One `ParsedDocument` has many `Chunk` records.
* One `PdfDocument` may have many `RowMatch` candidates but at most one winning row assignment per run.
* One `TableRow` + `SchemaColumn` + `PdfDocument` combination may yield one or more `Proposal` records over time, but only one latest active proposal per proposal kind.
* One `Proposal` has many `EvidenceItem` records.
* One `EvidenceItem` may have zero or one `HighlightAnchor`.
* One `Proposal` may have many `ReviewDecision` records over time, but only one latest effective decision.
* One `Run` may have many `ExportBundle` records.
* One `Run` has zero or one latest `EvalResult` per evaluation mode.
* One `Run` has many `RunArtifact` records.
* One `Run` has many `RunDiagnostic` records.
* One `Run` may have many `ProviderProbe` records.

---

## Core entities

## 1) `Run`

Represents one end-to-end execution of the pipeline for a specific table/schema/PDF set and configuration.

### Required fields

* `run_id`
* `created_at`
* `started_at`
* `completed_at`
* `status`
* `run_dir`
* `config_snapshot_path`
* `table_id`
* `input_fingerprint`
* `effective_config`

### Optional fields

* `label`
* `initiated_by`
* `why_no_values`
* `summary_metrics`
* `notes`

### Status enum

* `created`
* `running`
* `completed`
* `completed_with_warnings`
* `failed`
* `cancelled`

### Notes

* `effective_config` stores the resolved configuration that actually ran.
* `input_fingerprint` captures enough information to distinguish materially different runs.
* `summary_metrics` is derived, but persisted for fast UI display.

---

## 2) `InputTable`

Represents the input spreadsheet as understood by the run.

### Required fields

* `table_id`
* `run_id`
* `source_path`
* `format`
* `sheet_name`
* `row_count`
* `column_count`
* `table_fingerprint`

### Optional fields

* `source_display_name`
* `original_workbook_metadata`
* `schema_mode`
* `schema_source_path`

### Format enum

* `csv`
* `xlsx`

### Schema mode enum

* `embedded`
* `separate`

---

## 3) `SchemaColumn`

Defines one target column from the schema and its extraction behavior.

### Required fields

* `schema_column_id`
* `run_id`
* `column_key`
* `column_name`
* `definition`
* `position`
* `enabled`

### Optional fields

* `data_type`
* `unit`
* `allowed_values`
* `examples`
* `metadata_only`
* `in_paper`
* `required_evidence_level`
* `preferred_context_mode`
* `preferred_evidence_sources`
* `extraction_group`
* `normalization_rules`
* `validation_rules`
* `schema_hints`

### Suggested data type enum

* `string`
* `integer`
* `float`
* `boolean`
* `categorical`
* `list`
* `range`
* `text`

### Suggested preferred context mode enum

* `auto`
* `retrieval`
* `fulltext`
* `memory`

### Suggested preferred evidence source enum values

* `table`
* `caption`
* `abstract`
* `methods`
* `results`
* `figure_text`
* `any`

### Notes

* `column_key` is the normalized, stable identifier used everywhere else.
* `schema_hints` is the extensibility field for policies such as table-first or caption-aware.

---

## 4) `TableRow`

Represents one row from the input table.

### Required fields

* `row_id`
* `run_id`
* `row_index`
* `row_key`
* `row_context`

### Optional fields

* `source_row_identifier`
* `display_label`
* `normalized_metadata`

### Notes

* `row_key` should remain stable within a run even if the displayed row number changes through filtering.
* `row_context` is a normalized object containing fields useful for matching and extraction prompts.

---

## 5) `TableCell`

Represents one source-table cell at run time.

### Required fields

* `cell_id`
* `run_id`
* `row_id`
* `schema_column_id`
* `original_value`
* `cell_state`

### Optional fields

* `normalized_original_value`
* `treat_as_empty_reason`
* `verify_mode_enabled`
* `audit_target`

### Cell state enum

* `empty`
* `locked`
* `review_only`
* `audit_target`
* `skipped`

### Notes

* `locked` means non-empty and protected by default.
* `review_only` is for verify-like behavior where the system may generate a comparison proposal but not export automatically.

---

## 6) `PdfDocument`

Represents one PDF or other supported document ingested in the run.

### Required fields

* `pdf_id`
* `run_id`
* `source_path`
* `filename`
* `file_fingerprint`
* `page_count`
* `ingestion_status`

### Optional fields

* `display_title`
* `mime_type`
* `document_group`
* `is_supplement`
* `parse_warnings`
* `ocr_used`

### Ingestion status enum

* `pending`
* `parsed`
* `parsed_with_warnings`
* `failed`
* `skipped`

### Notes

* `document_group` can later support main-paper/supplement relationships without forcing that complexity into v1 behavior.

---

## 7) `ParsedDocument`

Represents one normalized parser output for one PDF and one backend.

### Required fields

* `parsed_document_id`
* `run_id`
* `pdf_id`
* `parser_backend`
* `parser_version`
* `normalized_contract_version`
* `status`
* `artifact_path`
* `page_count`

### Optional fields

* `document_metadata`
* `parse_metrics`
* `warnings`
* `is_primary_for_run`

### Status enum

* `ok`
* `ok_with_warnings`
* `partial`
* `failed`

### Notes

* A run may keep multiple parsed-document records for one PDF if multiple backends are used.
* One record may be marked `is_primary_for_run=true` for downstream consumption.

---

## 8) `ParsedElement`

Represents one typed structural unit extracted from a parsed document.

### Required fields

* `parsed_element_id`
* `parsed_document_id`
* `pdf_id`
* `element_type`
* `page_start`
* `page_end`
* `order_index`
* `text`

### Optional fields

* `text_raw`
* `text_norm`
* `bbox`
* `section_label`
* `element_metadata`
* `source_backend_id`

### Element type enum

* `title`
* `abstract`
* `section_header`
* `paragraph`
* `figure_caption`
* `table_region`
* `table_cell_summary`
* `reference_block`
* `header`
* `footer`
* `unknown`

### Notes

* `text` should remain source-preserving enough for quote display when possible.
* `bbox` may be null when geometry is unavailable.

---

## 9) `Chunk`

Represents one retrieval unit derived from parsed elements.

### Required fields

* `chunk_id`
* `chunk_pk`
* `run_id`
* `pdf_id`
* `parsed_document_id`
* `chunk_type`
* `chunk_index`
* `text`
* `retrieval_text`

### Optional fields

* `text_raw`
* `text_norm`
* `page_start`
* `page_end`
* `section_label`
* `source_element_ids`
* `neighbor_chunk_ids`
* `chunk_metadata`

### Chunk type enum

* `abstract`
* `section_header`
* `paragraph`
* `figure_caption`
* `table_region`
* `table_cell_summary`
* `reference_block`
* `page_fallback`
* `unknown`

### Notes

* `chunk_pk` is the globally unique operational key.
* `text` and `text_raw` are for evidence operations; `retrieval_text` is for indexing/ranking.

---

## 10) `RowMatch`

Represents a candidate or resolved assignment of a PDF to a table row.

### Required fields

* `row_match_id`
* `run_id`
* `pdf_id`
* `row_id`
* `match_stage`
* `match_status`
* `score`

### Optional fields

* `confidence`
* `deterministic_features`
* `model_rationale`
* `model_evidence`
* `rank`
* `is_winner`
* `duplicate_group`

### Match stage enum

* `deterministic`
* `adjudication`
* `final`

### Match status enum

* `candidate`
* `matched`
* `ambiguous`
* `unmatched`
* `duplicate`
* `rejected`

### Notes

* Multiple candidate matches may exist.
* At most one record per `pdf_id` per run should be the final winner.

---

## 11) `ExtractionTarget`

Represents one attempted extraction unit for one row, column, and PDF.

### Required fields

* `extraction_target_id`
* `run_id`
* `row_id`
* `schema_column_id`
* `pdf_id`
* `target_kind`
* `target_status`

### Optional fields

* `context_mode`
* `batch_id`
* `skip_reason`
* `attempt_count`
* `prompt_budget_summary`

### Target kind enum

* `missing_cell`
* `verify_only`
* `audit`

### Target status enum

* `pending`
* `attempted`
* `skipped`
* `failed`
* `completed`

### Notes

* This is useful for coverage accounting even when no proposal is produced.

---

## 12) `Proposal`

Represents one proposed value or one explicit non-value outcome for a target cell.

### Required fields

* `proposal_id`
* `run_id`
* `extraction_target_id`
* `row_id`
* `schema_column_id`
* `pdf_id`
* `proposal_kind`
* `proposal_status`
* `created_at`

### Optional fields

* `proposed_value`
* `normalized_value`
* `value_type`
* `value_unit`
* `rationale_short`
* `confidence`
* `needs_more_context`
* `needs_more_evidence`
* `evidence_strength`
* `validation_summary`
* `proposal_version`
* `supersedes_proposal_id`
* `is_latest`

### Proposal kind enum

* `normal`
* `verify`
* `audit`

### Proposal status enum

* `found`
* `inferred`
* `unclear`
* `error`
* `skipped`

### Evidence strength enum

* `strong`
* `weak`
* `none`

### Notes

* `found` means directly supported enough to count as strong proposal state.
* `inferred` means a plausible value exists but support is indirect or incomplete.
* `rationale_short` is concise reviewer-facing explanation, not chain-of-thought.

---

## 13) `EvidenceItem`

Represents one piece of evidence attached to a proposal.

### Required fields

* `evidence_item_id`
* `proposal_id`
* `run_id`
* `pdf_id`
* `evidence_status`
* `quote_text`

### Optional fields

* `quote_text_raw`
* `page`
* `page_start`
* `page_end`
* `anchor_id`
* `chunk_id`
* `chunk_pk`
* `chunk_index`
* `source_ref`
* `why_it_matters`
* `numeric_value`
* `quote_start`
* `quote_end`
* `validation_errors`
* `quality_flags`

### Evidence status enum

* `found`
* `inferred`
* `weak`
* `missing`
* `failed`

### Notes

* Each evidence item must belong to the same `pdf_id` as its proposal.
* `quote_text` is required even when evidence is weak, unless the status is `missing` or `failed` and the object exists only for diagnostics.

---

## 14) `HighlightAnchor`

Represents viewer-usable highlight coordinates or anchor metadata for one evidence item.

### Required fields

* `highlight_anchor_id`
* `evidence_item_id`
* `anchor_type`
* `page`

### Optional fields

* `rects`
* `quote_start`
* `quote_end`
* `token_spans`
* `anchor_confidence`
* `anchor_status`
* `anchor_notes`

### Anchor type enum

* `rect`
* `quote_span`
* `token_span`
* `page_only`

### Anchor status enum

* `ok`
* `salvaged`
* `failed`

### Notes

* `rects` should use a consistent coordinate convention documented in `contracts/`.
* One evidence item may later support multiple rectangles, but v1 may treat this as one object with an array field.

---

## 15) `ReviewDecision`

Represents one reviewer action on one proposal.

### Required fields

* `review_decision_id`
* `proposal_id`
* `run_id`
* `decision`
* `decided_at`

### Optional fields

* `reviewer_id`
* `edited_value`
* `edited_unit`
* `comment`
* `supersedes_review_decision_id`
* `is_latest`

### Decision enum

* `accepted`
* `accepted_with_edit`
* `rejected`
* `deferred`

### Notes

* Review decisions are append-only in spirit. Later decisions supersede earlier ones rather than deleting them.

---

## 16) `ExportBundle`

Represents one export operation and its resulting files.

### Required fields

* `export_bundle_id`
* `run_id`
* `created_at`
* `export_status`
* `updated_table_path`
* `audit_log_path`

### Optional fields

* `evaluation_path_json`
* `evaluation_path_md`
* `export_summary`
* `row_count_changed`
* `cell_count_changed`

### Export status enum

* `pending`
* `completed`
* `failed`

### Notes

* The export bundle represents a generated output set, not a mutable stateful spreadsheet session.

---

## 17) `EvalResult`

Represents evaluation output for a run.

### Required fields

* `eval_result_id`
* `run_id`
* `evaluation_mode`
* `created_at`
* `status`

### Optional fields

* `overall_metrics`
* `per_column_metrics`
* `evidence_metrics`
* `notes`
* `artifact_json_path`
* `artifact_md_path`

### Evaluation mode enum

* `audit_cells`
* `gold_fixture`
* `other`

### Status enum

* `ok`
* `no_targets`
* `partial`
* `failed`

---

## 18) `RunArtifact`

Represents one file or artifact emitted during a run.

### Required fields

* `run_artifact_id`
* `run_id`
* `artifact_type`
* `relative_path`
* `exists`

### Optional fields

* `content_hash`
* `size_bytes`
* `generated_at`
* `debug_only`
* `notes`

### Artifact type enum

* `config`
* `database`
* `log`
* `parsed_document`
* `retrieval_index`
* `ocr`
* `thumbnail`
* `export`
* `evaluation`
* `report`
* `debug`
* `other`

---

## 19) `ProviderProbe`

Represents one recorded capability or compatibility probe for a model/provider/backend.

### Required fields

* `provider_probe_id`
* `run_id`
* `provider_role`
* `provider_name`
* `model_name`
* `probe_type`
* `probe_result`
* `recorded_at`

### Optional fields

* `capability_summary`
* `error_code`
* `error_message`
* `recommended_action`

### Provider role enum

* `header`
* `matching`
* `extraction`
* `helper`
* `embedding`
* `reranker`

### Probe type enum

* `structured_output`
* `compatibility`
* `health`
* `ctx_window`

### Probe result enum

* `supported`
* `unsupported`
* `partial`
* `failed`

---

## 20) `RunDiagnostic`

Represents a structured diagnostic event or summary attached to a run.

### Required fields

* `run_diagnostic_id`
* `run_id`
* `diagnostic_scope`
* `diagnostic_level`
* `message`
* `recorded_at`

### Optional fields

* `pdf_id`
* `row_id`
* `schema_column_id`
* `proposal_id`
* `data`
* `diagnostic_code`

### Diagnostic scope enum

* `run`
* `pdf`
* `matching`
* `retrieval`
* `extraction`
* `evidence`
* `review`
* `export`
* `evaluation`
* `provider`

### Diagnostic level enum

* `info`
* `warning`
* `error`

---

## Derived views and aggregates

These are not necessarily first-class persisted tables in v1, but they are important conceptual outputs.

### `ProposalReviewView`

A UI-focused projection that combines:

* proposal
* latest review decision
* row context
* column metadata
* evidence summary
* risk/triage signals

### `RunSummaryView`

A run dashboard projection combining:

* run status
* counts by proposal status
* evidence coverage
* highlight success rate
* review progress
* export presence

### `PdfMatchSummaryView`

A matching-oriented view combining:

* PDF metadata
* candidate rows
* winner
* ambiguity/duplicate signals

---

## Key invariants

### Run invariants

* A `Run` must have exactly one `InputTable`.
* A `Run` must have a resolved effective config snapshot.
* A run directory must exist for every persisted run.

### Matching invariants

* For a given `pdf_id` in a run, at most one `RowMatch` may be the final winning match.
* A `matched` final winner must refer to an existing `row_id`.

### Proposal invariants

* Every `Proposal` must link to one `ExtractionTarget`.
* Every `Proposal` must reference exactly one `row_id`, one `schema_column_id`, and one `pdf_id`.
* For a given `(run_id, row_id, schema_column_id, pdf_id, proposal_kind)`, at most one proposal may be marked `is_latest=true`.
* `normal` proposals are export-eligible only through explicit review decisions.
* `audit` proposals are never exportable by default.

### Evidence invariants

* Every `EvidenceItem` must belong to the same `pdf_id` as its parent `Proposal`.
* Every non-empty `Proposal.proposed_value` should have at least one `EvidenceItem` unless the proposal is explicitly flagged as lacking usable evidence.
* `quote_text` used for display must come from a source-preserving field, not only normalized text.

### Review invariants

* Review decisions do not mutate or erase the original proposal object.
* For a given `proposal_id`, at most one `ReviewDecision` may be the latest effective decision.

### Export invariants

* Exports must never overwrite the original input table in place.
* Only accepted or accepted-with-edit decisions may generate export changes.

---

## Canonical versus derived data

### Canonical records

These should be treated as authoritative persisted state:

* `Run`
* `InputTable`
* `SchemaColumn`
* `TableRow`
* `TableCell`
* `PdfDocument`
* `ParsedDocument`
* `Chunk`
* `RowMatch`
* `ExtractionTarget`
* `Proposal`
* `EvidenceItem`
* `HighlightAnchor`
* `ReviewDecision`
* `ExportBundle`
* `EvalResult`
* `RunArtifact`

### Derived or recomputable records

These may be persisted for convenience, but are conceptually derived:

* summary metrics
* triage scores
* review queue ordering
* proposal review views
* run summary views
* some diagnostics summaries

---

## Suggested indexing and key strategy

### Stable identifiers

Each major entity should use a stable application ID rather than a raw database row number in external-facing contracts.

### Recommended unique constraints

* `SchemaColumn(run_id, column_key)`
* `TableRow(run_id, row_key)`
* `TableCell(run_id, row_id, schema_column_id)`
* `PdfDocument(run_id, file_fingerprint)`
* `Chunk(run_id, pdf_id, chunk_id)`
* `RowMatch(run_id, pdf_id, row_id, match_stage, rank)`
* `ExtractionTarget(run_id, row_id, schema_column_id, pdf_id, target_kind)`
* `Proposal(run_id, proposal_id)`
* `RunArtifact(run_id, relative_path)`

### Operational indexes

Index at minimum on:

* `Proposal(run_id, proposal_kind, proposal_status, is_latest)`
* `ReviewDecision(proposal_id, is_latest)`
* `EvidenceItem(proposal_id)`
* `RowMatch(pdf_id, is_winner)`
* `Chunk(pdf_id, chunk_type)`

---

## Storage notes

### Filesystem artifact structure

The filesystem bundle should preserve enough information to reconstruct or inspect:

* parser outputs
* retrieval indexes
* run reports
* logs
* exports
* evaluation outputs

### Database notes

The operational database stores normalized queryable state for UI and resumability.
It is not the only record of truth; it links back to artifacts in the run directory.

---

## Contract boundary guidance

### Good candidates for API schemas

* `RunSummaryView`
* `ProposalReviewView`
* `ReviewDecision` input/output objects
* `ExportBundle` summary
* `EvalResult` summary

### Keep internal for now

* parser-backend raw metadata
* raw retrieval cache internals
* low-level provider payload traces
* debug-only artifact details that are not part of the stable UI/API contract

---

## Open modeling questions

* [NEEDS CLARIFICATION: Do we need a first-class `PaperMemoryArtifact` entity, or is that just a `RunArtifact` plus proposal metadata in v1?]
* [NEEDS CLARIFICATION: Should `ParsedElement` always be persisted in the operational database, or only in parser artifacts with selected projections stored as `Chunk`s?]
* [NEEDS CLARIFICATION: Do we need first-class support for one row aggregating multiple PDFs in v1, or should the model remain one proposal source PDF per target cell?]
* [NEEDS CLARIFICATION: Should triage/risk scoring be a first-class persisted entity or a derived view?]
* [NEEDS CLARIFICATION: Which schema-hint keys are guaranteed contractual fields versus flexible metadata?]

---

## Concise summary

Paper Table Agent’s data model is centered on five things:

* a reproducible `Run`
* normalized `PdfDocument` and parsing/retrieval artifacts
* schema-driven `Proposal` generation with `EvidenceItem`s
* append-only `ReviewDecision`s
* safe audited `ExportBundle`s

This model keeps the system aligned with the product: trustworthy paper-to-table extraction with human review, not generic document chat.
