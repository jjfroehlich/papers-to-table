# Development Note (Batch 1 Baseline)

Paper Table Agent is implemented as a local-first workflow app with:

1. `backend/` FastAPI service that validates config, creates run artifact bundles, and executes a staged runner in-process.
2. `frontend/` React app with Run and Review views.
3. `tests/` deterministic fixture corpus and backend/frontend test scaffolding.

Canonical near-term pipeline stages:
- run creation
- config validation + snapshot
- input loading + table/schema checks
- eligibility classification (missing vs verify-mode filled)
- lifecycle progression to terminal state with inspectable artifacts

Later batches add parsing, matching, extraction, review queue, and export.
