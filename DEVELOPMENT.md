# Development Notes (Batch 1 Foundation)

Paper Table Agent is a local-first workflow app with a React frontend and FastAPI backend.

Canonical MVP pipeline stages:
1. Load config and inputs
2. Build style profiles
3. Parse PDFs
4. Match PDFs to rows
5. Build retrieval artifacts
6. Extract proposals
7. Validate and recover evidence
8. Run scoped figure fallback
9. Write proposal artifacts
10. Review in UI
11. Export
12. Write reviewer summaries

Batch 1 implements only the run-start foundation: contracts, config handling, artifact bundles, lifecycle transitions, and UI-driven run launch/status guidance.
