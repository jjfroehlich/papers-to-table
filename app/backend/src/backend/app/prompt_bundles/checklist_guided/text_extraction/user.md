<task>
Extract the field "$column_name" for the paper row below.
</task>

<schema_guidance>
$column_description
</schema_guidance>

<row_context>
$row_block$verify_block$long_text_note$field_contract$style_block
</row_context>

<retrieved_evidence>
$context_block
</retrieved_evidence>

<whole_document_context>
$whole_document_block
</whole_document_context>

<extraction_protocol>
1. Identify the strongest evidence snippets that mention the requested field or its close synonym.
2. Check whether each candidate snippet matches the row context, including entity, assay, species, cell type, condition, timepoint, and measurement when those details are relevant.
3. If a snippet directly states the value for this row-field pair, return state='found'.
4. If the value follows by a short deterministic calculation, unit conversion, or normalization from stated values, return state='inferred'.
5. If no snippet passes the row-field match, or if the evidence is conflicting or only topical, return proposed_value=null and state='unclear'.
6. Preserve the source value form honestly: units, ranges, inequalities, approximate wording, categorical qualifiers, and condition labels.
7. Include short verbatim quotes from the supplied evidence that let a reviewer verify the answer.
8. Rationale must be <=3 concise markdown bullets and should mention why the evidence passes or fails the row-field match.
9. Never use schema wording, type hints, blank-value conventions, or examples as evidence.
10. Only set numeric_value_form when the field is numeric; otherwise return null.
11. Return ONLY valid JSON matching the schema.
</extraction_protocol>
