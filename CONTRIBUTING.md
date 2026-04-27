# Contributing

Thanks for contributing to papers-to-table.

## Start here

- Repo overview and common commands: [`README.md`](README.md)
- Documentation home: [`docs/README.md`](docs/README.md)
- Human-review workflow: [`docs/main-app/README.md`](docs/main-app/README.md)
- Agent/headless workflow: [`docs/headless-agent.md`](docs/headless-agent.md)
- Repo operating rules: [`AGENTS.md`](AGENTS.md)
- Spec system: [`specs/README.md`](specs/README.md)

## Quick local setup

Run these from the repository root:

```bash
python scripts/papers_to_table.py install
```

## Common commands

```bash
python scripts/papers_to_table.py review
python scripts/papers_to_table.py preflight --config app/config.json
python scripts/papers_to_table.py headless --config app/config.json --accept-all --export
python scripts/papers_to_table.py optimizer compare-models
```

Lower-level wrapper scripts still exist under `scripts/` when you need backend-only or frontend-only control.

## When you change code

- Update the owning docs and specs in the same pass when repo truth changes.
- Keep screenshots current when UI behavior changes materially.
- Prefer the central command surface in `scripts/papers_to_table.py` for repo-wide workflows.
- Run the relevant existing tests before you finish.

## Where things live

- Main app backend: `app/backend/src/backend/app/`
- Main app frontend: `app/frontend/src/`
- Main app tests: `app/tests/`
- Eval companion: `tools/eval/`
- Optimizer companion: `tools/optimizer/`
- User docs: `docs/`
- Specs: `specs/`
