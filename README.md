<p align="center">
  <img src="./app/frontend/public/banner_1.jpg" width="900" alt="Title banner" />
</p>

Papers-to-table is an experimental system to extract information from scientific PDFs into structured tables, using large language models. It runs fully local, and includes an interface for human review, auditable run bundles, and tools for benchmarking and experiments.

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

The canonical `compare-models` preset includes external baselines and a gold positive control. Text cells are judge-scored by default, including normalized exact matches; only pass `--enable-text-exact-match-fast-path` through eval args for calibration runs that intentionally want deterministic text bypasses.

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
Two experimental agent-skill workflows:

- `skills/papers-to-table-agent-kit/`: portable rich review handoff for agents that already extract values from PDFs. Agents author `review_input.json` plus PDFs and optional table/schema files; the kit generates the local review UI, decisions, audit artifacts, and accepted-only CSV export without requiring the main app, backend, or local LLM provider.
- `skills/papers-to-table-local-app/`: local-app workflow for agents that can run the locally installed app with local LLM provider LM Studio.

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

## Specifications
The active rebuild-grade spec system starts at [`specs/README.md`](specs/README.md), with integrated truth in [`specs/spec.md`](specs/spec.md). Active improvement tracking lives in `specs/improvement-ideas.md` and `specs/experiment-results.md`; historical compatibility references live under `specs/archive/` only.

## Related systems
Commercial and research systems [Google Labs Science](https://labs.google/science/), [Elicit](https://elicit.com/), and [Scite](https://scite.ai/), all use structured information extracted from literature. This here is a free open source project. It can be used locally to for literature reviews, to experiment with large language models, or to be integrated in agentic research systems. 
