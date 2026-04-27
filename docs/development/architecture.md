# Architecture (developer view)

High-level boundaries:

- `app/`: main extraction/review/export product
- `tools/eval/`: scoring companion
- `tools/optimizer/`: orchestration companion
- `specs/`: canonical implementation truth
- `docs/`: operator/developer manual (MkDocs + Markdown)

Use specs for normative behavior; use docs for operator workflows and practical run guidance.
