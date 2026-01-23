You are verifying whether the provided evidence supports a proposed value for a column.
Return JSON: {"column": ..., "status": "supports|contradicts|unclear", "rationale": "...", "needs_more_evidence": bool}
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
