# Archived Eval Research

Archive status: historical, superseded as normative current source, still informative, partially migrated into [../../plan.md](../../plan.md) and selected current eval normative files.

Original source path: `tools/eval/specs/research.md`

This file preserves the pre-unification eval research notes in archival form. The legacy content below is preserved verbatim from git history except for this archive header.

---

# Extract Structured Info from Papers Eval Research Notes

## Purpose

This document records rationale, tradeoffs, open questions, and deferred items for `extract-structured-info-from-papers-eval`.

## Why the Evaluator Is a Separate Repository

The production app and the evaluator serve different jobs.

Keeping evaluation separate:

- avoids pulling benchmarking dependencies into extraction runtime
- forces the run bundle to be an explicit artifact contract
- makes scoring and comparison easier to inspect independently of extraction logic
- keeps benchmarking optional for operators who only need the main app

## Why Gold-Present Cells Are the Default Headline Scope

A gold-empty cell is not a reliable negative label.

Treating gold-empty cells as unscored by default keeps the headline score conservative when human-filled gold tables are incomplete. Reporting proposals on gold-empty cells as diagnostics preserves useful information without converting annotation incompleteness into false negatives.

## Why Correctness and Evidence Stay Separate

Correctness and evidence quality answer different questions.

Separate metrics make it easier to distinguish:

- wrong answers
- correct answers with weak support
- answers with inspectable support that still do not match gold

This separation keeps comparison outputs easier to interpret and debug.

## Why Stable Published Join Keys Matter

The evaluator is only genuinely decoupled if it can score from published identifiers.

Reconstructing row or cell identities from hidden main-app logic would create implicit coupling and fragile cross-repo behavior. Published `row_id`, `column_name`, and `cell_id` are the cleanest contract because they survive repo boundaries and make join failures explicit.

## Why Single-Sheet XLSX Scoring Is the Right Current Scope

Multi-sheet scoring introduces ambiguity around worksheet authority, schema interpretation, and output semantics.

Scoring one worksheet per invocation keeps the CLI explicit and keeps output rows unambiguous while still supporting XLSX as an operator-facing format.

## Why Structured Scoring Stays Deterministic

Boolean, categorical, and numeric fields are the easiest places to keep scoring inspectable and reproducible.

Deterministic structured scoring:

- is cheaper than judge-backed scoring
- is easier to test
- is easier to audit from artifacts
- avoids needless judge drift for fields with stable normalization rules

## Why Text Fields Default to Judge-Backed Scoring

Free-text fields often have semantically equivalent but lexically different answers.

Judge-backed scoring is the better default for text fields so long as the judge remains narrow, reproducible, and fully instrumented. Deterministic override still matters for standardized text columns that behave more like labels than free text.

## Why LM Studio Is the Default Judge Path

This repo is local-first by default.

LM Studio fits that constraint because it provides a local operator-controlled runtime with a narrow OpenAI-compatible API surface. That keeps judge integration simple without making cloud infrastructure the default dependency.

## Why the Resolved Runtime Model Identity Must Be Persisted

Configured model strings and runtime-served model ids are not always the same.

Persisting both values makes judge-backed outputs more reproducible and makes audits honest when an alias resolves to a different runtime model.

## Why Evidence Validation Stays Lightweight

The evaluator needs inspectable evidence checks, not a full faithfulness framework.

The current lightweight anchor validation captures whether a proposal has usable page-and-quote support and whether that support can be validated against persisted text when available. That is enough to distinguish unsupported guesses from minimally inspectable answers without turning the repo into an entailment system.

## Why Filesystem Artifacts Remain the Primary Surface

This repo is used for benchmarking, comparison, and debugging.

Explicit JSONL, CSV, XLSX, and Parquet outputs are easy to diff, archive, inspect in notebooks, and compare across runs. That is a better fit than hiding evaluation state behind a service or database.

## Open Questions

Open questions that remain product-relevant are:

- whether a narrow structured-field support proxy is worth adding beyond anchor validation
- whether future judge-provider expansion is valuable enough to justify a broader provider abstraction
- whether retrieval-style diagnostics such as `gold_in_document_rate` should be added once real operator demand exists

## Deferred Items

Deferred items currently outside the implemented surface are:

- structured-field support proxy metrics
- multi-sheet XLSX scoring in one invocation
- heavier evidence entailment or faithfulness checks
- broader benchmarking-platform features beyond the current CLI and artifact set
