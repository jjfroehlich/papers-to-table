# Extract Structured Info from Papers Eval - research.md

## Status

Initial rationale and tradeoff record for the evaluation repo MVP.

## Purpose

This document explains why the evaluator is shaped as a small separate CLI tool, why the metric stack is intentionally simple, and which design choices are meant to stay explicit before implementation begins.

---

## Why correctness and evidence quality are separated

Correctness and evidence quality answer different questions.

- Correctness asks whether the proposed value matches the gold answer.
- Evidence quality asks whether the run produced usable support for that answer.

Collapsing those into one number creates ambiguity:

- a correct answer with poor evidence looks similar to a wrong answer with good evidence
- a run can appear better or worse depending on how the blended score is weighted
- debugging becomes harder because the score does not explain whether the failure is extraction, normalization, or evidence quality

Separate reporting keeps the score interpretable and more actionable for model and prompt comparisons.

---

## Why only gold-present cells are scored by default

Completed human tables are often incomplete.

A gold-empty cell usually means one of the following:

- the curator did not extract that field yet
- the curator was unsure
- the paper was not fully reviewed for that field
- the value truly is absent

Those cases are not equivalent.

If the evaluator penalizes proposals on gold-empty cells in the headline score, it turns incomplete annotation into a false negative label. That would distort model comparisons and make the benchmark less trustworthy.

The cleaner default is:

- score gold-present cells in the headline metrics
- report gold-empty proposals as diagnostics

This keeps the main score conservative and more reproducible across partially complete gold tables.

---

## Why retrieval metrics are diagnostic rather than headline

Retrieval metrics explain why extraction failed, but they are not the same as answer quality.

Examples:

- a run may retrieve weak passages but still produce the right structured answer
- a run may retrieve the exact passage and still produce the wrong answer
- a run may fail because the gold answer was never parsed into the document text, not because the comparator was wrong

Retrieval diagnostics are useful for debugging parser, chunking, and query settings. They are weak headline metrics for real operator value.

That is why metrics such as `gold_in_document_rate` and later `gold_in_retrieved_context_rate` belong in the diagnostic layer.

---

## Why the evaluator is a separate repository

The production app and the evaluator have different jobs.

The production app should stay focused on:

- loading inputs
- parsing papers
- matching rows
- generating proposals
- supporting review and export

The evaluator should stay focused on:

- scoring
- comparison
- benchmark outputs

Keeping evaluation separate has several benefits:

- the production app stays lighter and simpler
- benchmarking remains optional
- evaluation logic can evolve without pulling benchmark dependencies into runtime extraction
- run bundles become a stable interface between production and benchmarking

This separation also forces the artifact contract to be explicit, which improves reproducibility.

---

## Why structured scoring stays deterministic in MVP

Boolean, categorical, and numeric fields are exactly where deterministic scoring works well and is easiest to trust.

Deterministic structured scoring provides:

- inspectable normalization rules
- consistent cross-run comparisons
- lower cost
- easier debugging
- less judge drift

Using an LLM to score obviously structured fields would add variability without a clear benefit. The evaluator should reserve LLM judgment for free-text equivalence where deterministic exact match is too brittle.

---

## Why an LLM judge is acceptable for text fields when constrained

Free-text fields often contain semantically equivalent but lexically different answers.

Examples:

- abbreviation versus expanded form
- paraphrase with the same biological meaning
- short descriptive variants that are not string-identical

Pure lexical overlap is often too brittle for those fields.

A constrained LLM judge is acceptable if the evaluator keeps the judge narrow and reproducible:

- fixed model
- temperature 0
- strict structured output
- short bounded prompts
- persisted metadata
- no hidden reasoning in core artifacts

The judge should be a scoped tool for text equivalence, not a replacement for the rest of the metric system.

---

## Why LM Studio is the default local-first judge path

This repo is explicitly local-first by default, so the default judge path should match that operating model.

LM Studio is a practical MVP default because it:

- provides a local operator-controlled runtime
- exposes an OpenAI-compatible API that keeps integration narrow
- fits the repo goal of inspectable, reproducible, low-coupling evaluation

That makes it a better default than starting with a cloud-only judge dependency for MVP, while still leaving room for future provider options if the evaluator later needs them.

---

## Why `qwen/qwen3.5-35b-a3b` is the default judge model for now

MVP needs one concrete default judge model so the repo, docs, and operator workflow are all aligned.

Choosing a fixed default model for now:

- reduces ambiguity in local setup
- makes the default path easier to document and support
- improves reproducibility across evaluations compared with an unspecified local model choice

This is a default for MVP, not a statement that other models will never be supported.

---

## Why the evaluator must persist the resolved runtime model identity

Configured model strings and runtime-served model identifiers are not always the same thing.

An operator may configure a convenient alias, while LM Studio may report a different concrete served model id at runtime. If the evaluator stores only the configured string, later comparison and audit trails can become misleading.

Persisting both the configured judge model and the resolved runtime model keeps the provenance honest and makes judge-backed results easier to reproduce and debug.

---

## Why evidence scoring stays lightweight in MVP

Faithfulness and support scoring can become an entire research program.

That is not the goal of this repo.

The MVP only needs to answer a practical question:

- did the run produce usable anchored evidence for this proposal?

That leads to a lightweight first step:

- validate whether a page and quote anchor exist and are usable

This is enough to distinguish:

- unsupported guesses
- minimally inspectable proposals
- correct answers that are still hard to trust in review

More advanced support analysis can come later if real usage shows it is needed.

---

## Why the main score stays simple

The main comparison artifact should be usable by a human looking across many runs.

If the headline score mixes:

- structured fields
- text fields
- retrieval diagnostics
- evidence quality
- penalties on gold-empty proposals

then the result becomes hard to interpret.

The MVP instead favors a small set of explicit columns:

- structured accuracy
- per-type structured accuracies
- text judge accuracy
- coverage on gold-present cells
- anchor-valid rate
- correct-and-anchored rate

This is simpler to understand and more honest about what each metric means.

---

## Why inspectable filesystem outputs are the right MVP surface

The eval tool is mainly for benchmarking and debugging.

Those workflows benefit from outputs that are:

- easy to diff
- easy to inspect in a spreadsheet or notebook
- easy to archive with run artifacts
- easy to regenerate

That is why the MVP should write explicit per-cell and per-run files rather than storing evaluation only in a database or dashboard.

---

## Why strong README and operator docs matter in this repo

This repo is a CLI-first evaluation tool that sits beside, not inside, the main app.

That means operators need docs that clearly explain:

- what the repo expects as input from the main app
- how to run one evaluation or many evaluations
- how to interpret headline versus diagnostic metrics
- how the LM Studio judge path is configured
- what limitations still exist

If those expectations are not documented clearly, the repo becomes harder to trust and harder to operate, even if the scoring logic itself is sound.

---

## Why explicit stable join keys are better than row-index dependence

The largest architectural risk is hidden coupling through row or cell identifiers.

The main app currently computes internal stable IDs. A separate repo should not be forced to copy that logic privately. If the evaluator must recreate row or cell IDs from internal rules, the split between repos is only superficial.

`row_index` is a weak primary contract because it is position-dependent and easier to break across workbook reshaping, filtering, or export transformations. It is useful as fallback context, but it should not be the main scoring join.

The cleaner solution is for the main app to publish explicit stable identifiers for evaluation, with `row_id`, `column_name`, and `cell_id` as the primary join contract.

That keeps the repo boundary real instead of forcing the evaluator to re-implement main-app internals.

---

## Why single-sheet XLSX MVP is the right scope

Multi-sheet workbook behavior creates avoidable ambiguity early:

- which worksheet is authoritative
- whether all sheets share one schema
- how run metadata should map to sheet identity

Scoring exactly one worksheet per invocation keeps the CLI explicit, keeps output rows unambiguous, and avoids accidental multi-sheet behavior before there is a real use case for it.

The evaluator can still support XLSX cleanly in MVP by requiring one selected sheet or one clear default worksheet policy.

---

## Why per-column numeric tolerance with global defaults is the right balance

Numeric fields vary in how strict they should be.

- some values should match exactly
- some values should tolerate small rounding differences
- some ranges should be compared by interval overlap

One global tolerance is simple but too blunt. Requiring every numeric column to define its own tolerance is too heavy.

Global defaults with per-column overrides gives the right MVP balance:

- simple out of the box
- customizable where field semantics require it
- still easy to explain in the headline metric because correctness remains binary within the resolved tolerance rule

---

## Why judge-by-default for text fields fits this product

Free-text fields are exactly where lexical mismatch and semantic equivalence diverge most often.

If MVP made deterministic matching the default for text, many materially correct answers would be scored as wrong for superficial wording reasons. That would weaken the evaluator's comparative value.

Judge-by-default for text fields is the better baseline, provided the judge stays constrained and reproducible.

At the same time, some text columns are effectively standardized labels. Those should be allowed to opt into deterministic scoring at the field or column level rather than forcing every text field through the judge.

---

## Why quote locatability should influence anchor validity

If a run bundle includes persisted page text or equivalent text evidence, the evaluator can check more than mere evidence presence.

A stored quote string that cannot be located in the persisted text should not count as fully anchor-valid, because the anchor is not actually validated against the run artifact.

This does not require a heavy faithfulness framework. It is still a simple inspectable check:

- evidence present
- evidence locatable
- therefore anchor-valid

That distinction improves trust in evidence metrics while keeping the MVP lightweight.

This should remain an explicit contract requirement before coding starts.

---

## Remaining contract risk

The main open dependency is no longer the policy choice. It is whether the main app will actually publish the stable join identifiers the evaluator now expects.

If eval-ready runs do not carry explicit `row_id`, `column_name`, and `cell_id` contract fields, implementation should fail fast rather than backsliding into hidden coupling.
