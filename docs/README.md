# papers-to-table documentation

This is the central install, command, and navigation page for the monorepo.

## Start here

Run these commands from the repository root:

```bash
python scripts/papers_to_table.py install
python scripts/papers_to_table.py review
```

Open `http://127.0.0.1:5173` for the browser review workflow.

## Command reference

### Main app

| Goal | Command |
| --- | --- |
| Install everything | `python scripts/papers_to_table.py install` |
| Start browser review mode | `python scripts/papers_to_table.py review` |
| Run terminal preflight | `python scripts/papers_to_table.py preflight --config app/config.json` |
| Run headlessly and export with explicit auto-accept | `python scripts/papers_to_table.py headless --config app/config.json --accept-all --export` |

### Eval companion

| Goal | Command |
| --- | --- |
| Score one run bundle | `python scripts/papers_to_table.py eval --run /abs/run --gold /abs/gold.csv --schema /abs/schema.json --out /abs/eval_out` |
| Use the low-level eval CLI directly | `cd tools/eval && paper-eval evaluate ...` |

### Optimizer companion

| Goal | Command |
| --- | --- |
| Compare models | `python scripts/papers_to_table.py optimizer compare-models` |
| Optimize one model | `python scripts/papers_to_table.py optimizer optimize-one-model` |
| Run the overnight sequence | `python scripts/papers_to_table.py optimizer overnight` |

## Pick the right page

- **Human-review main app**: [`main-app/README.md`](main-app/README.md)
- **Headless and agent usage**: [`headless-agent.md`](headless-agent.md)
- **Config system reference**: [`configuration.md`](configuration.md)
- **Eval companion**: [`eval/README.md`](eval/README.md)
- **Optimizer companion**: [`optimizer/README.md`](optimizer/README.md)
- **Artifacts and exports**: [`main-app/run-artifacts.md`](main-app/run-artifacts.md)
- **Troubleshooting**: [`troubleshooting.md`](troubleshooting.md)
- **Specs and development truth**: [`../specs/README.md`](../specs/README.md)

## What confuses people most

- `app/config.example.json` is the canonical main-app template; `app/config.json` is your local machine config.
- The browser UI is the normal human workflow. Headless mode is additive for agent or batch usage.
- Eval does not run extraction. It only scores existing run bundles.
- Optimizer does not extract or score directly. It orchestrates main-app and eval runs.
- `--accept-all` is intentionally explicit because it bypasses manual review.
