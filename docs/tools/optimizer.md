# Optimizer companion

Optimizer orchestrates repeated main-app + eval studies.

Canonical workflows:

```bash
python scripts/papers_to_table.py optimizer compare-models
python scripts/papers_to_table.py optimizer optimize-one-model
python scripts/papers_to_table.py optimizer overnight
```

Use optimizer for bounded model/prompt/retrieval studies and winner recommendations.

Detailed reference: [`../optimizer/README.md`](../optimizer/README.md).
