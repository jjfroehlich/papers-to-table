# 2026-06-15 Model-Comparison Figures

The JPG boxplots in this directory are generated from:

```text
tools/optimizer/runs/20260615_004637_compare_models/compare/experiment/plots/suite_replicate_score_distribution.csv
```

Regenerate them from the repository root with:

```bash
python tools/optimizer/scripts/render_compare_model_docs_plots.py \
  --input-csv tools/optimizer/runs/20260615_004637_compare_models/compare/experiment/plots/suite_replicate_score_distribution.csv \
  --output-dir docs/plots/20260615_004637_compare_models_plots_v2
```

`20260615_004637_compare_models_plots_v2.ai` is the legacy manually curated source for the earlier unlabeled versions. It is retained as historical design material, but it is not the source of truth for the current generated JPGs.

`20260615_004637_compare_models_plots_v2_score_vs_runtime.jpg` is not a boxplot and is unchanged by the boxplot renderer.
