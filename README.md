<p align="center">
  <img src="./app/frontend/public/banner_1.jpg" width="900" alt="Title banner" />
</p>

papers-to-table is a local-first system for extracting information from scientific PDFs into structured tables. It combines a browser review app for human review, auditable run bundles, and companion tools for getting benchmarking scores and for optimizing parameters.

## Quickstart

From the repository root:

```bash
python scripts/papers_to_table.py install
```

This installs backend, frontend, eval, and optimizer, with dependencies. It also upgrades `pip`, runs `npm audit fix` for the frontend, and fails if `npm audit --audit-level=moderate` still finds a moderate-or-worse vulnerability.

```bash
python scripts/papers_to_table.py review
```

This starts the browser-based app, which will be available at `http://127.0.0.1:5173`.

## Core commands

### Main app 
This is the primary workflow where the browser interface can be used to inspect evidence, and accept or edit proposals. 

```bash
python scripts/papers_to_table.py review
python scripts/papers_to_table.py preflight --config app/config.json
```

### Command-line interface
Use this headless mode when a terminal workflow, batch script, or coding agent needs to run the app without reviewing the extracted values and browser UI. 

(description for )
```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

### Eval tool
Eval can score main-app output against human-verified data to create benchmark scores. 

```bash
python scripts/papers_to_table.py eval \
  --run /absolute/path/to/run_bundle \
  --gold /absolute/path/to/gold.csv \
  --schema /absolute/path/to/schema.json \
  --out /absolute/path/to/eval_out
```

### Optimizer tool
Optimizer is an orchestration tool for comparing different models, prompts, and configuration parameters with Eval scoring.

```bash
python scripts/papers_to_table.py optimizer compare-models
python scripts/papers_to_table.py optimizer optimize-one-model
python scripts/papers_to_table.py optimizer overnight
```
### /Papers-to-table skill
Agents can use the skill when the task is to extract structured values from one or several scientific publications (for which .pdf files are available). 
Copy `./agent-skills/papers-to-table/` into your agent system's skill directory. Keep the `references/` files with it.

## Documentation
(link to relevant pages or better to static site if possible without a public github repository)

