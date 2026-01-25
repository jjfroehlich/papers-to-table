You are verifying whether the provided evidence supports a proposed value for a column.
Return JSON only (no markdown). Example:
{"column": "Accuracy", "status": "supports", "rationale": "Quote states the same value.", "needs_more_evidence": false}
Rules:
- If evidence directly supports the proposed value, return supports.
- If evidence contradicts the proposed value, return contradicts.
- If evidence is missing or ambiguous, return unclear with needs_more_evidence true.

Column:
{{column}}
Proposed value:
{{proposed_value}}
Evidence:
{{evidence}}
