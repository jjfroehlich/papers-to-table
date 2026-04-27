# papers-to-table agent skill

The repository ships a reusable `/skill`-style package at:

- `agent-skills/papers-to-table/SKILL.md`

## Installation/copy guidance

Copy `agent-skills/papers-to-table/` into your agent system’s skill directory (or register it in that system’s equivalent skill catalog).

Keep the `references/` files with it; the main SKILL file links to those compact operational notes.

## What the skill covers

- when to use papers-to-table for headless extraction
- required inputs and command pattern
- diagnostics and warnings to inspect before reporting
- reporting checklist with reliability caveats
- explicit warning that `--accept-all` is automation, not human review

The skill is intentionally small and links back to this manual for broader context.
