# Prepare Table and Schema

The app needs a table and a schema that define which information needs to be extracted.

## Table

Each row is a paper, and each column is a field you want filled or checked. The app uses `Title`, `Authors`, and `Publication Year` to match PDFs to existing rows. If a PDF does not match any row, the app makes a new row from extracted paper metadata.

Minimum columns:

```csv
Title,Authors,Publication Year,(followed by columns for extracted information)
Example paper title,"Smith, J.; Doe, A.",2024,(followed by empty fields for extracted information)
```

Leave cells blank where you want the system to extract information ("proposal"). Already pre-filled cells are skipped in normal mode, and checked in `verify mode`. 

Example:

```csv
Title,Authors,Publication Year, Species, Model system, DNA extraction kit
Example paper title,"Smith, J.; Doe, A.",2024, , ,
```

## Schema

The schema is the extraction contract. Its descriptions are used for the extraction prompts, so they define what the LLM looks for. Treat each description as prompt text: define the reported information precisely, and optionally say what counts as source evidence, and include units or scope boundaries. Of course you can ask an LLM to draft or refine these schema descriptions.

Use a CSV with these columns, for example:

```csv
column_name,description
Species,Species used in the assay or model system.
Model system,Cell line or organism context used for the reported experiments.
DNA extraction kit,Name of the DNA extraction kit used for genomic DNA extraction.
```

Do not put `Title`, `Authors`, or `Publication Year` in the schema, these fields are automatically handled by the app.

Rules:

- `column_name` must match a table column name exactly.
- `description` should define the desired information and acceptable source evidence. 

Optional columns:
- `field_type` can be `text`, `number`, `categorical`, or `boolean`.
- `allowed_values` is only for categorical fields and should be a JSON list.


## Writing Good Descriptions

Schema descriptions are crucial because they are converted into model prompts. A vague description is a vague prompt. You can use an LLM to draft or improve these descriptions, but review them before running. The final schema should clarify what is being looked for but should not smuggle in default answers that might be used in hallucinations!

- Name the reported parameter, result, or claim, not the workflow step.
- Say what counts as source evidence in the publication.
- Include units, scope, and disambiguators.
- Prefer one extractable concept per column.
- Use categorical allowed values when the answer must come from a fixed set.
