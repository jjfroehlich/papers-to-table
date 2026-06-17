# Configuration

The main app uses JSON as the advanced-control authority.

## Configuration Files

- `app/config.example.json`: template config.
- `app/config.json`: config for real runs.

## Minimal Example

```json
{
  "table_path": "../benchmark_datasets/massively_parallel_reporter_assays/table_template.csv",
  "schema_path": "../benchmark_datasets/massively_parallel_reporter_assays/schema.csv",
  "pdf_dir": "../benchmark_datasets/massively_parallel_reporter_assays/pdfs",
  "output_dir": "./runs",
  "provider": {
    "token": "lm_studio",
    "base_url": "http://localhost:1234",
    "text_model": {
      "model_id": "google/gemma-4-e4b"
    }
  }
}
```
Default model provider path is LM Studio at the moment (`provider.token = "lm_studio"`).
The `model_id` must match the model you downloaded or loaded in LM Studio.

## Current Defaults

- provider token: `lm_studio`
- default vision model: `google/gemma-4-e4b`
- retrieval mode: `hybrid_experimental`
- retrieval top-k: `12`
- recall rescue: disabled
- whole-document mode: disabled
- figure review: disabled (code default); enabled in the example config
- prompt-only vision review: enabled by default when figure review is enabled
- candidate selection: enabled, max one selector call per cell
- default text model: `google/gemma-4-e4b`

## Most Important Parameters

**Input / output**

- `table_path`: the workbook or table you want to fill.
- `schema_path`: the schema that tells the app what each column means.
- `pdf_dir`: the folder containing the source PDFs.
- `output_dir`: where run bundles and exported results are written.

**Provider**

- `provider.base_url`: the local provider endpoint, usually LM Studio (`http://localhost:1234`).
- `provider.text_model.model_id`: the text model used for extraction. 
- `provider.vision_model.model_id`: the vision model used for figure review. 

**Matching**

- `matching.ambiguity_threshold`: how strictly the metadata (title, authors, journal) extracted from a .pdf must match a row before the app flags the match as ambiguous. Lower values (e.g. `0.1`) stricter; higher values (e.g. `0.9`) more permissive.

**Retrieval**

- `retrieval.mode`: how the app builds context for extraction. Two modes are supported: `hybrid_experimental` (default) blends BM25 frequency scoring with a query-term recall component (what fraction of the query's distinct terms appear in a chunk) — weighted 0.7 BM25 + 0.3 recall; `lexical` uses BM25 scoring only. 
- `retrieval.top_k`: how many chunks to include in the extraction context. Default is `12`. 
- `retrieval.recall_rescue_enabled`: whether to do an extra retrieval pass when the initial context looks weak. Disabled by default. 
- `retrieval.whole_document_mode`: whether to fall back to feeding the whole document when retrieval confidence is low. Disabled by default. 
- `retrieval.whole_document_max_chars`: maximum characters to include when `whole_document_mode` is active or triggered by recall rescue. Default is `40000`. 
- `provider.text_model.working_context_budget`: total character budget reserved for the assembled extraction context (retrieved chunks + style examples). The example config uses `25000` for a 32k context window. 
- `provider.text_model.load_context_length`: the context window size to request when loading the text model. Defaults to `null` (derived from `working_context_budget`). When set explicitly, must be ≥ `working_context_budget`. 
- `style_profiles.enabled`: create style examples from existing values in a column, to improve the extraction prompts. Enabled by default. 
- `figure_review.enabled`: vision-model pass over targeted figures. Enabled in the example config, disabled by the code default.
- `figure_review.skip_when_prompt_only_degraded`: when `false`, a vision-capable model may still run with prompt-only JSON if structured vision JSON schema is unavailable. Default is `false`.
- `figure_review.planner_enabled`: when `true`, run one generic text-only planner before figure review to decide whether vision is needed and which figure images to inspect. Default is `true`.
- `figure_review.max_planner_calls_per_cell`: hard cap on planner calls per cell. Default is `1`.
- `figure_review.max_figures_per_cell`: maximum shortlisted figures inspected for one cell. Default is `2`.
- `figure_review.max_calls_per_cell`: hard cap on actual vision calls per cell. Default is `2`.
- `figure_review.max_retries_per_cell`: intended cap for figure-review structured-output retries. Prompt-only schema issues that can be repaired locally are not retried; malformed JSON gets at most one retry. Default is `1`.
- `extraction.candidate_selection_enabled`: when `true`, the app can run one generic selector call if collected candidates conflict or evidence is weak. Default is `true`.
- `extraction.max_candidate_selection_calls_per_cell`: hard cap on selector calls per cell. Default is `1`.

Retrieval includes figure-level chunks built from parsed figures when available. The app does not create panel-level retrieval chunks. Runs also write prepared per-paper retrieval indexes under `retrieval/_indexes/`; these are generated run artifacts with document fingerprints and source counts, not authored configuration. Figure review uses valid crops by default, falls back to full-page images when crops are missing or suspicious, and can prefer full-page images when the planner identifies layout or panel-counting work.

Figure review is evidence-gated. Direct figure context is not enough by itself to call vision for a strong non-visual text answer. Vision remains available for weak, unresolved, missing, or contradictory text evidence, and for genuinely visual requests with promising figure retrieval. Prompt-only vision parsing repairs recoverable schema issues, including optional missing diagnostics and invalid `numeric_value_form` values such as `N/A`. If a figure response proposes a value, its `proposed_value` must contain the extracted answer.

Recall rescue is selective and bounded to one extra rescue pass per cell. Whole-document fallback only runs when enabled and under `retrieval.whole_document_max_chars`; it is not a default path for every difficult cell.

Candidate selection is also bounded. It compares existing text, rescue, evidence-recovery, and figure-review candidates, and should not let related but semantically mismatched figure evidence override a strong text answer.

**Diagnostics**

- `diagnostics.verbose_provider_logging`: record detailed provider request/response logs in the run bundle. Useful for debugging and development.
- Run diagnostics include prepared-index source counts, figure planner counts and skip reasons, actual vision calls, image-source/fallback reasons, retry/repair details, dropped/no-hit reasons, accepted figure hits, successful vision calls without usable hits, candidate-selection outcomes, recall-rescue eligibility/use/skips, and whole-document eligibility/use/skips.
