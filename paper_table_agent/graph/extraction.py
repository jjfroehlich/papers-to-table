from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.models import GroupExtractionResult, ProposalItem, VerifyResult
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
    result = _ensure_group_coverage(result, group.columns)
    for proposal in result.proposals:
        proposal.flags.setdefault("mapping_dependent", mapping_dependent)
        _apply_evidence_rules(proposal)
    return result


def build_proposal_records(pdf_id: str, row_id: str, result: GroupExtractionResult) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for proposal in result.proposals:
        flags = dict(proposal.flags)
        if proposal.needs_more_evidence is not None:
            flags["needs_more_evidence"] = proposal.needs_more_evidence
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
                "reasoning": proposal.rationale,
                "flags": flags,
            }
        )
    return records


def _apply_evidence_rules(proposal: Any) -> None:
    if proposal.status == "found" and not proposal.evidence:
        proposal.needs_more_evidence = True
    if proposal.status in {"found", "inferred"}:
        for evidence in proposal.evidence:
            if not evidence.quote or not evidence.page:
                proposal.needs_more_evidence = True
                break
    if proposal.needs_more_evidence is None:
        proposal.needs_more_evidence = False


def build_error_records(
    pdf_id: str,
    row_id: str,
    columns: list[str],
    error: str,
    mapping_dependent: bool,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for column in columns:
        records.append(
            {
                "proposal_id": str(uuid.uuid4()),
                "pdf_id": pdf_id,
                "row_id": row_id,
                "column": column,
                "proposed_value": None,
                "status": "error",
                "confidence": 0.0,
                "evidence": [],
                "reasoning": error,
                "flags": {
                    "mapping_dependent": mapping_dependent,
                    "needs_more_evidence": True,
                    "error": True,
                },
            }
        )
    return records


def build_verify_records(
    pdf_id: str,
    row_id: str,
    results: list[VerifyResult],
    locked_values: dict[str, str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in results:
        needs_more = False
        for evidence in result.evidence:
            if not evidence.quote or not evidence.page:
                needs_more = True
                break
        if not result.evidence:
            needs_more = True
        records.append(
            {
                "proposal_id": str(uuid.uuid4()),
                "pdf_id": pdf_id,
                "row_id": row_id,
                "column": result.column,
                "proposed_value": locked_values.get(result.column),
                "status": result.status,
                "confidence": None,
                "evidence": [e.model_dump(mode="json") for e in result.evidence],
                "reasoning": result.rationale,
                "flags": {
                    "verify_only": True,
                    "needs_more_evidence": needs_more,
                },
            }
        )
    return records


def _ensure_group_coverage(result: GroupExtractionResult, columns: list[str]) -> GroupExtractionResult:
    by_column = {proposal.column: proposal for proposal in result.proposals}
    for column in columns:
        if column in by_column:
            continue
        by_column[column] = ProposalItem(
            column=column,
            proposed_value=None,
            status="not_found",
            confidence=0.0,
            evidence=[],
            needs_more_evidence=False,
            rationale="No evidence located in retrieved context.",
            flags={},
        )
    result.proposals = list(by_column.values())
    return result


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
