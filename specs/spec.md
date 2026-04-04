# Extract Structured Info from Papers Eval - spec.md

## Status

Initial product specification for a separate CLI-first evaluation repository.

## Purpose

This repository evaluates run artifact bundles produced by `extract-structured-info-from-papers` against a completed human-filled gold table or workbook.

The evaluator is intentionally separate from the production app. The main app is responsible for generating eval-ready runs. This repo is responsible for scoring those runs, surfacing diagnostics, and producing comparison tables that are useful for model, prompt, parser, and configuration benchmarking.

The evaluator must stay small, inspectable, reproducible, and loosely coupled to the main app. It must not depend on the main app frontend, backend runtime, or internal Python imports.

---

## Product summary

The product is a command-line tool that:

1. loads one run, many runs, or a directory of runs from the main app
2. loads a human-filled gold workbook or table
3. aligns run proposals to gold cells through a stable published artifact contract
4. scores proposal correctness and evidence quality separately
5. writes per-cell scored records, per-run summaries, and multi-run comparison tables
6. makes cross-run comparison easy for models, prompts, parser settings, and other run parameters

The evaluator is not a GUI product. Human-readable markdown output is optional. The primary outputs are structured files that can be inspected directly or loaded into notebooks, spreadsheets, or downstream analysis scripts.

---

## Goals

- Evaluate one or many app runs against a completed human-filled gold table.
- Keep the main headline score simple and comparable across runs.
- Separate answer correctness from evidence quality.
- Prefer deterministic scoring for structured fields.
- Allow constrained LLM judging for text fields.
- Treat retrieval-style signals as diagnostics, not as the main score.
- Produce one row per run comparison artifacts suitable for benchmarking.
- Preserve inspectability by writing explicit per-cell and per-run outputs.
- Keep the evaluator usable without the main app codebase at runtime.

## Non-goals

- No GUI requirement.
- No attempt to become a general benchmarking platform.
- No deep runtime imports from the main app.
- No heavyweight faithfulness or entailment framework in MVP.
- No attempt to prove that gold-empty cells are truly absent from the paper.
- No opaque single composite score that mixes correctness, evidence, and retrieval.

---

## Product principles

- Simplicity over benchmark-framework breadth.
- Inspectable artifacts over hidden scoring state.
- Stable contracts over convenient cross-repo imports.
- Reproducibility over judge flexibility.
- Comparative usefulness over exotic metrics.
- Gold-present scoring by default, because incomplete gold is common.
- Correctness and evidence quality must remain separate concepts.

---

## Primary user workflows

### Evaluate one run

An operator points the evaluator at one run directory plus a gold workbook or table and receives:

- per-cell scored records
- per-run summary metrics
- an optional human-readable summary

### Evaluate many runs

An operator points the evaluator at a runs root or an explicit list of run directories plus a gold workbook or table and receives:

- one scored output directory per run
- a combined comparison table with one row per run
- consistent run metadata columns for side-by-side analysis

### Compare runs across settings

An operator uses the comparison artifact to compare runs across:

- text model
- vision model if present
- parser identity or version
- prompt version or prompt hash
- schema hash or version
- config hash
- run mode and other available run parameters

---

## Scope

### In scope

- Loading run artifact bundles from the main app.
- Loading gold CSV or XLSX data.
- Scoring one run or many runs.
- Producing per-cell correctness and evidence outputs.
- Producing per-run summary JSON and CSV outputs.
- Producing multi-run comparison CSV, XLSX, and Parquet outputs.
- Optional constrained LLM judging for text fields.

### Out of scope for MVP

- Editing the gold table.
- Running extraction.
- Re-ranking retrieval.
- Re-parsing PDFs.
- Online dashboards.
- Human annotation tooling.
- Full evidence entailment or claim-verification systems.

---

## Input contract

The evaluator consumes:

- one run directory, or
- a directory containing multiple run directories, or
- an explicit list of run directories,

plus:

- one gold workbook or table,
- and optionally one schema file or schema metadata file when the run artifacts do not already contain enough field metadata.

### Gold input policy

The gold table may be incomplete.

- Gold-present cells are scored by default.
- Gold-empty cells are treated as unknown and unscored by default.
- Values proposed for gold-empty cells are reported as diagnostics only by default.

### Stable run artifact contract expected from the main app

The evaluator reads run artifacts as data files, not through Python imports.

The recommended eval-ready run bundle contains:

- `run.json`
- `config.snapshot.json`
- `inputs/input_summary.json`
- `proposals/proposals.jsonl`
- `summaries/run_summary.json`
- optional evidence artifacts if proposal records do not already include enough evidence data

### Required proposal-level fields for scoring

Each scored proposal record must expose, directly or via a stable linked artifact contract:

- `run_id`
- `row_id`
- `column_name`
- `cell_id`
- a published stable row or cell join contract that a separate repo can use without importing main-app code
- `pdf_id`
- `proposed_value`
- `state`
- `support`
- `field_type` when known
- `allowed_values` when relevant
- `numeric_value_form` when relevant
- evidence items, or a stable link to them

### Required reproducibility and comparison metadata

Each run should expose, when available:

- `run_id`
- `mode` or `run_mode`
- `provider_token`
- `provider_text_model_id` or equivalent text model id
- `provider_vision_model_id` or equivalent vision model id
- `parser_identity`
- `parser_version`
- `prompt_version` when available
- `prompt_hash` as the fallback prompt identity
- `schema_hash` or `schema_version`
- `config_hash`
- any other key run parameters safe to project into a flat comparison row

### Eval-mode provenance expected from the main app

For eval-mode runs, the stable contract should also carry:

- gold table source reference if available
- gold table content hash
- gold table snapshot path in the run bundle when available
- masked working table snapshot path
- masked working table content hash

The evaluator should consume these fields if present, but must not require the main app runtime in order to interpret them.

### Contract publication requirement

This repo must not reverse-engineer hidden ID logic from the main app.

For decoupled scoring, the main app must publish an explicit stable eval join contract that a separate repo can use directly.

The normative primary join fields are:

- `row_id` or an equivalent stable published row key
- `column_name`
- `cell_id`

`row_index` may be included for fallback diagnostics, debugging, or contract migration support, but it is not the normative primary scoring join path.

The evaluator should consume stable identifiers emitted by the main app rather than re-implementing hidden row-ID logic.

Acceptable published join contracts include:

- explicit `cell_id` plus `column_name` when needed for auditing context
- explicit `row_id` or stable row key plus `column_name`
- both `row_id` and `cell_id` on proposal records, with `column_name` preserved as the human-readable field key

If none of those are present, the evaluator may fail fast with a clear contract error rather than silently scoring against an inferred join.

### XLSX worksheet policy

For XLSX gold inputs, MVP scoring is single-sheet per evaluation invocation.

- The evaluator scores exactly one selected worksheet per invocation.
- Multi-sheet scoring is deferred.
- The CLI should support explicit worksheet selection when needed.
- If no worksheet is specified, the evaluator must use one clear default worksheet policy, documented as the first worksheet in workbook order.

MVP must avoid ambiguous multi-sheet behavior.

---

## Headline scoring policy

### Core rule

The evaluator scores only gold-present cells by default.

This means the headline score does not penalize a run for proposing a value where the gold cell is empty, because a gold-empty cell does not prove that the paper does not contain a valid answer.

### Correctness and evidence are separate

The evaluator reports answer correctness and evidence quality separately.

It must not collapse them into one opaque blended score.

### Field-type-aware scoring

The evaluator uses field-type-aware scoring:

- boolean: deterministic
- categorical: deterministic
- numeric: deterministic
- text: constrained LLM judge by default, with field-level deterministic override allowed for highly standardized text columns and deterministic text diagnostics allowed alongside it

### Retrieval-style metrics are diagnostic only

If retrieval-style metrics are included, they explain likely failure modes. They do not define the main score.

---

## Core metrics

### Headline correctness metrics

- `structured_accuracy`: accuracy over scored structured cells, meaning boolean, categorical, and numeric cells with gold-present values
- `boolean_accuracy`
- `categorical_accuracy`
- `numeric_accuracy`
- `text_accuracy`: accuracy over scored text cells under the configured text scoring policy, using judge-backed scoring by default and deterministic override where explicitly configured
- `proposal_coverage_on_gold_present`: fraction of gold-present cells for which the run produced a scoreable proposal record

### Evidence metrics

- `anchor_valid_rate`: fraction of scored cells whose selected proposal has at least one fully validated usable evidence anchor
- `correct_and_anchored_rate`: fraction of scored cells that are both correct and anchor-valid
- optional `structured_supported_by_evidence_rate`: a simple structured-field support proxy, not a heavyweight faithfulness score

### Diagnostic metrics

- `gold_present_cell_count`
- `gold_empty_cell_count`
- `filled_on_gold_empty_count`
- optional `gold_in_document_rate`
- optional later `gold_in_retrieved_context_rate`

Diagnostic metrics must be reported, but they must not be folded into the headline score.

---

## Field-type-aware scoring rules

### Boolean

Boolean scoring is deterministic after normalization.

Normalization should handle common equivalents such as:

- `true`, `yes`, `present`, `positive`, `1`
- `false`, `no`, `absent`, `negative`, `0`

After normalization, boolean scoring is exact-match binary correctness.

### Categorical

Categorical scoring is deterministic after normalization.

Normalization should support:

- case folding
- whitespace normalization
- punctuation simplification where appropriate
- `allowed_values`
- alias mapping when provided by schema metadata or evaluator config

The headline outcome is binary correct or incorrect against the normalized gold category.

### Numeric

Numeric scoring is deterministic.

Normalization should support:

- exact values
- ranges
- approximate values
- unit normalization when feasible and explicitly configured

Numeric tolerance policy for MVP is:

- global default tolerances exist for simple setup
- per-column tolerance settings may override the global defaults
- per-column settings take precedence when present
- numeric columns are not required to define their own tolerance settings

The MVP headline score is binary:

- correct within the configured tolerance or overlap rule
- otherwise incorrect

The evaluator may also report diagnostics such as absolute error, relative error, or interval overlap, but those are not part of the MVP headline score.

### Text

Text fields use a constrained LLM judge by default in MVP.

The judge should determine whether the proposal and the gold answer are materially equivalent for the field definition, not whether the strings are lexically identical.

Highly standardized text columns may opt into deterministic scoring instead when configured at the field or column level.

Deterministic text diagnostics may still be reported, for example normalized exact match or token-overlap metrics, but they are not the main correctness path for free-text fields.

---

## LLM judge policy

The evaluator uses an LLM judge primarily for text fields in MVP, with deterministic per-column override allowed for highly standardized text fields.

Judge guardrails for MVP:

- fixed judge model per evaluation run
- temperature `0`
- strict structured output
- bounded prompt inputs
- no long hidden reasoning stored in core artifacts
- judge metadata persisted in outputs
- judge use limited to text fields by default, not the entire scoring stack
- deterministic text override must remain field-scoped or column-scoped, not global by accident

Each judge-scored record should persist enough metadata for reproducibility, including at minimum:

- judge model id
- judge prompt version or hash
- judge temperature
- judge decision label
- any normalized intermediate values the evaluator uses as part of the final score

---

## Evidence policy

Evidence quality is evaluated separately from answer correctness.

### MVP evidence contract

The minimal usable evidence anchor contract is:

- `page`
- `quote_text`

When available, the evaluator may use additional fields, but MVP evidence scoring should not depend on a heavyweight entailment system.

### MVP evidence checks

At minimum, the evaluator should validate whether anchored evidence exists and is usable.

`anchor_valid` in MVP means:

- a page reference is present and valid when page bounds are known
- `quote_text` is non-empty
- when persisted parsed page text or equivalent text evidence is available, the quote is locatable on the cited page or in the cited text source
- the evidence item is attached to the scored proposal or can be resolved through a stable linked artifact

If quote text is present but cannot be validated against persisted text evidence when such text is available, the evidence should not count as fully `anchor_valid`.

The evaluator may record a secondary diagnostic state such as `evidence_present_but_unvalidated` to distinguish:

- missing evidence
- present but unvalidated evidence
- fully anchor-valid evidence

The evaluator may later add a simple structured-field support proxy, but that remains secondary to the anchor-valid check.

---

## Output artifacts

The evaluator writes explicit outputs.

### Per-cell outputs

Per-cell scored records should include at minimum:

- run id
- row locator
- column name
- cell id when available
- gold value
- proposed value
- field type
- correctness outcome
- evidence outcome
- judge outcome when used
- diagnostic flags

These records should be written in an inspectable machine-readable format such as JSONL or CSV, and may be written in both.

Per-cell scored records should also include the resolved join fields used for scoring, including stable `row_id` and `cell_id` when present, with `row_index` treated only as optional fallback or debug context.

### Per-run outputs

For each run, the evaluator should write:

- `run_summary.json`
- `run_summary.csv`

### Batch outputs

For multi-run evaluation, the evaluator should write a comparison table with one row per run in:

- CSV
- XLSX
- Parquet

The batch summary row should include run metadata columns such as:

- `run_id`
- `run_mode`
- `model_id` or text model id
- `vision_model_id` if present
- `parser_identity` or parser version
- `prompt_version` or prompt hash
- `schema_hash` or schema version
- `config_hash`
- key run parameters when available
- headline correctness metrics
- evidence metrics
- diagnostic counts

Human-readable markdown summary is optional, not required for MVP.

---

## CLI-first product surface

The evaluator is CLI-first.

The MVP should support:

- scoring one run
- scoring many runs under a runs root
- scoring an explicit list of runs
- emitting outputs to a chosen output directory

It should not require a server or GUI.

---

## Relationship to the main app

The main app is responsible for:

- generating eval-ready run bundles
- masking target cells in eval mode
- persisting stable ids and run metadata
- persisting proposal and evidence artifacts

This eval repo is responsible for:

- loading those artifacts as data
- scoring against the gold table
- producing per-cell and per-run outputs
- producing cross-run comparison tables

This split keeps the production app lightweight and keeps benchmarking optional.

---

## Acceptance criteria for MVP

The MVP is acceptable when:

- one run can be scored from the CLI without importing the main app codebase
- many runs can be scored in one batch from a runs root or explicit list
- gold XLSX inputs are evaluated one worksheet at a time with explicit or clearly defaulted worksheet selection
- only gold-present cells are included in headline scoring by default
- correctness and evidence metrics are reported separately
- boolean, categorical, and numeric scoring are deterministic
- numeric tolerance resolution supports global defaults with per-column overrides
- text scoring uses a constrained reproducible LLM judge by default, with deterministic field-level override available for standardized text columns
- anchor-valid scoring distinguishes fully validated anchors from evidence that is merely present but not validated when persisted text is available
- per-cell scored outputs and per-run summaries are inspectable on disk
- batch comparison outputs contain one row per run with useful metadata for benchmarking
- contract failures are explicit rather than silently guessed
