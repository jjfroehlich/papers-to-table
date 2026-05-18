Field to extract: $column_name
Schema guidance and table conventions (not evidence; do not copy into the answer unless the figure/caption states it): $column_description

$field_contract

$caption_block
$nearby_block

$retrieval_block
$reference_block
$section_block

Analyze the figure image. Does this figure provide evidence for the field above?
If yes, extract the value. If not, return state='unclear'.
If state is 'found' or 'inferred', proposed_value must contain the extracted answer itself. Do not leave proposed_value null, blank, or filled with a placeholder when returning found/inferred.
Never treat schema wording, type hints, blank-value conventions, or examples as evidence or as the proposed value by default.
If estimating or visually digitizing a value from a graph/plot, set numeric_value_form='approximate' or 'range' honestly and explain the visual basis briefly.
Return ONLY valid JSON matching the schema.
