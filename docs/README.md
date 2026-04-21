# Documentation map

## Pick the right entrypoint

- **Product / repo overview**: [`../README.md`](../README.md)
- **Operator docs**: [`main-app/README.md`](main-app/README.md)
- **Contributor quickstart**: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- **Coding-agent and maintainer rules**: [`../AGENTS.md`](../AGENTS.md)
- **Normative spec system**: [`../specs/README.md`](../specs/README.md)
- **Glossary and examples**: [`glossary.md`](glossary.md)

## Main doc groups

- `main-app/`: browser workflow, run artifacts, screenshots, and operator guidance
- `architecture-decisions/`: concise ADRs for durable repo decisions
- `contracts/`: implementation notes and historical migration docs for repo structure
- `engineering-lessons/`: reusable engineering lessons discovered during implementation
- `eval/` and `optimizer/`: companion tool docs

## Editing guidance by audience

- Product or operator workflow change -> update `README.md`, `docs/main-app/`, and the owning spec file.
- Contributor workflow change -> update `CONTRIBUTING.md`, `AGENTS.md`, and any affected wrapper-script docs.
- Normative behavior or contract change -> update `specs/` first, then sync user-facing docs.
- UI change -> update screenshots and `docs/main-app/operator-workflow.md`.
