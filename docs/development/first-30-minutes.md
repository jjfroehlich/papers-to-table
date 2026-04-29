# First 30 minutes for contributors

From repo root:

```bash
git clone <repo>
cd papers-to-table
python scripts/papers_to_table.py install
python scripts/papers_to_table.py --help
```

## Main app quick checks
```bash
python scripts/papers_to_table.py preflight --config app/config.json
python scripts/papers_to_table.py review
python scripts/papers_to_table.py headless --config app/config.json --accept-all --export
```

## Contract sanity check
```bash
python scripts/papers_to_table.py verify-contract --run /abs/path/to/run_bundle
```

## Tests
```bash
bash scripts/test-main-backend.sh
bash scripts/test-main-frontend.sh
bash scripts/test-eval-tool.sh
bash scripts/test-optimizer-tool.sh
```

## Docs
```bash
python scripts/papers_to_table.py docs build
```

LM Studio dependent/live tests are optional; run them only when a local LM Studio endpoint and configured model are available.

Troubleshooting: `docs/operators/troubleshooting.md`.
