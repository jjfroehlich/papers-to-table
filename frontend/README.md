# Frontend (Batch 1 baseline)

This frontend is the Batch 1 React + Vite + TypeScript shell for Paper Table Agent.

Implemented in this batch:
- Run and Review top-level views
- config-path run launch form
- run list + selected-run setup/lifecycle summary
- explicit pre-review guidance for empty/loading/running/failed/terminal states
- lifecycle polling against backend run APIs

Not implemented yet (later batches):
- proposal queue/detail/evidence viewer
- review decisions
- unresolved-match inspection
- export/download interactions

## Commands

```bash
npm install
npm run dev -- --host 127.0.0.1 --port 5173
npm run lint
npm run test
npm run build
npm run test:e2e -- --list
```

The UI expects backend API at `http://127.0.0.1:8000` by default. Override with `VITE_API_BASE_URL` if needed.
