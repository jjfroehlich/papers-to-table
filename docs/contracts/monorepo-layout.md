# Monorepo Layout

This repository is organized around one primary product and two internal developer tools.

## Roles

- `app/`: the main app and primary product surface
- `tools/eval/`: internal benchmarking and scoring tool
- `tools/optimizer/`: internal calibration and orchestration tool
- `docs/`: product, tool, and contract documentation
- `benchmarks/`: shared benchmark documentation and future shared manifests
- `scripts/`: root-level convenience wrappers for common commands

## Layout

```text
repo/
  README.md
  benchmarks/
  docs/
    main-app/
    eval/
    optimizer/
    contracts/
  app/
  tools/
    eval/
    optimizer/
  scripts/
```

## Presentation policy

- The repository landing page is main-app-centric.
- Eval and optimizer are documented as companion internal tools, not as equal standalone products.
- Architecture remains intentionally separated by role: execution, scoring, and orchestration.
- No large shared runtime package is introduced by this layout.
