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
      "model_id": "unsloth/gemma-4-26b-a4b-it"
    }
  }
}
```
Default model provider path is LM Studio at the moment (`provider.token = "lm_studio"`).
The `model_id` must match the model you downloaded or loaded in LM Studio.

## Current Defaults

- provider token: `lm_studio`
- default vision model: `unsloth/gemma-4-26b-a4b-it`
- retrieval mode: `hybrid_experimental`
- retrieval top-k: `12`
- recall rescue: disabled
- whole-document mode: disabled
- figure review: disabled (code default); enabled in the example config
- default text model: `unsloth/gemma-4-26b-a4b-it`

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
- `figure_review.enabled`: vision-model pass over figures. Enabled by default. 

**Diagnostics**

- `diagnostics.verbose_provider_logging`: record detailed provider request/response logs in the run bundle. Useful for debugging and development.
