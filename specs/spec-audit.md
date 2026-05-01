# Spec Audit

## Purpose and context

This audit records the current state of the spec system after the 2026-05-01 spec-structure consolidation pass and before the next optimizer implementation pass.

Audit date: 2026-05-01  
Repository: `/home/runner/work/papers-to-table/papers-to-table`

This document is an audit artifact, not a second owner of runtime behavior. Current behavior remains owned by the existing current specs, docs, and code paths named below.

## Current spec ownership model

The current spec system uses:

- `specs/spec.md` as the integrated repo-level summary
- domain-owning current specs under `specs/product/`, `specs/tools/`, `specs/contracts/`, `specs/architecture/`, and `specs/process/`
- `specs/tasks.md` as current verified status plus backlog
- `specs/archive/` as historical material only

The consolidation completed earlier in this branch moved `specs/spec.md` toward an integration role and reduced duplicated detailed truth there. Detailed durable truth is expected to live in the owning current file and be referenced from `spec.md`, not copied into it.

## Current truth owners

| Topic | Current owner |
| --- | --- |
| Integrated truth | `/home/runner/work/papers-to-table/papers-to-table/specs/spec.md` |
| Main-app product behavior | `/home/runner/work/papers-to-table/papers-to-table/specs/product/main-app.md` and `/home/runner/work/papers-to-table/papers-to-table/specs/product/review-workflow.md` |
| Optimizer behavior | `/home/runner/work/papers-to-table/papers-to-table/specs/tools/optimizer.md` |
| Eval behavior | `/home/runner/work/papers-to-table/papers-to-table/specs/tools/eval.md` |
| Run-bundle contracts | `/home/runner/work/papers-to-table/papers-to-table/specs/contracts/run-bundle.md`, `/home/runner/work/papers-to-table/papers-to-table/specs/contracts/eval-summary.md`, `/home/runner/work/papers-to-table/papers-to-table/specs/contracts/proposals-and-evidence.md`, `/home/runner/work/papers-to-table/papers-to-table/specs/contracts/optimizer-candidate.md` |
| Testing and change policy | `/home/runner/work/papers-to-table/papers-to-table/specs/process/testing-strategy.md` and `/home/runner/work/papers-to-table/papers-to-table/specs/process/change-policy.md` |
| Docs and manual | `/home/runner/work/papers-to-table/papers-to-table/README.md` and `/home/runner/work/papers-to-table/papers-to-table/docs/` |
| Archive and historical material | `/home/runner/work/papers-to-table/papers-to-table/specs/archive/` |

## Alignment observations

### Where specs and app currently appear aligned

- The integrated spec now describes `specs/spec.md` as the cross-repo summary instead of a second full owner for optimizer, eval, and contract detail.
- The optimizer code currently matches a single-benchmark selection model:
  - `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/benchmarks.py` loads named manifests and maps `smoke`, `dev`, and `holdout` splits to one benchmark id each.
  - `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/settings.py` validates one `benchmarks` object with manifest definitions plus optional `smoke`/`dev`/`holdout` selectors.
  - `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/pipeline.py` evaluates one candidate against one benchmark id at a time.
  - `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/cli.py` limits `evaluate-candidate --benchmark` to `smoke`, `dev`, or `holdout`.
- The docs and specs both treat optimizer as an orchestration tool rather than an extraction or scoring runtime.

### Where specs were recently consolidated

- `specs/spec.md` now carries explicit ownership metadata and points to owning current files instead of copying large sections of optimizer/eval/contract detail.
- `specs/README.md` now states that `product/`, `tools/`, `contracts/`, `architecture/`, and `process/` remain normative owners for their domains.
- `specs/tasks.md` now records that `specs/spec.md` acts as the integrated summary while detailed truth stays in owning current specs.

### Where docs, specs, and configs still risk duplication or drift

- Optimizer docs, optimizer spec text, and `tools/optimizer/configs/*.json` all describe benchmark behavior; they can drift if future suite/replicate config adds fields without simultaneous doc/spec updates.
- Optimizer reports and plotting code currently emit candidate-level outputs, while the next planned suite/replicate extension will need new aggregate artifacts and clear naming to avoid mismatches between report wording and actual files.
- The checked-in optimizer configs remain centered on manifest-level `smoke`/`dev`/`holdout` selectors, so future suite examples must avoid implying that suite execution already exists.
- The CLI surface and docs currently describe single benchmark split selection; any later suite CLI surface must be additive and must not silently redefine existing split semantics.

## Optimizer-specific current-state findings

The current optimizer implementation is still single-benchmark oriented.

- Current optimizer supports single benchmark split selection via `smoke` / `dev` / `holdout`.
- Current `BenchmarkManifest` represents one table/schema/pdf_dir/gold/eval setup.
- Current `evaluate_candidate_once` evaluates one candidate on one benchmark.
- Current CLI `evaluate-candidate` is limited to `smoke` / `dev` / `holdout`.
- Current reports are candidate-level, not true suite or replicate aggregation.

Observed code anchors:

- `tools/optimizer/paper_optimizer/benchmarks.py`
- `tools/optimizer/paper_optimizer/settings.py`
- `tools/optimizer/paper_optimizer/pipeline.py`
- `tools/optimizer/paper_optimizer/study.py`
- `tools/optimizer/paper_optimizer/report.py`
- `tools/optimizer/paper_optimizer/plotting.py`
- `tools/optimizer/paper_optimizer/cli.py`

## Explicit missing features

These features were missing at the time of the audit and have since been implemented in the optimizer runtime:

- benchmark suites
- replicates
- suite-level aggregation and reporting

Current implementation follow-up:

- config validation now covers `benchmark_suites`
- config validation now covers `replicates`
- persisted replicate rows include `replicate_index` and `replicate_id`
- suite-level weighted aggregation uses benchmark-level means
- report and plotting outputs now surface replicate caveats and `n=1` warnings

## Implementation order used for suite and replicate support

1. Extend optimizer config loading and validation to accept additive `benchmark_suites` and `replicates` sections without breaking existing `benchmarks.dev` / `benchmarks.holdout` behavior.
2. Add benchmark-suite resolution logic that turns an explicit ordered suite id into ordered benchmark ids, while preserving the current single-benchmark default when no suite is configured.
3. Add replicate orchestration for candidate x benchmark execution, with explicit replicate ids, artifact paths, and visible failed or degraded replicate results.
4. Add persisted benchmark-level and suite-level aggregation artifacts, including benchmark coverage, failure counts, degraded counts, runtime summaries, SD, and SEM.
5. Update ranking, reporting, and plotting so suite mode and replicate mode show trust caveats, error bars, `n=1` warnings, and the distinction between raw winner and recommended default.
6. Add backward-compatibility tests for old configs, old CLI behavior, and readability of existing result files.

## Verification performed

Reviewed current files:

- `/home/runner/work/papers-to-table/papers-to-table/AGENTS.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/AGENTS.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/README.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/spec.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/tasks.md`
- `/home/runner/work/papers-to-table/papers-to-table/specs/tools/optimizer.md`
- `/home/runner/work/papers-to-table/papers-to-table/docs/tools/optimizer.md`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/benchmarks.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/settings.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/contracts.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/pipeline.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/study.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/report.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/plotting.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/cli.py`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/configs/*.json`
- `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/tests/`

Verification command run:

```bash
cd /home/runner/work/papers-to-table/papers-to-table
python scripts/papers_to_table.py docs build --strict
```

Result: succeeded.
