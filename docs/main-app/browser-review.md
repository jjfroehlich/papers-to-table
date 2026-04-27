# Browser review workflow

Start the app:

```bash
python scripts/papers_to_table.py review
```

Then open `http://127.0.0.1:5173`.

Recommended flow:

1. Run preflight and confirm resolved inputs and provider readiness.
2. Start extraction.
3. Review queue proposals and evidence.
4. Accept/edit/reject/confirm no-data decisions explicitly.
5. Export reviewed updates.

Useful command:

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

Detailed walkthrough and screenshots: [`README.md`](README.md) and [`operator-workflow.md`](operator-workflow.md).
