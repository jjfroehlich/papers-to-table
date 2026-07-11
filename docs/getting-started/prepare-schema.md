# Prepare Table and Schema

The app needs a table and a schema that define which reported information needs to be extracted.

The table is the working spreadsheet. Each row is a paper, and each column is a field you want filled or checked. The app uses `Title`, `Authors`, and `Publication Year` to match PDFs to existing rows. If a PDF does not match any row, the app stages a new row from extracted paper metadata and generates proposals for the schema-defined target columns.

The schema is the extraction contract. Its descriptions are inserted into the extraction prompts, so they directly shape what the model looks for. Treat each description as prompt text: define the reported information precisely, say what counts as source evidence, and include units or scope boundaries. Target columns may describe technical parameters, reported results, or claims made by the publication. They should not ask the app to decide whether those claims are scientifically supported or true; connect downstream analysis systems for that task. It is often useful to ask an LLM to draft or refine these descriptions, then review them for domain correctness before running extraction.

## Table

Minimum columns:

```csv
Title,Authors,Publication Year,Species,Model system,Readout
Example paper title,"Smith, J.; Doe, A.",2024,,,
```

Use one row per paper when you already know the literature set. Leave target cells blank when you want proposals. Already pre-filled cells are skipped in normal mode, checked in `verify mode`, and masked in `eval mode`.

## Schema

Use a CSV with these columns, for example:

```csv
column_name,description
Species,Species used in the assay or model system.
Model system,Cell line or organism context used for the reported experiment.
```

Rules:

- `column_name` must match a table column exactly.
- `description` should define the paper-facing reported information and acceptable source evidence. These descriptions become model instructions, so unclear descriptions usually create unclear extractions.
- `field_type` can be `text`, `number`, `categorical`, or `boolean`.
- `allowed_values` is only for categorical fields and should be a JSON list.

For ordinary extraction tables, do not put `Title`, `Authors`, or `Publication Year` in the schema. Benchmark/eval datasets may include metadata columns in the schema when those fields are intentionally scored.

## Writing Good Descriptions

Schema descriptions are crucial because they are converted into model prompts. A vague description is a vague prompt. You can use an LLM to draft or improve these descriptions, but review them before running. The final schema should clarify what is being looked for and should not smuggle in default answers that might be used in hallucinations.

- Name the reported parameter, result, or claim, not the workflow step.
- Say what counts as source evidence in the publication.
- Include units, scope, and disambiguators.
- Prefer one extractable concept per column.
- Use categorical allowed values when the answer must come from a fixed set.
