# Home

papers-to-table is a local-first system for extracting reported information from scientific PDFs into structured tables. Target fields can ask for technical parameters, descriptions of results, or claims made in a publication. The app links proposals to inspectable source evidence for human review, but it does not evaluate whether publication claims are scientifically supported or true. It combines a browser review app for human review, auditable run bundles, and companion tools for getting benchmarking scores and for optimizing parameters.

Papers-to-table uses local LLMs to extract structured information from scientific documents with measurable accuracy on the project's checked-in benchmarks.

<img src="plots/20260615_004637_compare_models_plots_v2/20260615_004637_compare_models_plots_v2_main_plot_docs.jpg" alt="Benchmark score distributions for local papers-to-table models and Codex with the agent-kit skill" class="figure-half" width="50%" />

*Content-correctness [Eval scores](tools/eval.md) from the 2026-06-15 three-dataset comparison. Points are replicate-level scores, boxes show their distribution, black lines mark means, and the numbers above the boxes give those means to one decimal percentage point. The commercial comparison is Codex with GPT-5.5 xhigh using the papers-to-table agent-kit skill; results are specific to optimizer run `20260615_004637_compare_models`. Scores measure agreement with the current gold answers and rubric, not a literal percentage of objectively right and wrong values; see [Interpreting benchmark scores](tools/benchmark-datasets.md#interpreting-benchmark-scores).*

## What The System Does

- Reads one spreadsheet, one schema, and a directory of PDFs.
- Runs preflight checks before extraction starts.
- Parses and matches PDFs to table rows.
- Proposes source-linked values for eligible cells.
- Lets a reviewer accept, edit, reject, or confirm no data.
- Exports a content-only workbook copy plus audit artifacts.

## Primary Workflow

1. Browser mode is the regular workflow which includes human-review or accept-all options.

![Technical papers-to-table workflow](diagrams/refined_svg/01_readme_overview_refined.svg)

## Secondary Workflows

1. Command-line interface usage without human-review for agent use or other programmatic use-cases. 
2. Eval tool scores run bundles against benchmark "gold" data.
3. Optimizer tool compares model, prompt, and retrieval studies.

## Agent Skills

1. "local-app" skill so that an agent can use the locally installed app with LM Studio.
2. "agent-kit" skill, a standalone skill that enables information extraction and human-review interface for commercial agents such as Codex or Claude.
