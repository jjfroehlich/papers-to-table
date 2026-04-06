# Extract Structured Info from Papers Optimizer - plan.md

## Status

Initial technical plan for a small, explicit, eval-driven optimizer.

## Purpose

This document translates `spec.md` into a concrete implementation direction for the optimizer repo.

The goal is not to build a general agent framework or a self-improving codebase. The goal is to implement the smallest robust orchestration tool that can compare bounded prompt, model, and config variants against a fixed benchmark and promote improvements under a gated rule.

The plan supports two explicit study modes under one app contract:

- `compare`: fixed explicit candidate-set comparison
- `optimize`: iterative incumbent/challenger promotion loop

---

## Technical principles

- Keep the repo CLI-first.
- Keep runtime responsibilities orchestration-only.
- Treat the main app as the execution engine and the eval app as the scoring engine.
- Prefer stable subprocess or CLI integration over deep cross-repo runtime imports.
- Keep the search surface explicit, bounded, and versioned on disk.
- Keep candidate bundles immutable and auditable.
- Keep results inspectable through filesystem artifacts.
- Keep the default behavior deterministic-first.
- Keep holdout validation separate from the main search loop.
- Share one core execution-and-scoring pipeline across both study modes.
- Keep mode differences isolated to loop control and summaries.

---

## Proposed CLI surface

The MVP should expose four top-level commands.

### `optimize`

Runs either `compare` or `optimize` study behavior with shared execution contracts.

Representative form:

```bash
paper-optimizer optimize --study-type optimize --config optimizer.json --out runs/optimizer/dev_run
paper-optimizer optimize --study-type compare --config optimizer.json --out runs/optimizer/compare_run
```

In `compare` mode, this command evaluates an explicit fixed candidate set and does not run iterative promotion rounds.

In `optimize` mode, this command runs bounded iterative rounds with gated promotion.

### `evaluate-candidate`

Evaluates one explicit candidate bundle on a chosen benchmark without running a full search.

Representative forms:

```bash
paper-optimizer evaluate-candidate --candidate candidates/candidate_0003 --benchmark dev --config optimizer.json --out runs/optimizer/eval_candidate_0003
paper-optimizer evaluate-candidate --candidate candidates/candidate_0003 --benchmark holdout --config optimizer.json --out runs/optimizer/holdout_candidate_0003
```

### `validate-best`

Runs the current promoted best candidate on holdout and records a validation report.

Representative form:

```bash
paper-optimizer validate-best --experiment runs/optimizer/dev_run --config optimizer.json --out runs/optimizer/holdout_validation
```

### `summarize`

Rebuilds or refreshes summary tables and plots from recorded candidate-level artifacts.

Representative form:

```bash
paper-optimizer summarize --experiment runs/optimizer/dev_run
```

This CLI surface stays narrow and maps directly to the product workflows in `spec.md`.

---

## Proposed repo architecture

The repo should remain small and explicit. A reasonable MVP module layout is:

- `cli.py`: argument parsing and command dispatch
- `settings.py`: optimizer config loading and validation
- `benchmarks.py`: benchmark manifest loading and benchmark split validation
- `search_space.py`: explicit search-surface schema and helpers
- `bundle.py`: baseline and candidate bundle contracts, hashing, lineage, materialization
- `propose.py`: deterministic-first candidate generation from the bounded search space
- `launch_main.py`: main-app launch orchestration and run-artifact discovery
- `launch_eval.py`: eval-app launch orchestration and summary loading
- `acceptance.py`: primary metrics, guardrails, deterministic checks, and promotion decisions
- `loop.py`: multi-round optimization loop
- `study.py`: shared study-mode dispatch and mode-specific loop control
- `results.py`: result-row writing, experiment manifests, best-candidate state, and audit logs
- `plotting.py`: simple static progress plots
- `contracts.py`: typed optimizer-owned records for candidates, rounds, results, and decisions

The implementation should avoid plugin systems, broad framework abstractions, or agent-style orchestration layers in MVP.

---

## Configuration model

The optimizer should use one explicit optimizer config file that points to:

- the baseline bundle
- benchmark manifests
- the search-space definition
- main-app invocation settings
- eval-app invocation settings
- primary and guardrail metric settings
- round count and batch size
- result-output settings

The optimizer config should remain small and operator-readable.

It should not mirror the entire main-app config schema. The optimizer config only needs enough information to orchestrate runs and define the bounded mutation surface.

---

## Search-space representation

The search space should be explicit, machine-readable, and narrow.

The MVP search-space definition should support:

- enumerated prompt bundle variants
- enumerated text model ids
- optional enumerated vision model ids
- bounded numeric knobs with explicit min and max or explicit allowed values
- optional categorical toggles for a very small set of known-safe flags

The search-space file should reject:

- unknown main-app config paths outside the allowed surface
- unbounded free-form text mutation requests
- code-editing actions
- benchmark or eval-definition mutation requests

The optimizer should represent candidate mutations as explicit deltas against the incumbent or baseline rather than as ad hoc free-form patches.

---

## Candidate generation strategy

### MVP strategy

The first shipping candidate generator should be deterministic-first.

Reasonable MVP generation behavior:

- draw a small batch of candidates from the explicit search space
- mutate only a small number of dimensions per candidate
- keep batch size small to control runtime
- use a stable seed when randomization is allowed at all
- avoid generating duplicate candidates within or across rounds

### Candidate proposer policy

The default proposer should not require an LLM.

It should work through a bounded combination of:

- enumerated alternatives
- templated prompt bundle variants
- small numeric perturbations
- deterministic tie-breaking and duplicate suppression

An optional later LLM-based proposer may be added only if it remains:

- bounded by the same explicit search surface
- disabled by default
- fully auditable through persisted prompts, responses, and resulting candidate manifests

---

## Candidate bundle representation

Each candidate should be materialized into an immutable candidate directory.

The candidate directory should include at minimum:

- `candidate.json` with candidate id, round index, parent id, baseline id, and lineage
- a resolved prompt-bundle snapshot or prompt-bundle manifest with content hashes
- a resolved optimizer-controlled config overlay
- selected text and vision model ids
- benchmark id used for the evaluation
- a bundle hash or manifest hash
- timestamps and creation metadata

The optimizer should never rely only on a flat results table to reconstruct what a candidate actually was.

---

## Benchmark representation

The benchmark layer should define fixed named splits such as:

- `smoke`
- `dev`
- `holdout`

Each benchmark manifest should identify:

- input table or workbook reference
- paper subset or paper list
- optional worksheet or schema subset
- optional field subset
- gold input or gold reference for eval
- runtime-relevant benchmark metadata such as expected item count

The optimizer should validate at startup that:

- dev and holdout are distinct when both are configured
- holdout is not selected as the search benchmark
- the benchmark definition is complete enough for both the main app and eval app

---

## Main-app integration strategy

The optimizer should launch the main app through a stable automation entrypoint, ideally a CLI command.

The MVP integration flow should be:

1. load the baseline main-app config reference
2. apply the candidate's bounded overlay and prompt-bundle selection
3. bind the chosen benchmark inputs
4. force the run into the appropriate eval-compatible path expected for benchmarking
5. write a resolved candidate-owned main-app config snapshot
6. launch the main app command
7. discover the produced run directory and validate required artifacts

The optimizer should not import extraction logic from the main app or reach into its internals beyond published artifacts and automation surfaces.

---

## Eval-app integration strategy

The optimizer should launch the eval app through its CLI and consume machine-readable outputs.

The MVP eval flow should be:

1. pass the produced main-app run directory to the eval tool
2. pass the benchmark's gold input and any required benchmark metadata
3. wait for eval completion
4. load the per-run summary output
5. project the required primary, guardrail, and diagnostic metrics into optimizer-owned result records

The optimizer should treat metric names from the eval app as contract-bound inputs rather than recomputing them independently.

---

## Acceptance and promotion logic

The optimizer should compare candidates through an explicit acceptance policy.

### Required acceptance inputs

The policy should consume:

- incumbent result
- challenger result
- configured primary metric name
- configured minimum primary improvement when relevant
- configured guardrail thresholds
- runtime constraints
- deterministic pass or fail checks

### Recommended MVP rule

A challenger is promotable only if all of the following are true:

- the candidate completed successfully
- the eval summary is present and valid
- the candidate improves the primary metric over the incumbent by the configured rule
- evidence-quality guardrails remain within allowed limits
- runtime remains within the allowed ceiling or delta
- failure, abstention, and null-related guardrails remain within limits

When multiple candidates are promotable in the same round, the optimizer should use deterministic tie-breaking, for example:

1. higher primary metric
2. better guardrail slack
3. lower runtime
4. lower candidate id or earlier deterministic order

Rejected candidates should still be recorded together with structured rejection reasons.

---

## Results storage and audit trail

The optimizer should treat the experiment directory as the canonical state surface.

Recommended experiment outputs:

- `experiment.json` for top-level settings and metadata
- `candidates/<candidate_id>/` for immutable candidate bundles
- `rounds/round_<n>.json` for round summaries
- `results/results.csv` for flat candidate-level comparison rows
- `results/results.jsonl` for richer candidate records
- `best_candidate.json` for the current promoted incumbent
- `holdout/` for holdout validation outputs
- `plots/` for static plot artifacts
- `logs/` for launcher logs and subprocess metadata

Each candidate record should capture at minimum:

- `schema_version`
- `experiment_id`
- `study_type`
- candidate metadata and lineage
- `candidate_id`
- `parent_candidate_id` (nullable)
- `round_index` (nullable for `compare`)
- benchmark id
- prompt bundle identity
- text model id
- optional vision model id
- flattened optimizer-controlled config knobs
- main-app run id and run path
- eval output path
- primary, guardrail, and diagnostic metrics
- acceptance decision
- acceptance or rejection reasons
- timestamps and runtime durations

The results layer should emit both:

- flat tabular output for plotting and filtering (for example CSV)
- richer event-like rows for audit and diagnostics (for example JSONL)

---

## Plotting strategy

Plotting should stay simple and static in MVP.

Shared output expectation:

- CSV-backed plotting inputs plus static PNG plots

Required `compare` mode plots:

- primary metric by candidate, model, and parameter preset
- correctness versus runtime scatter
- correctness versus evidence-quality scatter
- null or failure trend summaries
- bounded parameter-comparison sweep plots

Required `optimize` mode plots:

- best primary score by round
- all candidate primary scores by round
- runtime by round
- incumbent or champion lineage view
- score delta or improvement by round
- autoresearch-style optimization-history line plot

The plotting system should not overbuild beyond these static outputs in MVP.

---

## Multi-round loop behavior

The multi-round optimizer should follow this sequence:

1. initialize experiment metadata
2. evaluate or register the baseline candidate as the incumbent
3. for each round:
   - generate a small batch of unique candidates
   - materialize candidate bundles
   - run the main app for each candidate
   - run the eval app for each candidate run
   - compare candidates against the incumbent
   - promote the best acceptable challenger if one exists
   - persist round summary, results rows, and refreshed plots
4. optionally validate the final incumbent on holdout

The loop should stop after the configured round count. Optional early stopping can be added later, but it is not required for MVP.

`compare` mode should reuse the same launch, eval, result, and plotting contracts, but with simpler control flow:

1. initialize experiment metadata
2. materialize or load the explicit candidate set
3. run main app plus eval app for each candidate
4. write candidate-level records and comparative summaries
5. optionally trigger bounded confirmation reruns for top candidates
6. optionally validate top-k on holdout after dev comparison

---

## Holdout validation strategy

Holdout validation is separate from the main search loop.

The MVP holdout path should:

- in `optimize`: run on an explicit promoted candidate, normally the current best
- in `compare`: optionally run on top-k candidates after dev ranking
- write a separate holdout validation record
- never feed holdout results into dev-set search as the primary ranking signal

Periodic holdout validation may be supported later, but it should still remain informational rather than a search driver.

## Optional confirmation policy

The plan should reserve a bounded optional confirmation step:

- rerun top candidates to reduce noise before final promotion (`optimize`) or recommendation (`compare`)
- keep rerun counts explicitly capped
- record confirmation linkage in result records

This can be deferred to a later batch if MVP scope must stay tighter, but the contract should anticipate it.

---

## Error handling and contract checks

The optimizer should fail early on contract-breaking setup errors such as:

- missing baseline bundle data
- invalid search-space definitions
- missing benchmark manifests
- missing main-app or eval-app commands
- missing required run or eval artifacts
- incompatible metric configuration

Candidate-level failures during the loop should be recorded as candidate outcomes, not silently discarded.

---

## Testing direction

The first implementation batches should emphasize:

- config and search-space validation tests
- candidate-bundle hashing and lineage tests
- benchmark split validation tests
- subprocess-launch contract tests with mocked main-app and eval-app outputs
- acceptance-rule unit tests
- end-to-end smoke tests on a tiny mocked benchmark

The optimizer does not need deep extraction or scoring tests because those responsibilities belong to the other repos.

---

## Staged implementation approach

### Batch 1

Establish repo skeleton, config loading, benchmark and search-space contracts, candidate bundle materialization, single-run orchestration, and result logging.

### Batch 2

Add the multi-round optimization loop, acceptance and promotion logic, best-candidate tracking, and progress plotting.

### Batch 3

Add holdout validation, richer summaries, and broader contract and end-to-end tests.

### Batch 4

Optionally add a bounded LM Studio-backed candidate proposer that remains off by default and stays within the existing explicit search surface.

---

## Implementation boundary

If a future implementation direction starts to require deep imports from the main app or eval app, broad mutation of their internals, or open-ended agent behavior, that should be treated as a design change to this plan rather than as routine implementation detail.