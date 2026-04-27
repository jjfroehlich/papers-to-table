# papers-to-table manual

papers-to-table is a local-first system for extracting evidence-backed values from scientific PDFs into structured tables.

Use this manual for operator and agent workflows. Keep these role boundaries in mind:

- **README**: short entry point and command cheatsheet.
- **Manual (this site)**: install/run/operator guidance.
- **Specs (`specs/`)**: canonical implementation truth.

## Primary workflows

1. **Browser review mode** (default): run extraction, inspect evidence, and export only reviewed updates.
2. **Headless mode**: run extraction from terminal/agent flows, optionally auto-accept only when explicitly requested.
3. **Eval**: score run bundles against gold data.
4. **Optimizer**: orchestrate repeated compare/optimize studies.

## Start here

- New users: [Getting Started](getting-started/index.md)
- Human reviewers: [Main App → Browser Review](main-app/browser-review.md)
- Agent flows: [Main App → Headless and Accept-All](main-app/headless.md)
- Tooling: [Companion Tools](tools/eval.md)
