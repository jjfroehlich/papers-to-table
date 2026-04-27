# Agent usage

This page explains how coding/automation agents should use papers-to-table.

## What agents should do

1. Confirm the app is installed and runnable in the environment.
2. Run preflight for readiness and input resolution.
3. Run headless extraction.
4. Use `--accept-all` only when explicitly requested or clearly appropriate.
5. Inspect diagnostics and evidence artifacts before reporting results.
6. Report output table path plus reliability caveats.

## Important boundaries

- The skill is an operating procedure, not an installer.
- If the app is not installed, the agent must install it or request that scope explicitly.
- Auto-accepted values are not human-reviewed.
- Local LM Studio readiness is usually required for live proposal generation.

## Related

- Skill package: [papers-to-table-skill.md](papers-to-table-skill.md)
- Headless details: [`../main-app/headless.md`](../main-app/headless.md)
