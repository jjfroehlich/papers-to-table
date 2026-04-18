Extract: $column_name
Schema guidance and table conventions (not evidence; do not copy into the answer unless the paper states it): $column_description

Paper row context:
$row_block$verify_block$long_text_note$field_contract$style_block

$context_block

$whole_document_block

Decision policy:
1. Use the row context as a hard filter for relevance.
2. Prefer values that are explicitly stated in retrieved text, tables, or captions.
3. Use state='found' only when the value is directly stated for this row context.
4. Use state='inferred' only for short deterministic calculations from stated numbers that still fit this row context.
5. If evidence is conflicting, indirect, under-specified, or tied to a different context, return proposed_value=null and state='unclear'.
6. Preserve the paper's value form honestly, including units, exact vs range vs approximate wording, and categorical qualifiers.
7. Evidence quotes should be short, verbatim, and chosen because they directly support the answer.
8. Rationale must explain why the selected evidence matches the requested row context.
9. Never fabricate quotes and never use schema wording, type hints, blank-value conventions, or examples as evidence.
10. Return ONLY valid JSON matching the schema.