from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.models import GroupExtractionResult, VerifyResult
from paper_table_agent.llm.prompts import render_prompt


@dataclass
class GroupContext:
    name: str
    columns: list[str]
    schema: dict[str, str]
    examples: dict[str, list[dict[str, str]]]


def extract_group(
    client: LlmClient,
    row_context: dict[str, Any],
    group: GroupContext,
    chunks: list[dict[str, Any]],
    mapping_dependent: bool,
) -> GroupExtractionResult:
    prompt = render_prompt(
        "extract_group.md",
        row_context=json.dumps(row_context, indent=2),
        group_schema=json.dumps(group.schema, indent=2),
        examples=json.dumps(group.examples, indent=2),
        chunks=json.dumps(chunks, indent=2),
    )
    result = client.complete_json(prompt, GroupExtractionResult)
    for proposal in result.proposals:
        proposal.flags.setdefault("mapping_dependent", mapping_dependent)
        _apply_evidence_rules(proposal)
    return result


def build_proposal_records(pdf_id: str, row_id: str, result: GroupExtractionResult) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for proposal in result.proposals:
        records.append(
            {
                "proposal_id": str(uuid.uuid4()),
                "pdf_id": pdf_id,
                "row_id": row_id,
                "column": proposal.column,
                "proposed_value": str(proposal.proposed_value) if proposal.proposed_value is not None else None,
                "status": proposal.status,
                "confidence": proposal.confidence,
                "evidence": [e.model_dump(mode="json") for e in proposal.evidence],
                "reasoning": proposal.reasoning,
                "flags": proposal.flags,
            }
        )
    return records


def _apply_evidence_rules(proposal: Any) -> None:
    if proposal.status == "found" and not proposal.evidence:
        proposal.flags["needs_more_evidence"] = True
    if proposal.status in {"found", "inferred"}:
        for evidence in proposal.evidence:
            if not evidence.quote or not evidence.page:
                proposal.flags["needs_more_evidence"] = True
                break


def verify_cells(
    client: LlmClient,
    row_context: dict[str, Any],
    locked_values: dict[str, str],
    chunks: list[dict[str, Any]],
) -> list[VerifyResult]:
    results: list[VerifyResult] = []
    for column, value in locked_values.items():
        prompt = render_prompt(
            "verify_cell.md",
            row_context=json.dumps(row_context, indent=2),
            cell_value=json.dumps({"column": column, "value": value}, indent=2),
            chunks=json.dumps(chunks, indent=2),
        )
        results.append(client.complete_json(prompt, VerifyResult))
    return results
