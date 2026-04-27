# GitHub Pages (future)

MkDocs Material is configured for local/static docs generation now.

## Local preview

```bash
python scripts/papers_to_table.py docs serve
```

## Static build

```bash
python scripts/papers_to_table.py docs build
```

Generated static site output is in `site/` by default.

## Later deployment idea

When ready, add a CI workflow that runs `mkdocs build` and publishes `site/` to GitHub Pages.

This repo intentionally does not force deployment configuration yet.
