<task>
Assess whether this figure provides evidence for "$column_name".
</task>

<schema_guidance>
$column_description
</schema_guidance>

<field_contract>
$field_contract
</field_contract>

<caption_and_nearby_text>
$caption_block
$nearby_block
</caption_and_nearby_text>

<retrieved_and_reference_context>
$retrieval_block
$reference_block
$section_block
</retrieved_and_reference_context>

<figure_protocol>
1. Identify the relevant panel, label, axis, legend, annotation, caption phrase, or nearby sentence.
2. Verify that it matches the requested row context and field meaning.
3. Use state='found' for directly printed or caption-stated values.
4. Use state='inferred' for clear visual reading, simple unit conversion, or normalization from visible/stated values.
5. Use state='unclear' if the figure is only generally related, the panel/category is ambiguous, or the value is not visible enough to verify.
6. Preserve approximate/range semantics and avoid false precision.
7. Never use schema wording, type hints, blank-value conventions, or examples as evidence.
8. Return ONLY valid JSON matching the schema.
</figure_protocol>
