# Monorepo Migration Prep

## Scope

This note records the baseline state for migrating the separate main app, eval, and optimizer repositories into the current main app repository as the long-term monorepo home.

This note began as the preparation batch note and now also records the structural migration batch.

- The destination repository remains the current main app repo.
- The main app stays primary in structure, naming, and operator-facing documentation.
- Public CLI semantics should be preserved unless a later batch requires a narrow compatibility adjustment.

## Current Source State

Recorded on `2026-04-18`.

| Repo role | Local path | Branch at capture | HEAD SHA |
| --- | --- | --- | --- |
| Destination main app | `D:/code/local/extract-structured-info-from-papers` | `main` before branch creation | `83bb44cff2ad6445fa4ba7dd659b024512473263` |
| Source eval repo | `D:/code/local/extract-structured-info-from-papers-eval` | `main` | `1623c6b0b91b03166bb766e0fea3f73202427ea4` |
| Source optimizer repo | `D:/code/local/extract-structured-info-from-papers-optimizer` | `main` | `e9f1cb0d9d4ca745ef28d59c71b33e9a3c5396a5` |

Migration work for this prep batch is on branch `migration/monorepo-prep` in the destination repo.

## Target Structure

Planned long-term layout:

```text
extract-structured-info-from-papers/
  README.md
  docs/
    main-app/
    eval/
    optimizer/
    contracts/
  benchmarks/
  app/
  tools/
    eval/
    optimizer/
  scripts/
```

Interpretation for later batches:

- `app/` becomes the primary home for the main app runtime and UI.
- `tools/eval/` becomes the in-repo home for the evaluator.
- `tools/optimizer/` becomes the in-repo home for the optimizer.
- `docs/` is split so the main app remains clearly primary while eval and optimizer docs remain available.
- No shared runtime package is introduced during this migration.

## Structural Migration Batch

Structural migration completed on branch `migration/monorepo-prep` after the prep checkpoint.

### Imports performed

History-preserving imports were performed with `git subtree add` without `--squash`:

- Eval source `1623c6b0b91b03166bb766e0fea3f73202427ea4` imported to `tools/eval/`
- Optimizer source `e9f1cb0d9d4ca745ef28d59c71b33e9a3c5396a5` imported to `tools/optimizer/`

Resulting import commits in the destination repo:

- `36936208f10d6a53397471eb66990193577af4ce` for `tools/eval/`
- `34dd28c837e7e60dcd45d7d7407c9a749522d746` for `tools/optimizer/`

### Main app moves performed

The main app runtime and immediate config/test surface were moved into `app/` using `git mv` where the files were tracked:

- `backend/` -> `app/backend/`
- `frontend/` -> `app/frontend/`
- `tests/` -> `app/tests/`
- `config.example.json` -> `app/config.example.json`
- `config.json` -> `app/config.json`
- `pyproject.toml` -> `app/pyproject.toml`
- `uv.lock` -> `app/uv.lock`

The generated `extract_structured_info_from_papers_backend.egg-info/` directory was present locally but not tracked, so it was not moved with `git mv`.

### History preservation status

- Eval history preserved through subtree import.
- Optimizer history preserved through subtree import.
- Main app move history preserved through `git mv` rename tracking for the tracked files listed above.

### Minimal path adjustments made in this batch

Only the smallest root-level path references were updated so the destination repo is structurally coherent:

- root `AGENTS.md` now points at `app/backend`, `app/frontend`, and `app/tests/fixtures`
- root CI workflow now installs/tests from `app/backend` and `app/frontend`

### Temporary broken or stale paths intentionally left for the next batch

The following are intentionally deferred to the path/runtime-fix batch rather than redesigned here:

- root `README.md` still documents pre-move main-app paths
- imported `tools/optimizer/README.md` still documents sibling repos
- imported optimizer configs still point at sibling repo paths such as `../extract-structured-info-from-papers` and `../extract-structured-info-from-papers-eval`
- imported optimizer launchers and shell scripts still assume separate repo roots
- imported eval and optimizer CI files still reflect their original standalone-repo layouts
- any runtime command that shells into the old top-level `frontend/` path is now stale

## Current Entrypoints And Baseline Commands

### Main app

Primary operator and automation entrypoints:

- Backend API server: `python -m uvicorn backend.app.main:app --reload --port 8000`
- Backend automation CLI: `python -m backend.app.automation start --config-path config.json`
- Frontend dev server: `npm --prefix frontend run dev`
- Backend tests: `pytest tests/backend -m "not e2e and not smoke"`
- Frontend tests: `npm --prefix frontend test -- --run`

Evidence:

- `README.md`
- `backend/app/automation.py`
- `backend/app/main.py`
- `backend/pyproject.toml`
- `frontend/package.json`
- `.github/workflows/ci.yml`

### Eval repo

Primary entrypoints:

- CLI: `python -m paper_eval evaluate ...`
- Compare rebuild: `python -m paper_eval compare ...`
- Tests: `pytest`

Evidence:

- `README.md`
- `paper_eval/__main__.py`
- `paper_eval/cli.py`
- `.github/workflows/ci.yml`

### Optimizer repo

Primary entrypoints:

- Installed CLI: `paper-optimizer ...`
- Module CLI used by scripts: `python -m paper_optimizer.cli ...`
- Study wrapper: `bash scripts/run_study.sh ...`
- Overnight wrapper: `bash scripts/run_overnight.sh ...`
- Tests: `pytest` with `MPLBACKEND=Agg`

Evidence:

- `README.md`
- `pyproject.toml`
- `paper_optimizer/cli.py`
- `scripts/run_study.sh`
- `scripts/run_overnight.sh`
- `.github/workflows/ci.yml`

## Migration Strategy

This migration stays structural first.

1. Keep the main app repo as the destination and preserve its identity as the root product.
2. Import eval and optimizer history into the destination repo with path prefixes rather than copying files without history.
3. Use `git mv` for files already in the main app repo whenever they move to their monorepo locations.
4. Land structural movement before behavior changes, then do the smallest path and runtime fixes needed to restore existing commands.
5. Keep migration notes and per-batch verification in-repo so later batches can compare against a pinned baseline.

## Baseline Verification

Commands below were run before any structural import.

Python commands used the currently configured interpreter:

`d:/code/web/guess-the-citations/.venv/Scripts/python.exe`

### Main app baseline

Command:

```bash
cd /d/code/local/extract-structured-info-from-papers
d:/code/web/guess-the-citations/.venv/Scripts/python.exe -m pytest tests/backend -m "not e2e and not smoke"
```

Result:

- Failed, exit code `1`
- `1 failed, 642 passed, 1 deselected in 77.25s`
- Failing test: `tests/backend/test_e2e_hermetic.py::TestHermeticMatchedExtractionExport::test_export_xlsx_written_with_correct_value`
- Decisive assertion excerpt: `AssertionError: assert 'Cloning' in ['column_name', 'description']`

Command:

```bash
cd /d/code/local/extract-structured-info-from-papers
npm --prefix frontend test -- --run
```

Result:

- Passed, exit code `0`
- `12 passed files, 71 passed tests`
- Reported duration: `53.43s`

### Eval baseline

Command:

```bash
cd /d/code/local/extract-structured-info-from-papers-eval
d:/code/web/guess-the-citations/.venv/Scripts/python.exe -m pytest
```

Result:

- Passed, exit code `0`
- `67 passed in 3.65s`

### Optimizer baseline

Command:

```bash
cd /d/code/local/extract-structured-info-from-papers-optimizer
env MPLBACKEND=Agg d:/code/web/guess-the-citations/.venv/Scripts/python.exe -m pytest
```

Result:

- Failed, exit code `1`
- `1 failed, 38 passed in 15.90s`
- Failing test: `tests/test_proposer_and_confirmation.py::test_confirmation_rerun_can_block_promotion`
- Decisive assertion excerpt: `AssertionError: assert 'cand_0001' == 'cand_0000'`

### Baseline interpretation

- Eval is green at the captured SHA.
- Main app already has one failing backend test before migration work.
- Optimizer already has one failing test before migration work.
- Those failures should be treated as pre-existing baseline issues unless a later migration batch changes the same code paths.

## Known Path Assumptions To Update Later

The most important migration risk is the optimizer's current assumption that the main app and eval app live as sibling repositories.

### Runtime-critical assumptions

1. Optimizer config files hardcode sibling-repo roots and fixture paths.

Examples:

- `config.example.json`
- `configs/compare_models_dev.json`
- `configs/compare_models_fixture_dev.json`
- `configs/compare_models_smoke.json`
- `configs/compare_prompts_dev.json`
- `configs/compare_retrieval_dev.json`
- `configs/compare_retrieval_modes_dev.json`
- `configs/optimize_overnight.json`

Current assumptions include paths like:

- `../extract-structured-info-from-papers`
- `../extract-structured-info-from-papers-eval`
- `../../extract-structured-info-from-papers/tests/fixtures/...`
- `../../extract-structured-info-from-papers-eval/tests/fixtures/...`

2. Optimizer config loading resolves path fields relative to the optimizer config file location.

Evidence:

- `paper_optimizer/settings.py`

Affected fields include:

- `repo_root`
- `base_config_path`
- `table_path`
- `schema_path`
- `pdf_dir`
- `gold_path`
- `eval_schema_path`

3. Optimizer launches the main app and eval app by switching subprocess working directories to separate repo roots.

Evidence:

- `paper_optimizer/launch_main.py`
- `paper_optimizer/launch_eval.py`

4. Optimizer shell wrappers assume their repo root is also the runtime root for configs, runs, and logs.

Evidence:

- `scripts/run_study.sh`
- `scripts/run_overnight.sh`

These scripts are not wrong today, but their path math must be updated once the optimizer lives under `tools/optimizer/`.

### Documentation assumptions

1. Optimizer README explicitly documents a multi-repo sibling checkout layout.

Evidence:

- `extract-structured-info-from-papers-optimizer/README.md` in the source repo

2. Main app README describes optimizer consumption as external tooling.

Evidence:

- `README.md`

That wording is directionally correct today, but after migration it should describe optimizer and eval as in-repo tools instead of separate repositories.

3. Eval README presents the evaluator as a separate repository identity.

Evidence:

- `extract-structured-info-from-papers-eval/README.md` in the source repo

### Historical artifacts with embedded absolute paths

Generated files under optimizer `runs/` and `logs/` embed absolute paths to the current repo layout.

Examples:

- optimizer run metadata files
- materialized configs under past run directories
- overnight analysis reports and logs

These are historical artifacts, not primary runtime code. Later batches should avoid broad rewriting of historical runs unless a specific operator requirement makes it necessary.

## Risk Areas

1. CLI compatibility during path moves.
2. Optimizer subprocess launches that currently rely on separate working directories.
3. Relative benchmark and fixture references in optimizer configs.
4. Main app backend and frontend startup commands if `backend/` and `frontend/` move under `app/`.
5. CI consolidation across Python backend, frontend, eval, and optimizer checks.
6. Avoiding a premature shared package during path cleanup.
7. Preserving git history for eval and optimizer imports.

## Batch Plan

### Batch 2: Structural import and move

Goal: bring all three codebases into the destination repo with preserved history where practical, but keep fixes limited to what is required for the tree to exist coherently.

Planned steps:

1. Add source remotes for eval and optimizer to the destination repo and fetch pinned SHAs.
2. Import eval into `tools/eval/` with history preserved via prefixed git import.
3. Import optimizer into `tools/optimizer/` with history preserved via prefixed git import.
4. Create destination doc folders:
   - `docs/main-app/`
   - `docs/eval/`
   - `docs/optimizer/`
5. Move main-app-owned docs into `docs/main-app/` only where the move is structural and low risk.
6. Move main app runtime directories into the planned `app/` subtree with `git mv` rather than copy/delete.
7. Move or create top-level `scripts/` only for scripts that belong at monorepo root.
8. Keep imports and command fixes minimal in this batch; only add transitional notes if commands are temporarily expected to fail until Batch 3.

Expected moved locations after Batch 2:

- main app runtime under `app/`
- eval under `tools/eval/`
- optimizer under `tools/optimizer/`

Verification target for Batch 2:

- tree shape exists as planned
- git history for imported repos is visible from the destination repo
- no accidental content drops

### Batch 3: Path and runtime fixes

Goal: restore working CLI, test, config, and script behavior from the new monorepo layout without redesigning ownership boundaries.

Planned steps:

1. Update optimizer config defaults and prepared configs to monorepo-local paths.
2. Update optimizer path resolution and launch working-directory logic to the new in-repo locations.
3. Adjust shell scripts so `tools/optimizer/scripts/*.sh` still produce the same run and log behavior from the new tree.
4. Update main app backend and frontend startup/test commands if the `app/` move changes working directories.
5. Update CI to run the same checks from the new paths.
6. Add only narrow compatibility shims if needed to keep current public CLI semantics working.
7. Re-run the same baseline commands from this note using monorepo paths and compare outcomes against the pre-migration baseline.

Verification target for Batch 3:

- existing documented startup commands either still work or have explicit compatibility wrappers
- optimizer can locate main app, eval, and fixtures inside the monorepo
- baseline test surface is restored to at least the pre-migration pass/fail profile

### Batch 4: Docs, polish, and finalization

Goal: make the monorepo truthful and operator-usable once runtime paths work.

Planned steps:

1. Rewrite the root README so the main app remains primary and eval/optimizer are described as in-repo tools.
2. Split or relocate repo-specific docs into `docs/main-app/`, `docs/eval/`, and `docs/optimizer/`.
3. Update examples and setup instructions that currently assume sibling repositories.
4. Add an explicit migration summary and final tree map.
5. Remove stale cross-repo wording that no longer matches the monorepo.
6. Run final baseline verification and record exact commands and outcomes.

Verification target for Batch 4:

- docs match the new layout
- root repo identity is still centered on the main app
- eval and optimizer instructions remain available but secondary

## Rollback Strategy

Rollback should remain commit-based and batch-scoped.

1. Keep each migration batch in a small, reviewable commit or short commit stack on `migration/monorepo-prep` or follow-on migration branches.
2. Do not rewrite the source repositories during migration prep.
3. If Batch 2 import or moves go wrong, revert the specific import or move commit instead of redesigning in place.
4. If Batch 3 path fixes go wrong, revert only the runtime-fix commit(s) and keep the structural import commit intact for inspection.
5. Keep this note updated with the exact source SHAs so a clean re-import remains possible.
6. Do not merge to `main` until the baseline verification surface is re-run from the new layout.

## Immediate Next Checks For Batch 2

Before the next batch starts, confirm:

1. The destination repo still has a clean diff except for this migration note.
2. The source repo SHAs above are still the intended import points.
3. The chosen git import method preserves history acceptably for review.
4. No new unrelated failures appear in the existing baseline commands.