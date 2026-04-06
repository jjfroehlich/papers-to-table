# Spec Implementation Audit

Reality-checked on 2026-04-06 against current source, targeted tests, checked-in docs, historical run artifacts, and live browser behavior.

This document supports [specs/tasks.md](../specs/tasks.md), which remains the canonical progress tracker.

## Contradictions Found And Fixed

| Area | Old claim | Verified reality | Action |
| --- | --- | --- | --- |
| Repo implementation state | Root guidance still described the repo as pre-restart or lacking canonical commands. | The repo has an implemented FastAPI backend, React frontend, backend/frontend tests, screenshots, and canonical startup commands. | Updated `AGENTS.md` and `specs/AGENTS.md` to match current repo truth. |
| Earliest incomplete canonical batch | A quick read could suggest Batch 4 because several later items were unchecked. | `specs/tasks.md` still had unchecked Batch 1 work (`T052d`, `T067e`), so Batch 1 was the earliest incomplete canonical batch. | Implemented the Batch 1 provider-truth gap first. |
| Checked-in run artifacts | Historical run bundles looked like current artifact truth. | Checked-in bundles under `runs/` predate current artifact paths and omit newer summary/diagnostic fields. | Treated checked-in bundles as historical examples, not canonical behavior. |

## Verified Features

| Item | Evidence | Status | Notes |
| --- | --- | --- | --- |
| Config snapshot persistence and resolved input context | `backend/app/runner.py`, `tests/backend/test_runner.py` | Implemented | `config.snapshot.json` and resolved input context are written at run start. |
| Lexical retrieval baseline artifacts | `backend/app/retrieval.py`, `tests/backend/test_batch3.py`, `tests/backend/test_runner.py` | Implemented | Canonical retrieval mode is `lexical`; retrieval artifacts persist per cell. |
| Prompt identity and bundle provenance | `backend/app/prompts.py`, `backend/app/runner.py`, `backend/app/extraction.py`, `tests/backend/test_runner.py`, `tests/backend/test_batch3.py` | Implemented | Run artifacts persist `prompt_hash`, bundle identity, manifest hash, bundle hash, and prompt keys/files. |
| Stable non-UI automation entrypoint | `backend/app/automation.py`, `tests/backend/test_automation.py` | Implemented | Supports `start`, `status`, and `wait` with machine-readable payloads. |
| Provider diagnostics and probes | `backend/app/runner.py`, `backend/app/artifacts.py`, `tests/backend/test_runner.py`, `tests/backend/test_artifacts.py` | Implemented | Diagnostics persist under `diagnostics/`, including provider probe and request counts. |
| Retrieval-failure diagnostics | `backend/app/extraction.py`, `backend/app/runner.py` | Implemented | Questionable-cell classification is persisted from current extraction artifacts. |
| Figure-review ROI diagnostics | `backend/app/extraction.py`, `backend/app/runner.py` | Implemented | Per-cell and aggregate figure-review counters/timing are persisted. |
| Provider readiness vs capability truth | `backend/app/provider.py`, `backend/app/runner.py`, `backend/app/review.py`, `backend/app/automation.py`, `frontend/src/components/RunDetail.tsx`, `frontend/src/components/RunSummaryPanel.tsx`, targeted backend/frontend tests | Implemented in this pass | Readiness failures and structured-output fallback/capability classes are now carried separately end to end. |
| Review header fallback/status UI | Live browser check at `http://127.0.0.1:4173/` | Implemented | Review header showed `LM Studio`, `live local`, and `prompt-only fallback` chips on a historical degraded run. |

## Task Reclassification Summary

- Batch 1: complete after implementing `T052d` and `T067e`.
- Batch 4: mixed state.
- `T108`: implemented.
- `T109`: partial. Run stats exist, but the full counter surface described in the task text is not complete.
- `T111`: partial. Heuristic policy exists and is persisted per retrieval artifact, but compact run-level policy usage summaries are still missing.
- `T112`: implemented.
- Batch 5: implemented.

## Browser Verification Notes

- The live app shell loaded successfully with the expected Run-first empty state.
- The Run tab listed historical runs and enabled the Review tab after run selection.
- The selected historical run showed run-detail provider status, structured-output mode, fallback-used status, warnings, and resolved input paths.
- The Review tab showed operator-facing summary chips and the prompt-only fallback badge in the header.

## Remaining Gaps

- `T109` is still not complete enough to mark done: some counter fields described in the task text are not yet emitted.
- `T111` is still not complete enough to mark done: heuristic policy is persisted per retrieval artifact, but compact aggregate usage summaries are not yet emitted in run outputs.
- Broad test runs still include unrelated existing failures outside this pass, including failures in `tests/backend/test_batch3.py`.
- The checked-in Playwright pytest harness was blocked in this Windows environment because Python subprocess startup could not locate `npm`; direct live-browser verification was used instead.