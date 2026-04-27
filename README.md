# papers-to-table

papers-to-table is a local-first paper-to-table review app.

It ingests scientific PDFs plus a structured spreadsheet, proposes evidence-backed cell values, keeps human review in a browser UI, and exports an audited workbook only after explicit acceptance.

## Repository shape

This monorepo has three operator-facing surfaces:

- **Main app**: browser review workflow for preflight, extraction, review, and export
- **Eval companion**: scores a main-app run bundle against gold data
- **Optimizer companion**: launches repeated main-app + eval studies for compare and optimize workflows

The browser UI is the primary human workflow. The JSON config file remains the authoritative advanced-control surface.

## Quickstart

Run these commands from the repository root:

```bash
python scripts/papers_to_table.py install
python scripts/papers_to_table.py review
```

Then open `http://127.0.0.1:5173`.

## Most common commands

### Human-review main app

```bash
python scripts/papers_to_table.py review
python scripts/papers_to_table.py preflight --config app/config.json
```

### Headless extraction for agents or batch work

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

Use `--accept-all` only when you explicitly want unattended review bypass. The resulting artifacts record that proposals were auto-accepted and still need audit.

### Eval a run bundle

```bash
python scripts/papers_to_table.py eval \
  --run /absolute/path/to/run_bundle \
  --gold /absolute/path/to/gold.csv \
  --schema /absolute/path/to/schema.json \
  --out /absolute/path/to/eval_out
```

### Optimizer companion workflows

```bash
python scripts/papers_to_table.py optimizer compare-models
python scripts/papers_to_table.py optimizer optimize-one-model
python scripts/papers_to_table.py optimizer overnight
```

## Default runtime assumptions

- Default live provider path: **LM Studio** via config token `lm_studio`
- Default text model: `unsloth/gemma-4-26b-a4b-it`
- Default retrieval stack: `retrieval.mode=hybrid_experimental`, `retrieval.top_k=12`, recall rescue off, whole-document mode off
- Browser review remains the normal operator path
- Headless auto-accept is additive for agent and batch workflows only

## Outputs

- Main-app run bundles default to `app/runs/{run_id}/` unless config overrides `output_dir`
- Eval writes per-run and compare outputs under the `--out` directory you pass
- Optimizer writes experiment bundles under `tools/optimizer/runs/` unless you pass `--out`

## Documentation map

- Central install, commands, and navigation: [`docs/README.md`](docs/README.md)
- Human-review main app: [`docs/main-app/README.md`](docs/main-app/README.md)
- Headless and agent usage: [`docs/headless-agent.md`](docs/headless-agent.md)
- Config system reference: [`docs/configuration.md`](docs/configuration.md)
- Eval companion: [`docs/eval/README.md`](docs/eval/README.md)
- Optimizer companion: [`docs/optimizer/README.md`](docs/optimizer/README.md)
- Troubleshooting: [`docs/troubleshooting.md`](docs/troubleshooting.md)
- Spec system: [`specs/README.md`](specs/README.md)

## Troubleshooting

If LM Studio, parser readiness, or model loading looks wrong, run:

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

Then see [`docs/troubleshooting.md`](docs/troubleshooting.md).
