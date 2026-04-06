Extract: $column_name
Field description: $column_description

Paper row context:
$row_block$verify_block$long_text_note$field_contract$style_block

$context_block

$whole_document_block

Instructions:
1. Return proposed_value=null and state='unclear' if the paper does not clearly support a value.
2. Use state='found' for directly stated values, 'inferred' for derived/reasoned values.
3. Include one or more evidence quotes when they are genuinely needed to support the value.
4. Rationale must be <=3 concise markdown bullets (- bullet text).
5. Never fabricate quotes; only use text that appears in the passages above.
6. Only set numeric_value_form when the field is numeric; otherwise return null.
7. Return ONLY valid JSON matching the schema.
