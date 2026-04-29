# Quickstart

> From a fresh clone, run `python scripts/papers_to_table.py install` first. See [Installation](installation.md).

## Browser review workflow (recommended)

```bash
python scripts/papers_to_table.py review
```

Then open `http://127.0.0.1:5173`.

## Terminal preflight

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

## Headless extraction

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

`--accept-all` means proposals are auto-accepted by automation, not by human review.

## Companion tools

```bash
python scripts/papers_to_table.py eval --run /abs/run --gold /abs/gold.csv --schema /abs/schema.json --out /abs/eval_out
python scripts/papers_to_table.py optimizer compare-models
python scripts/papers_to_table.py optimizer optimize-one-model
python scripts/papers_to_table.py optimizer overnight
```
