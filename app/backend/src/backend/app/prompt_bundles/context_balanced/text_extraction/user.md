Extract: $column_name
Schema guidance and table conventions (not evidence; do not copy into the answer unless the paper states it): $column_description

Paper row context:
$row_block$verify_block$long_text_note$field_contract$style_block

$context_block

$whole_document_block

Decision policy:
1. First identify which retrieved passages, tables, captions, or whole-document context match the requested row entity, assay, species, cell type, condition, timepoint, and measurement.
2. Use state='found' when a value is directly stated in matching evidence.
3. Use state='inferred' for short deterministic calculations, unit conversions, or normalization from stated values when the source values clearly match the row context.
4. Prefer extracting a supported value over returning unclear when the evidence is specific enough for a reviewer to verify it.
5. Return proposed_value=null and state='unclear' when evidence is absent, only topical, contradictory, or tied to a materially different row context.
6. Preserve the paper's value form honestly, including units, exact vs approximate wording, ranges, inequalities, and categorical qualifiers.
7. Include short verbatim evidence quotes that let a reviewer verify the answer; use quotes from the passages above only.
8. Rationale must be <=3 concise markdown bullets and explain the match between evidence and row context.
9. Never fabricate quotes and never use schema wording, type hints, blank-value conventions, or examples as evidence.
10. Only set numeric_value_form when the field is numeric; otherwise return null.
11. Return ONLY valid JSON matching the schema.
