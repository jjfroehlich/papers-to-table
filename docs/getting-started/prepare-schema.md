# Prepare Table and Schema

The app needs a table and a schema that define which information needs to be extracted.

The table is the working spreadsheet. Each row is a paper, and each column is a field you want filled or checked. The app uses `Title`, `Authors`, and `Publication Year` to match PDFs to existing rows. If a PDF does not match any row, the app stages a new row from extracted paper metadata and generates proposals for the schema-defined target columns.

The schema is the extraction contract. It tells the model what each target column means, what evidence is acceptable, and whether the value should be text, numeric, boolean, or categorical.

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
- `description` should define the paper-facing fact and acceptable evidence.
- `field_type` can be `text`, `number`, `categorical`, or `boolean`.
- `allowed_values` is only for categorical fields and should be a JSON list.

Do not put `Title`, `Authors`, or `Publication Year` in the schema.

## Writing Better Descriptions

- Name the fact, not the workflow step.
- Say what counts as evidence.
- Include units, scope, and disambiguators.
- Prefer one extractable concept per column.
- Use categorical allowed values when the answer must come from a fixed set.
