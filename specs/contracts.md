# Contracts

- Status: Canonical focused spec
- Owner: Shared Contracts
- Depends on: `spec.md`, `contracts/schemas/*.json`
- Consumed by: main app, eval, optimizer, docs, tests

## Purpose

This file owns the human-readable filesystem and record contracts shared by the main app, eval, optimizer, review UI, and export path. JSON schemas under `contracts/schemas/` own machine-readable validation and should not be copied field-for-field here.

## Schema Files

Current machine-readable schemas:

- `contracts/schemas/run.schema.json`
- `contracts/schemas/config.snapshot.schema.json`
- `contracts/schemas/proposals.schema.json`
- `contracts/schemas/evidence.schema.json`
- `contracts/schemas/decisions.schema.json`
- `contracts/schemas/run_summary.schema.json`
- `contracts/schemas/audit_log.schema.json`

Schemas are versioned contract checks, not examples. Runtime artifacts may carry additional fields, but required fields and enums in schemas must remain truthful.

Current artifact schema tags are canonical names, not compatibility-version lanes:

- `run.json.artifact_schema_version` must be `main_run_bundle`.
- Every evidence record's `evidence_schema_version` must be `main_evidence`.

Active tooling must reject missing, legacy `.v2`, and unknown values. Archive material may preserve old tags only as historical data.

## Run Bundle Directory Contract

One main-app run writes one run bundle rooted at `{output_dir}/{run_id}/`. The bundle must be consumable from files alone by the browser UI after reload, eval, optimizer, and audit tooling.

Required stable files:

- `run.json`
- `proposals/proposals.jsonl`

Stable files when produced:

- `config.snapshot.json`
- `inputs/input_summary.json`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `proposals/proposal_index.json`
- evidence artifacts under `evidence/`
- parsed or page-text-compatible artifacts needed for evidence anchor validation
- matching artifacts for metadata extraction, candidate row scores, ambiguity, and duplicate-row diagnostics
- retrieval artifacts under `retrieval/`, including per-cell retrieval records and prepared per-paper indexes under `retrieval/_indexes/`
- export artifacts under `exports/`

Stable conceptual directories:

- `inputs/`
- `style_profiles/`
- `parsed/`
- `matching/`
- `retrieval/`
- `proposals/`
- `evidence/`
- `review/`
- `summaries/`
- `diagnostics/`
- `exports/`

Directory internals may evolve, but downstream tools must keep finding the stable conceptual categories above.

Prepared retrieval indexes are generated run artifacts, not authored inputs. Each index must carry a schema tag, document fingerprint, document identity, retrieval mode, caption/table inclusion policy, typed scoring context, source-grounded retrieval chunks, candidate chunks, chunk counts, and lexical scoring metadata. Consumers must treat mismatched schema, document, mode, inclusion policy, or typed scoring context as invalid rather than silently reusing the index.

## Stable Identifiers

Proposal, evidence, decision, eval, and optimizer joins depend on:

- `row_id`
- `column_name`
- `cell_id`

`row_index` may be retained for debug context or fallback display, but it is not the canonical cross-tool join identity.

## Proposal Semantics

Each persisted proposal record represents one target-cell semantic outcome. The canonical proposal record stream is `proposals/proposals.jsonl`; lookup/index files are secondary.

Canonical proposal fields include:

- `proposal_status`: `value_proposed`, `no_data`, `unresolved`, `not_applicable`, `not_attempted`, or `error`
- `evidence_status`: `direct_strong`, `direct_weak`, `inferred_strong`, `inferred_weak`, `no_evidence`, or `not_applicable`
- `review_bucket`: `review`, `attention`, or `diagnostic`
- `reason_codes`: stable explanatory strings with forward-compatible extension
- evidence ids, with one primary evidence item when applicable

`review_bucket` is derived from `proposal_status`, `evidence_status`, and `reason_codes`; serialized values must validate against the derived route. Diagnostic-only global outcomes such as unmatched PDFs, duplicate-row conflicts, or pure retrieval-empty pre-cell failures should remain diagnostics instead of being forced into fake reviewable proposals.

Useful unresolved target-cell outcomes belong in `attention` when they carry rationale, candidate text, ambiguity/conflict context, or manual-edit value. Pure process failures remain `diagnostic`.

## Evidence Semantics

Evidence is attached to proposals and must remain inspectable.

Supported evidence categories include:

- direct quote evidence
- inferred reasoning
- calculation-based justification
- approximate highlight evidence
- quote-plus-page evidence
- caption-grounded figure evidence
- visual-interpretation figure evidence

Figure-derived evidence must remain distinguishable from text-derived evidence. Retrieval figure chunks are whole-figure chunks, not panel-level persisted retrieval units. Panel reasoning may happen inside a prompt, but the persisted retrieval contract remains figure-level.

Evidence artifacts must preserve enough source text, page reference, quote text, and compatible parsed-document material for eval to distinguish valid anchors, present-but-unvalidated evidence, invalid anchors, and missing evidence.

Retrieval artifacts must preserve source text separately from retrieval-only context. `display_text` remains the source-preserving text used for review and evidence anchoring, while `retrieval_text` may include conservative context used for retrieval scoring. The default typed scoring context may add chunk-type, section, figure, and table markers to `retrieval_text`, but it must not add page-number tokens. Extraction prompt headers may expose section, table, and figure orientation metadata, but prompt passage bodies must remain source-preserving.

Figure-review diagnostics are part of the run-bundle evidence contract. Per-cell diagnostics record trigger reasons, planner decisions, shortlisted figures, image source/fallback, attempt result states, dropped/no-hit reasons, accepted hit counts, and persisted useful evidence. Per-run summaries roll these fields up for optimizer comparison.

## Reason Codes And Support Labels

Backend-generated reason codes should be centralized in code constants where practical. JSON accepts arbitrary strings for forward compatibility, but generated reason codes should be stable enough for docs, UI, eval, and optimizer reports.

Common reason-code families:

- explicit absence: `explicitly_not_reported`, `not_reported`
- retrieval/evidence weakness: `retrieval_empty`, `insufficient_evidence`, `ambiguous_evidence`, `conflicting_evidence`
- anchoring: `anchor_fallback`, `approximate_anchor`
- derivation: `calculation`
- applicability/scope: `schema_not_applicable`, `cell_not_targeted`, `column_excluded`
- matching: `pdf_unmatched`, `row_unmatched`, `duplicate_row_conflict`
- runtime failure: `provider_error`, `parser_error`, `invalid_model_output`

Legacy persisted `state` and `support` fields are not part of new proposal records. Current records must use `proposal_status`, `evidence_status`, `review_bucket`, and `reason_codes`.

## Review Decision Contract

Review decisions are first-class artifacts in `review/decisions.jsonl`. Valid decisions are:

- `accepted`
- `accepted_with_edit`
- `confirmed_no_data`
- `rejected`

New decision-source values are:

- `human_individual`
- `human_bulk_accept`
- `automation_accept_all`

Legacy `human_reviewer` remains readable for backward compatibility, but new manual decisions must use the explicit individual or bulk values.

Bulk accept applies only to the currently visible filtered subset. Headless `--accept-all` records automation acceptance explicitly and must not be confused with human review.

## Export Contract

Export writes new artifacts under `exports/`. The source workbook is never mutated in place.

Exports include only explicitly accepted changes. Rejected, unreviewed, diagnostic, and confirmed-no-data outcomes are not written as accepted cell values. Audit logs must preserve proposal id, cell id, decision, decision source, exported value when applicable, and auto-accept truth.

## Portable Agent-Kit Review Contract

`skills/papers-to-table-agent-kit/` has a separate authoring contract for external agents that bring their own extraction capability. It is not a main-app run bundle input contract.

Agents author only:

- `review_input.json`
- `pdfs/`
- optional `source_table.csv`
- optional `schema.json`

`build_review_package.py` derives the MVP generated artifacts:

- `review/index.html`
- `review/assets/*`
- `review/review_package.json`
- `normalized/proposals.jsonl`
- `normalized/evidence.jsonl`
- `summaries/validation_report.json`

Review/export then generates:

- `review/decisions.jsonl`
- `exports/final_table.csv`
- `exports/audit_log_*.json`
- `summaries/reviewer_summary.json`

`review_input.json` uses `papers_to_table.review_input.v1`. Authored `proposal_id`, `evidence_id`, `cell_id`, and `created_at` are optional. The builder generates stable deterministic IDs when they are absent and validation checks uniqueness and references when they are supplied.

Every non-empty proposed value must have at least one structured evidence record. Evidence is tiered for validation and UI labels:

- Tier A: `pdf_id` plus `page_number` plus quote/table/caption/evidence text maps to `direct_strong`.
- Tier B: `pdf_id` plus `page_number` plus exact/approximate bbox regions maps to `direct_strong` or `direct_weak`.
- Tier C: `pdf_id` plus `page_number` plus `source_location` and/or `reasoning` maps to `inferred_weak` and attention.
- Tier D: no structured evidence is invalid for non-empty proposed values.

Generated agent-kit evidence records use `evidence_schema_version="main_evidence"` and must emit main-compatible `source_type` values. Kit-authored text kinds such as `table_text`, `caption_text`, and `evidence_text` are preserved in a separate `authored_evidence_kind` field while normalized `source_type` maps to a main-compatible value such as `direct_quote`.

`validate_review_package.py` must validate authored and generated highlight regions for finite numeric coordinates, positive page references, nonzero area, normalized-coordinate ranges when applicable, and warnings for mixed or otherwise ambiguous coordinate conventions.

## Eval Summary Contract

Eval outputs must preserve stable per-run and comparison artifacts containing:

- explicit scored/unscored state
- `unscored_reason` when applicable
- headline content correctness metrics
- secondary metadata or overall metrics when available
- evidence metrics and anchor-validation totals
- missing-proposal and join-failure accounting
- judge failure and judge-disagreement diagnostics
- structured deterministic failure diagnostics
- compact main-app provenance passthrough needed by optimizer
- canonical proposal-status, evidence-status, review-bucket, and reason-code accounting

Dual-judge runs must preserve per-judge verdicts, request failures, unclear counts, disagreement metrics, response-mode usage, and enough detail for trust reporting.

Per-cell scored records for structured fields must preserve `deterministic_failure_kind` and `adjudication_eligible`. These fields are diagnostic only: current structured scoring remains deterministic, headline correctness metrics are unchanged by future-adjudication eligibility, and no structured judge records are emitted.

Run summaries must include the diagnostic metrics `structured_deterministic_failure_count`, `structured_adjudication_eligible_count`, `structured_adjudication_eligible_failure_rate`, and the compatibility alias `structured_adjudication_eligible_rate`.

## Optimizer Candidate And Result Contract

Optimizer candidate bundles are immutable candidate-specific records. They must preserve:

- candidate id and optional parent lineage
- benchmark id, suite id, and replicate identity when applicable
- prompt bundle id
- text model id and optional vision model id
- optimizer-controlled knob values
- candidate hash

Candidate result rows must preserve:

- schema version
- experiment/study id and study type
- candidate identity and lineage
- benchmark, suite, and replicate identity when applicable
- primary, guardrail, runtime, and diagnostic metrics
- main-app run reference
- eval-output reference
- explicit scored, degraded-score, unscored, or failed state
- decision and decision reason

Optimizer reports must distinguish best raw completed candidate, eligible winner under gates, provisional winner, and recommended default when trust caveats differ.

## Schema-Version And Verification Expectations

Run bundles and evidence record streams must publish explicit schema-version fields. Downstream tools must validate the canonical supported values instead of guessing or accepting legacy unversioned bundles.

Contract verification command:

```bash
python scripts/papers_to_table.py verify-contract --run /abs/path/to/run_bundle
```

Use `--json` for machine-readable output. The verifier checks required files, JSON-schema shape, and cross-file consistency across proposals, evidence, decisions, and audit logs.
