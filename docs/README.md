# papers-to-table documentation

This directory is the source for the local/static MkDocs Material site.

## Build And Preview

Install docs dependencies:

```bash
python -m pip install -r tools/docs/requirements.txt
```

Serve locally:

```bash
python scripts/papers_to_table.py docs serve
```

Build static site:

```bash
python scripts/papers_to_table.py docs build
```

Direct MkDocs commands from the repo root:

```bash
mkdocs serve -f tools/docs/mkdocs.yml
mkdocs build -f tools/docs/mkdocs.yml
```