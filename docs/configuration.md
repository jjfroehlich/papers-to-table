# Configuration reference

This page explains how the app, eval companion, and optimizer companion are configured.

## Configuration surfaces

| Surface | Canonical source | What it controls |
| --- | --- | --- |
| Main app | `app/config.example.json` | Inputs, provider, parser, retrieval, diagnostics, output paths |
| Eval | CLI arguments to `paper-eval` | Run bundle selection, gold input, schema metadata, judge settings, eval output path |
| Optimizer | `tools/optimizer/configs/*.json` | Candidate lists, search space, benchmark manifests, main-app launch path, eval launch path, acceptance rules |

## Main app config

### Canonical files

- `app/config.example.json`: canonical checked-in template and fixture-backed example
- `app/config.json`: local machine config for real work

### Required top-level fields

- `table_path`
- `schema_path`
- `pdf_dir`
- `output_dir`
- `provider.token`
- `provider.text_model.model_id`

### Important optional sections

- `provider.base_url`
- `provider.vision_model`
- `parser.*`
- `matching.*`
- `prompt.bundle`
- `retrieval.*`
- `style_profiles.*`
- `figure_review.*`
- `diagnostics.*`

### Current defaults and norms

- provider token: `lm_studio`
- retrieval mode: `hybrid_experimental`
- retrieval top-k: `12`
- recall rescue: disabled
- whole-document mode: disabled
- default text model: `unsloth/gemma-4-26b-a4b-it`

### Minimal example

```json
{
  "table_path": "tests/fixtures/tables/literature_fixture.xlsx",
  "schema_path": "tests/fixtures/tables/literature_fixture_schema.csv",
  "pdf_dir": "tests/fixtures/papers",
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

## Eval configuration

Eval is CLI-first. There is no required JSON config file.

### Required arguments

- one `--run` or `--runs-root`
- `--gold`
- `--out`

### Common optional arguments

- `--schema`
- `--judge-model`
- `--judge-model-b`
- `--judge-api-base`
- `--judge-api-base-b`

### Default judge assumptions

Real benchmark studies should use two judges. Current documented defaults are:

- `judge_a=google/gemma-4-26b-a4b`
- `judge_b=openai/gpt-oss-20b`

## Optimizer configs

### Canonical preset families

| Preset | Purpose | Benchmark intent |
| --- | --- | --- |
| `compare_models.json` | canonical compare-models study | real benchmark when external benchmark paths are configured |
| `compare_prompts.json` | compare prompt bundles | real benchmark |
| `compare_retrieval.json` | compare retrieval settings | real benchmark |
| `compare_retrieval_modes.json` | compare retrieval modes | real benchmark |
| `optimize_one_model.json` | canonical focused single-model optimization | real benchmark dev benchmark |
| `compare_models_overnight.json` | overnight compare-model preset | real benchmark overnight |
| `optimize_overnight.json` | overnight optimization stage | real benchmark overnight |
| `compare_models_contract_smoke.json` | smoke contract check | fixture/smoke |
| `compare_models_fixture_manual.json` | deeper manual fixture check | fixture/manual |

### Benchmark intent labels

- **real benchmark**: expects non-fixture paths and meaningful development or overnight use
- **fixture/manual**: safe for checked-in examples and manual inspection
- **smoke**: minimal contract check, not meaningful benchmark evidence

### Optimizer config areas

- `baseline_candidate`
- `compare_candidates`
- `search_space`
- `benchmarks`
- `main_app`
- `eval_app`
- `acceptance`
- `optimize`
- `compare`

### Important interpretation rules

- `compare-models` ranks explicit candidate lists
- `optimize-one-model` starts from one baseline and proposes bounded challengers
- `overnight` chains several compare and optimize stages together
- benchmark winner and recommended default can differ when degraded-mode or trust caveats differ

## Common workflows

### Human review with the local app

- edit `app/config.json`
- run `python scripts/papers_to_table.py review`
- run preflight in the UI or terminal

### Headless batch extraction

- edit `app/config.json`
- run `python scripts/papers_to_table.py headless --config app/config.json --accept-all --export`

### Compare models

- review and adjust `tools/optimizer/configs/compare_models.json`
- run `python scripts/papers_to_table.py optimizer compare-models`

### Optimize one model

- review and adjust `tools/optimizer/configs/optimize_one_model.json`
- run `python scripts/papers_to_table.py optimizer optimize-one-model`
