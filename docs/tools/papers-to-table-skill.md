# /papers-to-table Skill

The project ships an agent skill at `agent-skills/papers-to-table/SKILL.md`.

## Use cases

Agents can use the /papers-to-table skill when the task is to:

- extract structured values from one or several scientific publications, for which .pdf files need to be available
- preserve evidence and diagnostics for later audit
- produce a table with structured information from scientific publications and .pdf documents. 

## Installation Or Registration

Copy `agent-skills/papers-to-table/` into your agent system's skill directory, or register it in that system's equivalent skill catalog. Keep the `references/` files with it.

## Agent Workflow

The agent should then: 

1. Confirm the papers-to-table app and LM Studio with a good LLM model is installed and runnable in the environment.
2. Run preflight for readiness and input resolution.
3. Inspect schema descriptions and improve vague descriptions before extraction; these descriptions are prompt instructions.
4. Run headless extraction.
5. Use `--accept-all`, this skips the human review of the extracted values.
6. Inspect diagnostics and evidence artifacts before reporting results.
7. Report output table path plus reliability caveats.

## Command Pattern

```bash
python scripts/papers_to_table.py headless \
  --config app/config.json \
  --accept-all \
  --export
```

## Important Boundaries

- The skill is an operating procedure, not an installer.
- If the app is not installed, the agent must install it or request that scope explicitly.
- Auto-accepted values are not human-reviewed.
- Local LM Studio readiness is usually required for live proposal generation.

## Reporting Checklist

An agent report should include:

- run id
- run-bundle path
- exported workbook path when export was done
- whether `--accept-all` was used
- proposal/review counts from `summaries/reviewer_summary.json`
- relevant warnings from `summaries/run_summary.json`
- reliability caveats for degraded provider, matching, parsing, or evidence quality

## Files To Inspect Before Reporting

- `run.json`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `review/decisions.jsonl`
- `exports/audit_log_*.json`
- `exports/diagnostics_*.json`
