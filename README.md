<p align="center">
  <img src="./app/frontend/public/banner_1.jpg" width="900" alt="Title banner" />
</p>

## Purpose
Papers-to-table is an experimental system to extract reported information from scientific PDFs into structured tables, using large language models. Target fields can ask for technical parameters, descriptions of results, or claims made in a publication. The app links extracted information to inspectable source evidence. It runs fully local, and includes an interface for human review, auditable run bundles, and tools for benchmarking and experiments.

<p align="center">
  <img src="docs/diagrams/refined_svg/01_readme_user_overview_refined.svg" width="760" alt="Illustrative papers-to-table workflow" />
</p>

## Relevance
Commercial literature tools often extract structured information into table formats, see for example [Google Labs Science](https://labs.google/science/), [Elicit](https://elicit.com/), or [Scite](https://scite.ai/). This project here is free, open source, and can run fully local. It can be used for literature reviews, to experiment with large language models, or to be integrated in larger agentic research assistants.

<p align="center">
  <img src="docs/plots/20260615_004637_compare_models_plots_v2/20260615_004637_compare_models_plots_v2_main_plot_readme.jpg" width="380" alt="Benchmark scores for seven local papers-to-table models and Codex with GPT-5.5 xhigh" />
</p>

*Content-correctness [Eval scores](docs/tools/eval.md) across 15 papers and 31 target columns. Points show replicate-level scores, boxes summarize their distribution, and bars show the average. Results are from optimizer run `20260615_004637_compare_models`. These scores measure agreement with the current gold answers; they are not literal percentages of objectively right values because some benchmark fields permit reasonable judgment. See [Interpreting benchmark scores](docs/tools/benchmark-datasets.md#interpreting-benchmark-scores).*

## Hardware Specs
Developed and benchmarked on Windows 11 Pro 64-bit (build 26200), with AMD Ryzen 9 5950X processor (16 cores / 32 threads), 32 GB RAM, and an NVIDIA GeForce RTX 3090 with 24 GB VRAM.

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
```

### Command-line interface
Use this headless mode when a terminal workflow, batch script, or agent needs to run the app without reviewing the extracted values and browser UI. 

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

### Optimizer tool
Optimizer is an orchestration tool for comparing different models, prompts, and configuration parameters with Eval scoring.

```bash
python scripts/papers_to_table.py optimizer dev-check
python scripts/papers_to_table.py optimizer compare-models
python scripts/papers_to_table.py optimizer full-benchmark
```

### Eval tool
Eval can score main-app output against benchmarking datasets to create benchmark scores. 

```bash
python scripts/papers_to_table.py eval \
  --run /absolute/path/to/run_bundle \
  --gold /absolute/path/to/gold.csv \
  --schema /absolute/path/to/schema.json \
  --out /absolute/path/to/eval_out
```

### Agent skills
- `skills/papers-to-table-agent-kit/`: standalone skill for regular agent systems (Codex, Claude, Hermes, etc.), which instructs an agent for systematic extraction and provides an interface for human review. 
- `skills/papers-to-table-local-app/`: local-first skill for agents to run the locally installed app with a local LLM provider LM Studio.

Install by telling your agent, for example `install the skills at https://github.com/jjfroehlich/papers-to-table/tree/main/skills/`. Alternatively, copy the relevant skill folder into your agent system's skill directory.

## Documentation
The manual source lives in [`docs/`](docs/). 
Serve the static site locally with:
```bash
python scripts/papers_to_table.py docs serve
```
Compile the static site to /site:
```bash
python scripts/papers_to_table.py docs build
```
