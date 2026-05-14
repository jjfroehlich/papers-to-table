# Spec Audit

## Purpose and context

This audit records the current state of the spec system after the 2026-05-01 spec-structure consolidation pass and the optimizer suite/replicate implementation pass.

Audit date: 2026-05-01  
Repository: `/home/runner/work/papers-to-table/papers-to-table`

This document is an audit artifact, not a second owner of runtime behavior. Current behavior remains owned by `spec.md`, `plan.md`, `tasks.md`, current docs, and code paths named below.

## Current spec ownership model

The current spec system uses:

- `specs/spec.md` as the canonical product/system behavior file
- `specs/plan.md` as roadmap and technical direction
- `specs/tasks.md` as current verified status plus backlog
- `specs/contracts/schemas/*.json` as machine-readable validation contracts
- markdown under `specs/product/`, `specs/tools/`, `specs/contracts/`, `specs/architecture/`, and `specs/process/` as compatibility references
- `specs/archive/` as historical material only

The consolidation completed earlier in this branch moved durable markdown truth into `specs/spec.md`, with roadmap/status split into `plan.md` and `tasks.md`.

## Current truth owners

| Topic | Current owner |
| --- | --- |
| Product/system behavior | `specs/spec.md` |
| Roadmap and technical direction | `specs/plan.md` |
| Verified status and backlog | `specs/tasks.md` |
| Machine-readable contracts | `specs/contracts/schemas/*.json` |
| Docs and manual | `README.md` and `docs/` |
| Compatibility references | `specs/product/`, `specs/tools/`, `specs/contracts/`, `specs/architecture/`, and `specs/process/` |
| Archive and historical material | `specs/archive/` |

## Alignment observations

### Where specs and app currently appear aligned

- The integrated spec now describes `specs/spec.md` as the cross-repo summary instead of a second full owner for optimizer, eval, and contract detail.
- The optimizer runtime now uses suite/replicate orchestration as the canonical execution path. One-benchmark work is represented as a one-benchmark suite with one replicate.
  - `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/settings.py` normalizes split aliases into suites for migration convenience.
  - `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/study.py` orchestrates candidate x suite x benchmark x replicate execution.
  - `/home/runner/work/papers-to-table/papers-to-table/tools/optimizer/paper_optimizer/cli.py` uses suite ids for low-level candidate evaluation.
- The docs and specs both treat optimizer as an orchestration tool rather than an extraction or scoring runtime.

### Where specs were recently consolidated

- `specs/spec.md` now carries explicit canonical behavior for main app, eval, optimizer, model phases, and report/output truth.
- `specs/README.md` now states that `spec.md`, `plan.md`, and `tasks.md` are the canonical markdown truth files, with JSON schemas as machine-readable contracts.
- `specs/tasks.md` now records that `specs/spec.md`, `plan.md`, and `tasks.md` are the canonical markdown truth files.

### Where docs, specs, and configs still risk duplication or drift

- Optimizer docs, optimizer spec text, and `tools/optimizer/configs/*.json` all describe benchmark behavior; they can drift if future suite/replicate config adds fields without simultaneous doc/spec updates.
- Optimizer reports and plotting now emit candidate, replicate, benchmark-summary, and suite-summary outputs.
- Checked-in optimizer configs now declare explicit benchmark suites and replicate settings.
- Split aliases may remain for convenience, but suite ids are the runtime-facing selection surface.

## Optimizer-specific current-state findings

The current optimizer implementation is suite/replicate oriented.

- Canonical execution is candidate x suite x benchmark x replicate.
- `BenchmarkManifest` still represents one table/schema/pdf_dir/gold/eval setup.
- One-benchmark suites are the supported simple case.
- `evaluate_candidate_once` remains as the leaf implementation for one candidate x one benchmark x one replicate.
- Compare, optimize, holdout validation, and low-level candidate evaluation resolve to suite execution plans.
- Current reports include suite ranking, benchmark summaries, replicate visibility, failure/degraded counts, and trust caveats.

Observed code anchors:

- `tools/optimizer/paper_optimizer/settings.py`
- `tools/optimizer/paper_optimizer/pipeline.py`
- `tools/optimizer/paper_optimizer/study.py`
- `tools/optimizer/paper_optimizer/results.py`
- `tools/optimizer/paper_optimizer/report.py`
- `tools/optimizer/paper_optimizer/plotting.py`
- `tools/optimizer/paper_optimizer/cli.py`

## Suite and replicate implementation status

Implemented runtime features:

- benchmark suite config validation
- replicate config validation
- suite execution plans
- candidate x suite x benchmark x replicate orchestration
- persisted `replicate_index` and `replicate_id`
- benchmark-level aggregate artifacts
- suite-level aggregate artifacts using benchmark-level means
- report and plotting outputs that surface replicate caveats and `n=1` warnings

## Implementation order used for suite and replicate support

1. Extend optimizer config loading and validation to accept `benchmark_suites` and `replicates` sections.
2. Add benchmark-suite resolution logic that turns an explicit ordered suite id into ordered benchmark ids.
3. Add replicate orchestration for candidate x benchmark execution, with explicit replicate ids, artifact paths, and visible failed or degraded replicate results.
4. Add persisted benchmark-level and suite-level aggregation artifacts, including benchmark coverage, failure counts, degraded counts, runtime summaries, SD, and SEM.
5. Update ranking, reporting, and plotting so suite mode and replicate mode show trust caveats, `n=1` warnings, and the distinction between raw winner and recommended default.
6. Replace old one-benchmark execution branches with the canonical suite execution path.
7. Migrate checked-in optimizer configs to explicit suite and replicate settings.

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
