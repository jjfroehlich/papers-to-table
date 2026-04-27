# papers-to-table documentation

This directory is both:

1. a readable Markdown manual on GitHub, and
2. the source for a local/static MkDocs Material site.

## Build and preview the manual

Install docs dependencies:

```bash
python -m pip install -r requirements-docs.txt
```

Serve locally:

```bash
python scripts/papers_to_table.py docs serve
```

Build static site:

```bash
python scripts/papers_to_table.py docs build
```

You can also run `mkdocs serve` and `mkdocs build` directly from the repo root.

## Manual navigation start

- Site home: [`index.md`](index.md)
- Getting started: [`getting-started/index.md`](getting-started/index.md)
- Main app: [`main-app/overview.md`](main-app/overview.md)
- Companion tools: [`tools/eval.md`](tools/eval.md), [`tools/optimizer.md`](tools/optimizer.md)
- Agents: [`agents/agent-usage.md`](agents/agent-usage.md)
- Development/spec boundaries: [`development/specs.md`](development/specs.md)

## Existing deep references

The existing detailed pages remain part of the manual and are linked from the new navigation:

- main-app walkthrough and artifacts under `docs/main-app/`
- configuration details in [`configuration.md`](configuration.md)
- troubleshooting in [`troubleshooting.md`](troubleshooting.md)
- eval/optimizer deep references under `docs/eval/` and `docs/optimizer/`
