(placeholder here, needs to be completed)

## Writing Better Schema Descriptions

Treat the schema as the normal extraction contract, even when the table is mostly empty.

- Name the paper-facing fact, not the workflow step.
- Say what counts as evidence for the field.
- Add the unit, scope, or disambiguator when a short column name could mean multiple things.
- Prefer one extractable concept per column.
- For categorical fields, constrain the allowed values instead of relying on reviewer memory.

```csv
column_name,description,field_type,allowed_values
Species,Species used in the assay or model system.,categorical,"[""human"",""mouse"",""yeast""]"
Model system,Cell line or organism context used for the reported experiment.,text,
Number of Conditions,How many distinct experimental conditions were tested in the paper.,number,
Readout,Primary assay readout used to measure expression or activity.,categorical,"[""RNAseq"",""scRNAseq"",""FACS""]"
```