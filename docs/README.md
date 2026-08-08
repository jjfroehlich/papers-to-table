# papers-to-table documentation

This directory is the source for the local/static MkDocs Material site. The
repository-root `.readthedocs.yaml` also makes the same site deployable on Read
the Docs without changing the local workflow.

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

## Read the Docs Hosting

The checked-in `.readthedocs.yaml` configures Read the Docs to:

- build on Ubuntu 24.04 with Python 3.12;
- install the pinned documentation dependencies from
  `tools/docs/requirements.txt`; and
- build the manual from `tools/docs/mkdocs.yml`.

After the repository is public, import it into Read the Docs Community through
the Read the Docs GitHub integration. Community projects and their generated
documentation are public. Hosting directly from a private repository requires
Read the Docs Business instead.

Before importing into Read the Docs Community:

1. make the GitHub repository public;
2. add or confirm the intended open-source license; and
3. commit and push `.readthedocs.yaml` together with the MkDocs configuration,
   requirements, and documentation sources.

Read the Docs supplies `READTHEDOCS_CANONICAL_URL` during hosted builds. The
MkDocs configuration uses it as the canonical site URL while keeping the local
build valid when that variable is absent.
