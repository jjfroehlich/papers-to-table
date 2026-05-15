Field to extract: $column_name
Schema guidance and table conventions (not evidence; do not copy into the answer unless the figure/caption states it): $column_description

$field_contract

$caption_block
$nearby_block

$retrieval_block
$reference_block
$section_block

Analyze the figure image and decide whether it supports the requested field.
1. Use caption, labels, legends, panel titles, axes, annotations, and nearby/retrieved text to determine whether the figure matches the row context.
2. Prefer explicit numeric or categorical values when visible in labels, tables, annotations, or captions.
3. If the value must be read from a graph, extract it only when the visual basis is clear; set numeric_value_form='approximate' or 'range' honestly.
4. If the figure supports direction or category but not an exact number, preserve that form rather than inventing precision.
5. Return state='unclear' when the figure is ambiguous, the relevant panel cannot be identified, or the evidence appears to describe a different context.
6. Never use schema wording, type hints, blank-value conventions, or examples as evidence.
7. Return ONLY valid JSON matching the schema.
