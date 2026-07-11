# Model Choice

Start with `google/gemma-4-e4b` unless you have a specific reason to choose another model. It is the checked-in default, the development reference used for current improvement work, and the simplest choice for a first run.

Model choice affects extraction quality, runtime, memory use, and structured-output reliability. A larger or slower model is not automatically better for every paper or field, so treat the choices below as practical starting points rather than universal rankings.

## Practical Choices

| Goal | Model | Guidance |
|---|---|---|
| Regular first run and current development default | `google/gemma-4-e4b` | Start here. It keeps runs comparable with current development checks and was the fastest of these four models in the 2026-06-15 comparison. |
| Stronger quality/runtime reference | `google/gemma-4-12b` | Use when the additional runtime is acceptable. It substantially improved the comparison score over e4b without being the slowest candidate. |
| Non-Gemma quality reference | `qwen/qwen3.6-27b` | Useful for model-family sensitivity checks, but it was considerably slower than regular Gemma 12B in this study. |
| Occasional slow quality ceiling | `google/gemma-4-12b-qat` | Highest-scoring tested local model in this comparison, but the modest gain over regular 12B came with much longer runtime. It is not the default. |

The measured study-level results were:

| Model | Content-correctness | Comparison runtime |
|---|---:|---:|
| `google/gemma-4-e4b` | 55.4% | 1.33 h |
| `google/gemma-4-12b` | 64.7% | 1.87 h |
| `qwen/qwen3.6-27b` | 65.6% | 3.25 h |
| `google/gemma-4-12b-qat` | 67.8% | 2.93 h |

These are results from optimizer run `20260615_004637_compare_models`, not promises for a single user run. The comparison covered three benchmark datasets, 15 papers, 31 target columns, and three replicates on the project's RTX 3090 workstation. Different papers, quantizations, context sizes, hardware, and app versions can change both quality and runtime.

## Quality Across Tested Candidates

![Scores for local models, external baselines, failures, and score-calibration controls](../plots/20260615_004637_compare_models_plots_v2/20260615_004637_compare_models_plots_v2_scores_of_all_candidates.jpg){ .figure-wide }

*Content-correctness scores from the 2026-06-15 model comparison. Gray points are replicate scores, blue lines are medians, and black lines are means. External agent baselines and gold-derived controls provide context but are not local model candidates. See [Interpreting benchmark scores](../tools/benchmark-datasets.md#interpreting-benchmark-scores) before treating the values as literal error rates.*

## Quality Versus Runtime

![Average benchmark score plotted against runtime for tested models](../plots/20260615_004637_compare_models_plots_v2/20260615_004637_compare_models_plots_v2_score_vs_runtime.jpg){ .figure-half }

*Average content-correctness versus comparison runtime for the same run. Local-model timings were measured on the benchmark workstation. The pale Codex points are external GPT-5.5 xhigh baselines and are not locally measured model runtimes.*

The main lesson is that more runtime did not consistently produce a higher score. Regular Gemma 12B offered a useful quality/runtime balance in this sweep, while e4b remains the current default for development continuity and faster iteration.

## Change And Check A Model

1. Download and load the model in LM Studio.
2. Set `provider.text_model.model_id` in `app/config.json` to the exact LM Studio model identifier.
3. Keep `provider.vision_model.model_id` aligned when you want the same model to handle targeted figure review, or configure a separate compatible vision model deliberately.
4. Run preflight before extraction:

```bash
python scripts/papers_to_table.py preflight --config app/config.json
```

For a controlled one-benchmark comparison, use the [Optimizer development check](../tools/optimizer.md#development-check) with `--model MODEL_ID` rather than comparing models from unrelated runs.
