# Eval companion

Eval scores main-app run bundles against gold data.

Run it from the repo-level command surface:

```bash
python scripts/papers_to_table.py eval \
  --run /absolute/path/to/run_bundle \
  --gold /absolute/path/to/gold.csv \
  --schema /absolute/path/to/schema.json \
  --out /absolute/path/to/eval_out
```

Use eval when you need correctness/evidence metrics or run-to-run comparison outputs.

Detailed reference: [`../eval/README.md`](../eval/README.md).
