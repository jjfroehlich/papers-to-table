# LM Studio operator notes

papers-to-table is local-first by default and currently documents LM Studio as the primary live provider path.

## Expectations

- Config token: `lm_studio`
- Provider must be reachable before extraction starts
- Readiness failures should be explicit (not silent fallback)

## Quick check

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

If readiness fails, resolve LM Studio/model setup before extraction.
