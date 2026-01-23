from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.models import GroupExtractionResult, ProposalItem, ProposalVerificationResult, VerifyResult
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
    chunks_by_column: dict[str, list[dict[str, Any]]],
    mapping_dependent: bool,
) -> GroupExtractionResult:
    prompt = render_prompt(
        "extract_group.md",
        row_context=json.dumps(row_context, indent=2),
        group_schema=json.dumps(group.schema, indent=2),
        examples=json.dumps(group.examples, indent=2),
        chunks=json.dumps(chunks_by_column, indent=2),
    )
    result = client.complete_json(prompt, GroupExtractionResult)
    result = _ensure_group_coverage(result, group.columns)
    chunk_lookup = _build_chunk_lookup(chunks_by_column)
    for proposal in result.proposals:
        proposal.flags.setdefault("mapping_dependent", mapping_dependent)
        _apply_evidence_rules(proposal, chunk_lookup)
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


def _apply_evidence_rules(proposal: Any, chunk_lookup: dict[str, dict[str, Any]]) -> None:
    status = proposal.status or "unclear"
    if status in {"found", "inferred"}:
        has_evidence, errors, mode, reason = _validate_evidence_list(proposal.evidence, chunk_lookup)
        if mode:
            proposal.flags["validation_mode"] = mode
        if reason:
            proposal.flags["validation_reason"] = reason
        if errors:
            proposal.flags.setdefault("evidence_validation_errors", []).extend(errors)
        if not has_evidence:
            proposal.proposed_value = None
            proposal.status = "unclear"
            proposal.needs_more_evidence = True
        else:
            proposal.status = status
    if proposal.status in {"not_found", "no_evidence", "unclear"}:
        proposal.proposed_value = None
    if proposal.needs_more_evidence is None:
        proposal.needs_more_evidence = proposal.status in {"unclear", "no_evidence"}


def build_error_records(
    pdf_id: str,
    row_id: str,
    columns: list[str],
    error: str,
    mapping_dependent: bool,
    error_type: str | None = None,
    raw_output: str | None = None,
    repair_attempted: bool | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for column in columns:
        flags = {
            "mapping_dependent": mapping_dependent,
            "needs_more_evidence": True,
            "error": True,
        }
        if error_type:
            flags["error_type"] = error_type
        if raw_output:
            flags["raw_output"] = raw_output[:2000]
        if repair_attempted is not None:
            flags["repair_attempted"] = repair_attempted
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
                "flags": flags,
            }
        )
    return records


def build_verify_records(
    pdf_id: str,
    row_id: str,
    results: list[VerifyResult],
    locked_values: dict[str, str],
    chunk_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for result in results:
        has_evidence, errors, mode, reason = _validate_evidence_list(result.evidence, chunk_lookup)
        needs_more = not has_evidence
        flags: dict[str, Any] = {
            "verify_only": True,
            "needs_more_evidence": needs_more,
        }
        if mode:
            flags["validation_mode"] = mode
        if reason:
            flags["validation_reason"] = reason
        if errors:
            flags["evidence_validation_errors"] = errors
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
                "flags": flags,
            }
        )
    return records


def _ensure_group_coverage(result: GroupExtractionResult, columns: list[str]) -> GroupExtractionResult:
    by_column: dict[str, ProposalItem] = {}
    for proposal in result.proposals:
        by_column[proposal.column] = proposal
        if proposal.column not in columns:
            proposal.flags.setdefault("unknown_column", True)
    for column in columns:
        if column in by_column:
            continue
        by_column[column] = ProposalItem(
            column=column,
            proposed_value=None,
            status="no_evidence",
            confidence=0.0,
            evidence=[],
            needs_more_evidence=True,
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


def verify_proposals(
    client: LlmClient,
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for proposal in proposals:
        column = proposal.get("column")
        proposed_value = proposal.get("proposed_value")
        evidence = proposal.get("evidence") or []
        flags = proposal.setdefault("flags", {})
        if not proposed_value or not evidence:
            flags["verification_status"] = "unclear"
            flags["verification_needs_more_evidence"] = True
            flags["verification_rationale"] = "Missing proposed value or evidence."
            continue
        prompt = render_prompt(
            "verify_proposal.md",
            column=json.dumps(column),
            proposed_value=json.dumps(proposed_value),
            evidence=json.dumps(evidence, indent=2),
        )
        result = client.complete_json(prompt, ProposalVerificationResult)
        flags["verification_status"] = result.status
        flags["verification_needs_more_evidence"] = result.needs_more_evidence
        flags["verification_rationale"] = result.rationale
    return proposals


def _build_chunk_lookup(chunks_by_column: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for chunks in chunks_by_column.values():
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id") or "")
            text = str(chunk.get("text") or "")
            if chunk_id and text:
                lookup.setdefault(
                    chunk_id,
                    {
                        "text": text,
                        "page_start": chunk.get("page_start"),
                        "page_end": chunk.get("page_end"),
                    },
                )
    return lookup


def _validate_evidence_list(
    evidence_list: list[Any],
    chunk_lookup: dict[str, dict[str, Any]] | None,
) -> tuple[bool, list[str], str | None, str | None]:
    if not evidence_list:
        return False, ["missing_evidence"], "missing", "missing_evidence"
    errors: list[str] = []
    for evidence in evidence_list:
        quote = getattr(evidence, "quote", None)
        page = getattr(evidence, "page", None)
        chunk_id = getattr(evidence, "chunk_id", None)
        if not quote or not page:
            errors.append("missing_quote_or_page")
            continue
        if chunk_lookup is None:
            return True, [], "unvalidated", "no_chunk_lookup"
        if not chunk_id:
            errors.append("missing_chunk_id")
            continue
        chunk_meta = chunk_lookup.get(str(chunk_id))
        if not chunk_meta:
            errors.append("unknown_chunk_id")
            continue
        page_start = chunk_meta.get("page_start")
        page_end = chunk_meta.get("page_end")
        if page_start is not None and page_end is not None:
            if int(page) < int(page_start) or int(page) > int(page_end):
                errors.append("page_outside_chunk")
                continue
        chunk_text = str(chunk_meta.get("text") or "")
        if str(quote) in chunk_text:
            return True, [], "exact", "exact_match"
        normalized_quote = _normalize_text(str(quote))
        normalized_chunk = _normalize_text(chunk_text)
        if normalized_quote and normalized_quote in normalized_chunk:
            return True, [], "normalized", "normalized_match"
        if str(quote) not in chunk_text:
            errors.append("quote_not_in_chunk")
    return False, errors, "failed", errors[0] if errors else None


_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "ft",
    "\ufb06": "st",
}


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.translate(str.maketrans(_LIGATURES))
    normalized = re.sub(r"-\s*\n\s*", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.casefold().strip()
