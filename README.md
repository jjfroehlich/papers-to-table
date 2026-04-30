# papers-to-table

![papers-to-table banner](app/frontend/public/banner_1.jpg)

papers-to-table is a local-first app that extracts evidence-backed values from scientific PDFs into structured tables, keeps review in a browser UI, and exports audited workbook updates.

The monorepo also includes:

- **eval** companion (scores run bundles)
- **optimizer** companion (orchestrates compare/optimize studies)

## Quickstart

From the repository root:

```bash
python scripts/papers_to_table.py install
python scripts/papers_to_table.py review
```

Then open `http://127.0.0.1:5173`.

## Core commands

### Docs manual

```bash
python -m pip install -r tools/docs/requirements.txt
python scripts/papers_to_table.py docs serve
python scripts/papers_to_table.py docs build
```

### Main app (browser review)

```bash
python scripts/papers_to_table.py review
python scripts/papers_to_table.py preflight --config app/config.json
```

### Headless extraction

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

⚠️ `--accept-all` bypasses human review. Auto-accepted values are not human-reviewed and must be audited via run artifacts.

### Eval

```bash
python scripts/papers_to_table.py eval \
  --run /absolute/path/to/run_bundle \
  --gold /absolute/path/to/gold.csv \
  --schema /absolute/path/to/schema.json \
  --out /absolute/path/to/eval_out
```

### Optimizer

```bash
python scripts/papers_to_table.py optimizer compare-models
python scripts/papers_to_table.py optimizer optimize-one-model
python scripts/papers_to_table.py optimizer overnight
```

## Documentation and specs

- Manual home: [`docs/index.md`](docs/index.md)
- Manual map: [`docs/README.md`](docs/README.md)
- Agent skill: [`docs/agents/papers-to-table-skill.md`](docs/agents/papers-to-table-skill.md)
- Specs (canonical implementation truth): [`specs/README.md`](specs/README.md)

Use docs for operator guidance and specs for canonical rebuild-grade behavior.
