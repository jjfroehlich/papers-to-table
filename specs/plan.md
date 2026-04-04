# Extract Structured Info from Papers Eval - plan.md

## Status

Initial technical plan for a small, explicit, CLI-first evaluation tool.

## Purpose

This document translates `spec.md` into a concrete implementation direction for the evaluation repo.

The goal is not to build a large benchmarking framework. The goal is to implement the smallest robust evaluator that can compare one or many main-app runs against a human-filled gold table with outputs that are easy to inspect and trust.

---

## Technical principles

- Keep the repo separate from the main app at runtime.
- Read JSON and workbook artifacts directly.
- Prefer a narrow published artifact contract over implicit coupling.
- Keep structured scoring deterministic.
- Keep text judging constrained and reproducible.
- Keep evidence checks lightweight in MVP.
- Make CSV the canonical inspectable batch artifact, with XLSX and Parquet emitted from the same normalized rows.

---

## Proposed CLI surface

The MVP should expose two top-level commands.

### `evaluate`

Scores one or many runs against a gold table and writes per-run plus batch outputs.

Representative forms:

```bash
paper-eval evaluate --run path/to/run --gold gold.xlsx --out out/
paper-eval evaluate --run path/to/run --gold gold.xlsx --gold-sheet Sheet1 --out out/
paper-eval evaluate --runs-root path/to/runs --gold gold.xlsx --out out/
paper-eval evaluate --run path/a --run path/b --gold gold.xlsx --out out/
```

### `compare`

Rebuilds or filters comparison artifacts from already-produced per-run summaries without rescoring everything.

Representative form:

```bash
paper-eval compare --summaries out/per-run --out out/compare
```

This split keeps normal scoring simple while allowing cheap re-rendering of comparison tables.

---

## Proposed repo architecture

The repo should remain small and explicit. A reasonable MVP module layout is:

- `cli.py`: argument parsing and command dispatch
- `contracts.py`: artifact contract validation and typed records
- `run_loader.py`: load run metadata, proposals, and evidence from run bundles
- `gold_loader.py`: load CSV or XLSX gold data into a normalized table view
- `schema_loader.py`: optional schema metadata loading
- `normalize.py`: field-type-aware normalization helpers
- `compare_structured.py`: deterministic boolean, categorical, and numeric comparators
- `judge.py`: constrained text-judge adapter and prompt wiring
- `evidence.py`: anchor validation and optional support proxy checks
- `score.py`: per-cell scoring orchestration
- `aggregate.py`: per-run summaries and batch comparison rows
- `writers.py`: JSON, CSV, XLSX, and Parquet outputs

The implementation should avoid generic plugin systems or cross-cutting abstraction layers that exceed the MVP.

---

## Data flow

### 1. Resolve inputs

The CLI resolves:

- one run directory, many run directories, or a runs root
- one gold workbook or table
- for XLSX gold input, exactly one worksheet selection per invocation, either explicit or defaulted to the first worksheet
- optional schema metadata
- output directory
- judge settings when text judging is active

For MVP, the default local-first judge settings should target LM Studio through its OpenAI-compatible local API, with `qwen/qwen3.5-35b-a3b` as the default configured judge model.

### 2. Load and validate run artifacts

For each run:

- read the required artifact files
- validate the presence of proposal and metadata fields needed for scoring
- fail fast on missing contract-critical fields
- persist contract warnings for optional but useful metadata that is absent

### 3. Load and normalize the gold table

The gold loader should support:

- CSV
- XLSX

For XLSX, MVP should support a single selected worksheet, defaulting to the first worksheet unless the CLI specifies another sheet.

Multi-sheet evaluation is explicitly deferred. One invocation scores one worksheet only.

The loader should preserve raw cell values and build a normalized view for scoring.

### 4. Align proposals to gold cells

The scorer should align proposal records to gold cells through the published stable identifier contract.

The normative primary join path is:

- `row_id` or equivalent stable published row key
- `column_name`
- `cell_id`

`cell_id` should normally be the most specific published identifier for auditing and conflict detection. `row_id + column_name` is the expected primary scoring join when both are present and consistent.

`row_index` may be consumed only as fallback or debug context during contract migration. It is not the normative primary scoring join path.

The evaluator must not depend on a private copy of the main app's ID generation functions.

### 5. Score each cell

For each gold-present cell in scope:

- identify the relevant proposal record for that run and cell
- determine field type from proposal metadata, schema metadata, or evaluator fallback rules
- normalize gold and proposal values
- apply the correct comparator
- resolve numeric tolerance from per-column settings first, then global defaults
- resolve text scoring strategy from per-column policy, defaulting to judge-backed scoring for text fields
- separately score evidence quality
- write a per-cell scored record

Gold-empty cells should be recorded as diagnostics only unless the operator explicitly enables an alternate policy later.

### 6. Aggregate per-run outputs

For each run, compute:

- headline correctness metrics
- evidence metrics
- diagnostic counts
- run metadata projection for comparison tables

Write one machine-readable summary row per run.

### 7. Aggregate batch comparison outputs

Combine run summary rows into:

- canonical comparison CSV
- comparison XLSX
- comparison Parquet

The batch row schema should be flat and analysis-friendly.

---

## Main-app artifact contract handling

The evaluator should define a versioned adapter for the main app's run bundle contract.

### Contract strategy

- Treat the run bundle as versioned data, not as an importable API.
- Validate required fields eagerly.
- Isolate app-specific field names inside the loader layer.
- Normalize loaded records into evaluator-owned internal data classes.

### Files to read first

The loader should first attempt to read:

- `run.json`
- `config.snapshot.json`
- `inputs/input_summary.json`
- `proposals/proposals.jsonl`
- `summaries/run_summary.json`

If evidence is not fully embedded in the proposal record, the loader should also resolve evidence from the run bundle.

### Recommended normalized internal run metadata

The loader should normalize run metadata into one flat object containing at minimum:

- `run_id`
- `run_mode`
- `provider_token`
- `text_model_id`
- `vision_model_id`
- `parser_identity`
- `parser_version`
- `prompt_version`
- `prompt_hash`
- `schema_hash`
- `schema_version`
- `config_hash`
- eval-mode gold and masked table provenance when present

### Required contract gap to close explicitly

The current main app computes stable IDs internally. The eval repo must not replicate hidden ID logic.

Before implementation, the published run artifact contract should guarantee explicit stable scoring identifiers that are safe for a separate repo.

The preferred MVP requirement is to persist:

- `row_id` or equivalent stable row key
- `column_name`
- `cell_id`

`row_index` may be retained as fallback or debug context, but it should not be the primary eval contract.

---

## Gold table handling

### MVP assumptions

- The gold file is either CSV or XLSX.
- Exactly one worksheet is scored per eval invocation.
- Column names in the gold file correspond to schema or proposal column names.
- Empty gold cells are unscored by default.

For XLSX:

- the CLI may accept an explicit worksheet selector such as `--gold-sheet`
- if omitted, the evaluator uses the first worksheet in workbook order
- ambiguous multi-sheet scoring behavior is out of scope for MVP

### Gold-present detection

The gold loader should treat a cell as gold-present when, after normalization for emptiness, the cell contains a real value.

Examples of empty forms to normalize consistently:

- empty string
- whitespace-only string
- null or missing value
- spreadsheet blank cell

The loader should not treat placeholder strings such as `NA` or `not reported` as empty unless the operator explicitly configures that behavior.

---

## Normalization and comparators

### Boolean

Implement a deterministic boolean normalizer with a bounded synonym map.

### Categorical

Implement deterministic categorical normalization with:

- case folding
- whitespace normalization
- alias mapping
- optional schema-provided `allowed_values`

### Numeric

Implement deterministic numeric normalization into a common internal representation:

- exact scalar
- interval
- approximate scalar with tolerance policy

Numeric tolerance resolution should be:

- per-column override when configured
- otherwise global numeric defaults

The comparator should not require every numeric column to define its own tolerance.

The comparator should return:

- headline binary correctness
- optional diagnostics such as normalized forms and error magnitude

### Text

Text scoring should support two layers:

1. optional deterministic diagnostics, such as normalized exact match
2. constrained LLM judgment as the default equivalence decision for text fields

The scoring-policy resolver should also support a per-column deterministic override for highly standardized text fields.

Boolean, categorical, and numeric fields should continue to use deterministic scoring by default. The judge path should remain primarily for text fields and any explicitly configured residual cases.

---

## LLM judge implementation policy

The judge layer should be intentionally narrow.

### Default provider direction

The default local-first judge path for MVP should be LM Studio using its OpenAI-compatible local API.

- default provider: LM Studio
- default configured judge model: `qwen/qwen3.5-35b-a3b`
- future providers may be added later, but LM Studio is the default path that README and operator docs should explain first
- the evaluator should not require cloud judge infrastructure in the default setup

### Judge inputs

The judge prompt should include only the minimum needed context:

- field name
- field description if available
- gold value
- proposed value
- optional short evidence excerpt when that helps disambiguate text equivalence

### Judge outputs

The judge should return strict structured output via an explicit JSON schema, for example:

- decision: correct or incorrect or unclear
- short public rationale label
- optional normalization hint for logging

Outputs should stay bounded. The evaluator should not persist long free-form reasoning in its core artifacts.

### Judge reproducibility

Persist:

- judge provider
- configured judge model id
- resolved runtime-served judge model id
- temperature
- prompt version or hash
- verdict
- input hash
- timestamp
- request count and token usage if available

The evaluator should avoid storing long hidden reasoning or raw chain-of-thought text.

The resolved runtime model identity must be persisted even when the operator configured a model string up front, because LM Studio or another provider may serve a different runtime identifier than the configured alias.

### Bounded use

The judge should run only for text fields by default.

Highly standardized text columns may opt out of judge use through an explicit field or column scoring policy.

If a later option allows judge use for other ambiguous fields, that option should remain opt-in and separately labeled.

---

## Evidence validation plan

Evidence scoring in MVP should stay lightweight.

### Anchor-valid check

For the selected proposal, determine whether at least one evidence item is usable.

Anchor-valid means:

- page reference present
- quote text present
- page number valid when page metadata is known

When persisted parsed page text or equivalent text evidence is available, anchor validation should also require quote locatability on the cited page or source text.

If quote text exists but cannot be validated against persisted text evidence when such evidence is available, the evaluator should mark the evidence as present but unvalidated rather than fully anchor-valid.

This keeps the metric simple while preventing stored quote strings from counting as fully valid anchors when the run bundle provides enough information to check them.

### Structured support proxy

After the anchor-valid check exists, the evaluator may add a simple structured support proxy for structured fields, such as whether the normalized gold or proposal value appears in the anchored quote.

This proxy is optional and secondary.

---

## Output layout

The evaluator should write outputs under one operator-selected directory.

Suggested layout:

```text
{out}/
  per-run/
    {run_id}/
      scored_cells.jsonl
      scored_cells.csv
      run_summary.json
      run_summary.csv
      judge_records.jsonl          # only when judge used
  compare/
    runs_comparison.csv
    runs_comparison.xlsx
    runs_comparison.parquet
```

CSV is the canonical inspectable output. XLSX and Parquet are alternate renderings of the same normalized comparison rows.

---

## README and operator-doc deliverables

README and operator-facing docs should be treated as implementation deliverables, not polish.

They should clearly cover:

- what the eval repo does
- which input artifacts it expects from the main app
- one-run evaluation
- many-run evaluation
- headline metrics versus diagnostic metrics
- LM Studio judge configuration through the OpenAI-compatible local API
- the default configured judge model `qwen/qwen3.5-35b-a3b`
- current limitations and local-first assumptions

Batch completion should require docs clear enough that an operator can run the tool and interpret the main outputs without reading source code.

---

## Testing strategy

The repo should bias toward deterministic tests.

### Unit tests

- normalization
- boolean comparator
- categorical comparator
- numeric comparator
- anchor validation
- aggregation

### Contract tests

- run bundle validation
- missing required artifact fields
- explicit contract failure messages
- eval-mode provenance loading

### Judge tests

- structured parsing of judge output
- prompt construction bounds
- deterministic mock-based scoring behavior

### End-to-end tests

- one run scoring flow
- multi-run scoring flow
- batch comparison artifact generation

Judge-backed e2e tests should default to mocked judge responses. A live-judge smoke test can be optional and clearly separated.

---

## Implementation philosophy

Implementation should proceed batch by batch.

The first usable slice should score structured fields on one run with explicit outputs and no live judge dependency, while still defining the text-policy resolution surface early so later judge integration does not force contract drift. After that, add multi-run comparison and evidence validation, then text judging, then polish and docs.

This ordering keeps the evaluator useful early while preserving a narrow contract surface.
