Field to extract: $column_name
Schema guidance and table conventions (not evidence; do not copy into the answer unless the figure/caption states it): $column_description

$field_contract

$caption_block
$nearby_block

$retrieval_block
$reference_block
$section_block

Analyze the figure image.
1. First decide whether this figure is truly about the requested field and row context.
2. Prefer explicit values, labels, legends, captions, or visually unambiguous comparisons.
3. If the figure only gives weak, indirect, or ambiguous support, return state='unclear'.
4. If estimating from a graph or plot, set numeric_value_form='approximate' or 'range' honestly.
5. Never use schema wording, type hints, blank-value conventions, or examples as evidence.
6. Return ONLY valid JSON matching the schema.