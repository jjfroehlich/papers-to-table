# papers-to-table

papers-to-table is a local-first paper-to-table review app.

It ingests scientific PDFs and a structured spreadsheet, proposes evidence-backed cell values, lets a human reviewer inspect the evidence in a browser UI, and exports an audited XLSX only after explicit review.

## What the main app does

- resolves a run from a JSON config plus optional staged input overrides
- shows preflight scope and provider/model readiness before launch
- streams live run updates into the browser UI with SSE
- keeps review, evidence inspection, diagnostics, and export in a browser workflow
- persists run bundles with diagnostics, evidence, review artifacts, and reviewer summaries
- produces explicit audited exports instead of silently modifying the source workbook

## Happy-path install and run

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later and npm
- LM Studio running locally for live proposal generation

### Install

Run these commands from the repository root:

```bash
git clone https://github.com/jjfroehlich/papers-to-table.git
cd papers-to-table/app
python -m pip install -e ./backend[test]
cd frontend
npm install
cd ../..
```

### Start the app

Run these commands from the repository root:

```bash
bash scripts/run-main-backend.sh
bash scripts/run-main-frontend.sh
```

Open `http://localhost:5173`.

## Browser workflow

1. Start from the **Run** tab.
2. Run preflight to confirm the resolved table, schema, PDF scope, and provider/model readiness.
3. Start the run only after the preflight context is understood.
4. Review evidence-backed proposals in the queue-first workspace.
5. Open the diagnostics surface when you need unmatched, ambiguous, or warning context.
6. Export only after explicit review.

## Wrapper scripts

Use these scripts for the normal local workflow:

```bash
bash scripts/run-main-backend.sh
bash scripts/run-main-frontend.sh
bash scripts/test-main-backend.sh
bash scripts/test-main-frontend.sh
bash scripts/verify-main-app-full.sh
```

These wrapper scripts assume the current working directory is the repository root.

## Main docs by audience

- Product and repo overview: this file
- Operator docs: [`docs/main-app/README.md`](docs/main-app/README.md)
- Screenshot-backed operator workflow: [`docs/main-app/operator-workflow.md`](docs/main-app/operator-workflow.md)
- Contributor quickstart: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Coding-agent and maintainer rules: [`AGENTS.md`](AGENTS.md)
- Normative spec system: [`specs/README.md`](specs/README.md)
- Docs map and glossary: [`docs/README.md`](docs/README.md), [`docs/glossary.md`](docs/glossary.md)

## Trustworthiness and evidence

- Evidence types stay distinct: exact highlights, approximate highlights, quote-plus-page fallback, reasoning, and figure evidence.
- Provider mode and degraded fallback states are recorded in run artifacts.
- The default extraction path is `google/gemma-4-e4b` with `retrieval.mode=hybrid_experimental`, `retrieval.top_k=12`, recall rescue off, and whole-document mode off. `google/gemma-4-26b-a4b` remains the heavier optimization target.
- Review remains manual; proposal presence is not treated as proof.
- Export is never automatic.

## Companion tools

This repository also includes two internal developer tools:

- Eval: benchmarking and scoring for run bundles. See [`docs/eval/README.md`](docs/eval/README.md).
- Optimizer: bounded calibration and orchestration for compare/optimize studies. See [`docs/optimizer/README.md`](docs/optimizer/README.md).

These tools support development and benchmarking. They are not the primary product surface.

Current companion-tool truth:

- real benchmark studies use the explicit `*_real_dev.json` and `*_real_overnight.json` optimizer configs instead of smoke or fixture configs
- real benchmark studies are expected to run with two judges end to end
- compare-model and overnight configs include Gemma, Qwen, GPT-OSS, Unsloth, and GLM candidates under the same extraction stack with small per-model request policies
- eval and optimizer reports now separate the raw benchmark winner from the recommended default when degraded or trust caveats differ
