# Extract Structured Info from Papers Eval Technical Plan

## Purpose

This document records the stable technical architecture and implementation direction for `extract-structured-info-from-papers-eval`.

It describes how the repo should stay small, explicit, and decoupled from the main app while supporting truthful run-bundle evaluation.

## Architecture Constraints

The evaluator should:

- remain a separate runtime from the main app
- read run bundles as files rather than importing main-app Python code
- keep deterministic structured scoring isolated from judge-backed text scoring
- write inspectable filesystem artifacts as the primary contract
- keep comparison rows flat and analysis-friendly

## Canonical Module Layout

The current architecture centers on these modules:

- `cli.py` for command parsing and command dispatch
- `contracts.py` for evaluator-owned data classes and shared constants
- `run_loader.py` for run discovery, run metadata loading, proposal loading, and contract validation
- `gold_loader.py` for CSV and XLSX gold loading
- `schema_loader.py` for optional schema metadata loading
- `normalize.py` for normalization helpers
- `compare_structured.py` for deterministic structured comparators
- `judge.py` for bounded text-judge request construction and LM Studio integration
- `evidence.py` for lightweight anchor validation
- `score.py` for per-cell scoring orchestration
- `aggregate.py` for per-run summaries and comparison-row generation
- `writers.py` for JSONL, CSV, XLSX, and Parquet artifact writing

## CLI Direction

The CLI surface has two commands:

- `evaluate` for scoring one or more runs against a gold input
- `compare` for rebuilding comparison artifacts from per-run summaries

`evaluate` should continue to own:

- run discovery from repeated `--run` values or `--runs-root`
- gold loading from CSV or XLSX
- optional schema loading
- optional JSON stdout completion payloads
- writing per-run artifacts and comparison artifacts in one pass

`compare` should remain a writer-oriented command that rebuilds comparison artifacts from stored `run_summary.json` files without rescoring proposals.

## Data Boundaries

The evaluator owns its internal normalized representations.

Key boundaries are:

- run metadata is normalized into `RunMetadata`
- proposal records are normalized into `ProposalRecord`
- gold cells are normalized into `GoldCell`
- scored outputs are normalized into `ScoredCell`
- per-run aggregates are normalized into `RunSummary`

App-specific payload shapes should stay confined to loader logic.

## Loading and Contract Validation Direction

Run loading should continue to validate contracts early.

Required checks belong in the loader layer:

- required run files exist
- proposal JSONL is parseable
- stable join fields are present on every proposal
- eval-mode provenance fields are present when run mode is eval
- referenced provenance snapshot paths exist when required

Gold loading should continue to:

- support CSV and XLSX
- support wide and long gold layouts
- enforce unique `row_id + column_name` pairs
- treat XLSX as single-sheet per invocation

## Scoring Pipeline Direction

The scoring pipeline should remain:

1. load and normalize run metadata, proposals, gold cells, and optional schema
2. join gold cells to proposals by published stable identifiers
3. classify join outcomes before scoring
4. resolve field type and scoring policy per matched cell
5. score structured fields deterministically
6. score text fields through deterministic override or bounded judge logic
7. evaluate evidence separately from correctness
8. write scored-cell records for both scored cells and diagnostics
9. aggregate run-level metrics from scored-cell outputs

## Field Resolution Direction

Field resolution should continue to use this precedence:

1. proposal metadata
2. schema metadata
3. evaluator inference from values and allowed values

Text scoring policy should continue to default to judge-backed scoring for resolved text fields unless a deterministic override is explicitly configured.

## Evidence Direction

Evidence validation should stay lightweight and inspectable.

The current direction is:

- validate page and quote anchors
- use persisted page text when available to check quote locatability
- distinguish `anchor_valid` from `evidence_present_but_unvalidated`
- keep evidence metrics separate from correctness metrics

Any richer support-proxy or faithfulness logic should remain a narrow extension instead of reshaping the core scoring pipeline.

## Output Architecture

Per-run output directories should continue to contain scored-cell artifacts, run summaries, and judge records when present.

Comparison outputs should remain flat one-row-per-run artifacts rendered from the same normalized summary rows into:

- CSV
- XLSX
- Parquet

File artifacts remain the source of truth even when the CLI emits JSON completion payloads on stdout.

## Judge Integration Direction

The judge path should remain narrow and reproducible.

The current technical direction is:

- default provider: LM Studio through its OpenAI-compatible local API
- default configured model: `qwen/qwen3.5-35b-a3b`
- fixed temperature of `0`
- bounded response-mode fallback from `json_schema` to `json_object` to prompt-only JSON mode with app-side parsing
- persisted provider, configured model id, resolved runtime model id, prompt metadata, and input hash

Judge integration should stay limited to text scoring by default.

## Verification Direction

Verification should continue to rely on:

- unit coverage for normalization and comparators
- contract tests for loaders and failure modes
- evidence tests for anchor-valid versus unvalidated behavior
- mocked judge tests for text-scoring integration
- end-to-end CLI tests for per-run and batch outputs

When platform-specific resource handling matters, tests should close temporary workbook handles explicitly so Windows verification remains reliable.

## Deliberately Excluded Architecture

The evaluator should not grow these as default architecture:

- runtime imports from the main app
- plugin systems for simple scoring paths
- a database-backed persistence layer
- a GUI or server process
- a general benchmarking framework with broad provider abstraction as the starting point
