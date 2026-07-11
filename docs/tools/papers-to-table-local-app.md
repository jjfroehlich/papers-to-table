# Papers-To-Table Local App Skill

`skills/papers-to-table-local-app/` is the local-app skill for agents that can run this repo's installed app/headless workflow with a configured local LLM provider, usually LM Studio.

![Comparison of the local-app and agent-kit skills](../diagrams/refined_svg/04_agent_skills_refined.svg)

## Use Cases

Agents can use this skill when the task is to:

- extract structured values from one or several scientific PDF files into a configured table/schema
- run unattended or batch extraction through the app's headless command path
- preserve evidence, decisions, diagnostics, and exported workbook artifacts for audit

## Installation

Just tell your agent, for example `install the skill at https://github.com/jjfroehlich/papers-to-table/tree/main/skills/papers-to-table-local-app/`. Alternatively, copy `skills/papers-to-table-local-app/` into your agent system's skill directory. Keep the `references/` files with it.

## Preconditions

- The papers-to-table app is installed and runnable.
- A config JSON exists and points to valid table, schema, and PDF inputs.
- The configured local LLM provider is ready, usually LM Studio for the default path.

## Agent Will Do This

1. Confirm the app and local LLM provider are installed and runnable.
2. Run preflight for readiness and input resolution.
3. Inspect schema descriptions and improve vague descriptions before extraction; these descriptions are prompt instructions.
4. Run headless extraction.
5. Use `--accept-all` only when unattended acceptance is appropriate.
6. Inspect diagnostics and evidence artifacts before reporting results.
7. Report output table path plus reliability caveats.

## Command Pattern Agent will use

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

## Important Boundaries

- The skill depends on the installed local app and a configured LLM provider.
- If the app is not installed, the agent must install it or request that scope explicitly.
- Auto-accepted values are not human-reviewed.
- Provider readiness failures are blockers, not soft warnings.
- Source input tables must not be silently overwritten; exports are written as new artifacts.
