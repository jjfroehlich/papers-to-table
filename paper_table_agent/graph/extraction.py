from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process
from paper_table_agent.llm.client import LlmClient
from paper_table_agent.llm.models import GroupExtractionResult, ProposalItem, ProposalVerificationResult, VerifyResult
from paper_table_agent.llm.prompts import render_prompt
from paper_table_agent.text.normalization import normalize_chunk_id, normalize_for_matching, normalize_key, normalize_unicode


@dataclass
class GroupContext:
    name: str
    columns: list[str]
    schema: dict[str, str]
    examples: dict[str, list[dict[str, str]]]
    columns_payload: list[dict[str, Any]]
    column_id_map: dict[int, str]
    column_key_map: dict[str, str]


def extract_group(
    client: LlmClient,
    row_context: dict[str, Any],
    group: GroupContext,
    chunks_by_column: dict[str, list[dict[str, Any]]],
    mapping_dependent: bool,
    full_chunk_lookup: dict[str, dict[str, Any]] | None = None,
    pdf_id: str | None = None,
    prompt_meta: dict[str, Any] | None = None,
) -> GroupExtractionResult:
    merged_chunks = _merge_chunks(chunks_by_column)
    prompt = render_prompt(
        "extract_group.md",
        _prompt_meta={"pdf_id": pdf_id, "group": group.name},
        row_context=json.dumps(row_context, indent=2),
        columns=json.dumps(group.columns_payload, indent=2),
        chunks=json.dumps(merged_chunks, indent=2),
    )
    if prompt_meta is not None:
        prompt_meta["prompt_hash"] = hashlib.sha1(prompt.encode("utf-8")).hexdigest()
        prompt_meta["prompt_chars"] = len(prompt)
    result = client.complete_json(prompt, GroupExtractionResult)
    result = _coerce_group_columns(result, group)
    result = _ensure_group_coverage(result, group.columns)
    chunk_lookup = full_chunk_lookup or _build_chunk_lookup(chunks_by_column)
    for proposal in result.proposals:
        proposal.flags.setdefault("mapping_dependent", mapping_dependent)
        if proposal.column and proposal.column in group.schema:
            proposal.flags.setdefault("column_description", group.schema.get(proposal.column))
        _apply_evidence_rules(proposal, chunk_lookup)
    return result


def build_proposal_records(pdf_id: str, row_id: str, result: GroupExtractionResult) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for proposal in result.proposals:
        flags = dict(proposal.flags)
        if proposal.needs_more_evidence is not None:
            flags["needs_more_evidence"] = proposal.needs_more_evidence
        if proposal.evidence_quality:
            flags["evidence_quality"] = proposal.evidence_quality
        if proposal.search_hints:
            flags["search_hints"] = proposal.search_hints
        if proposal.col_id is not None:
            flags["col_id"] = proposal.col_id
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
    has_evidence, errors, mode, reason = _validate_evidence_list(proposal.evidence, chunk_lookup)
    if mode:
        proposal.flags["validation_mode"] = mode
    if reason:
        proposal.flags["validation_reason"] = reason
    if errors:
        proposal.flags.setdefault("evidence_validation_errors", []).extend(errors)
    if not has_evidence:
        proposal.flags["evidence_missing"] = True
        proposal.flags["failure_reason"] = proposal.flags.get("failure_reason") or reason or "missing_evidence"
        proposal.needs_more_evidence = True
    proposal.status = status
    if _has_ellipsis_quote(proposal.evidence):
        proposal.flags["quote_has_ellipsis"] = True
        proposal.needs_more_evidence = True
    if proposal.needs_more_evidence is None:
        proposal.needs_more_evidence = proposal.status in {"unclear", "no_evidence"} or not has_evidence
    if proposal.proposed_value is not None or (proposal.evidence or proposal.needs_more_evidence):
        proposal.flags.setdefault("needs_review", True)
    proposal.evidence_quality = _derive_evidence_quality(proposal.evidence, has_evidence, errors)
    proposal.flags["evidence_quality"] = proposal.evidence_quality
    if proposal.evidence_quality != "strong":
        if proposal.proposed_value and not proposal.search_hints:
            proposal.search_hints = [str(proposal.proposed_value)]
        if not proposal.search_hints:
            proposal.search_hints = []
        column_desc = proposal.flags.get("column_description")
        if column_desc:
            proposal.search_hints.append(str(column_desc))
        if proposal.column:
            proposal.search_hints.append(str(proposal.column))
        proposal.search_hints = _dedupe_search_hints(proposal.search_hints)


def build_error_records(
    pdf_id: str,
    row_id: str,
    columns: list[str],
    error: str,
    mapping_dependent: bool,
    error_type: str | None = None,
    validation_errors: list[dict[str, Any]] | None = None,
    raw_output: str | None = None,
    repair_attempted: bool | None = None,
    http_status: int | None = None,
    error_substring: str | None = None,
    guided_json_active: bool | None = None,
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
            flags["failure_reason"] = error_type
        if validation_errors:
            flags["validation_errors"] = validation_errors
        if raw_output:
            flags["raw_output"] = raw_output[:2000]
        if repair_attempted is not None:
            flags["repair_attempted"] = repair_attempted
        if http_status is not None:
            flags["http_status"] = http_status
        if error_substring:
            flags["error_substring"] = error_substring
        if guided_json_active is not None:
            flags["guided_json_active"] = guided_json_active
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
            evidence_quality="none",
            needs_more_evidence=True,
            search_hints=[column],
            rationale="No evidence located in retrieved context.",
            flags={"failure_reason": "no_evidence"},
        )
    result.proposals = list(by_column.values())
    return result


def verify_cells(
    client: LlmClient,
    row_context: dict[str, Any],
    locked_values: dict[str, str],
    chunks: list[dict[str, Any]],
    pdf_id: str | None = None,
) -> list[VerifyResult]:
    results: list[VerifyResult] = []
    for column, value in locked_values.items():
        prompt = render_prompt(
            "verify_cell.md",
            _prompt_meta={"pdf_id": pdf_id, "column": column},
            row_context=json.dumps(row_context, indent=2),
            cell_value=json.dumps({"column": column, "value": value}, indent=2),
            chunks=json.dumps(chunks, indent=2),
        )
        results.append(client.complete_json(prompt, VerifyResult))
    return results


def verify_proposals(
    client: LlmClient,
    proposals: list[dict[str, Any]],
    pdf_id: str | None = None,
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
            _prompt_meta={"pdf_id": pdf_id, "column": column},
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
    idx_lookup: dict[int, str] = {}
    pk_lookup: dict[str, str] = {}
    for chunks in chunks_by_column.values():
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id") or "")
            chunk_idx = chunk.get("chunk_idx")
            text = str(chunk.get("text") or "")
            if chunk_id and text:
                canonical_id = normalize_chunk_id(chunk_id)
                lookup.setdefault(
                    canonical_id,
                    {
                        "text": text,
                        "text_raw": chunk.get("text_raw") or text,
                        "text_norm": chunk.get("text_norm") or text,
                        "page_start": chunk.get("page_start"),
                        "page_end": chunk.get("page_end"),
                        "chunk_pk": chunk.get("chunk_pk"),
                        "chunk_idx": chunk_idx,
                    },
                )
                if isinstance(chunk_idx, int):
                    idx_lookup[chunk_idx] = canonical_id
                chunk_pk = chunk.get("chunk_pk")
                if chunk_pk:
                    pk_lookup[str(chunk_pk)] = canonical_id
    lookup["_chunk_idx_map"] = idx_lookup
    lookup["_chunk_pk_map"] = pk_lookup
    return lookup


def build_chunk_lookup_from_list(chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _build_chunk_lookup({"__all__": chunks})


def _merge_chunks(chunks_by_column: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunks in chunks_by_column.values():
        for chunk in chunks:
            chunk_id = normalize_chunk_id(str(chunk.get("chunk_id") or ""))
            if not chunk_id or chunk_id in seen:
                continue
            merged.append(chunk)
            seen.add(chunk_id)
    return merged


def _coerce_group_columns(result: GroupExtractionResult, group: GroupContext) -> GroupExtractionResult:
    key_map = group.column_key_map
    id_map = group.column_id_map
    for proposal in result.proposals:
        if proposal.col_id is not None and proposal.col_id in id_map:
            proposal.column = id_map[proposal.col_id]
        else:
            column_name = proposal.column or ""
            normalized = normalize_key(column_name)
            if normalized in key_map:
                proposal.column = key_map[normalized]
            else:
                proposal.column = proposal.column or "unknown"
                proposal.flags.setdefault("unknown_column", True)
    return result


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
        chunk_idx = getattr(evidence, "chunk_idx", None)
        if quote:
            normalized_quote = normalize_for_matching(normalize_unicode(str(quote)))
            setattr(evidence, "quote_raw", str(quote))
            setattr(evidence, "quote_normalized", normalized_quote)
        if chunk_lookup is None:
            return True, [], "unvalidated", "no_chunk_lookup"
        chunk_idx_map = chunk_lookup.get("_chunk_idx_map", {})
        chunk_pk_map = chunk_lookup.get("_chunk_pk_map", {})
        canonical_id = ""
        if chunk_id:
            canonical_id = normalize_chunk_id(str(chunk_id))
        if not canonical_id and isinstance(chunk_idx, int):
            canonical_id = chunk_idx_map.get(chunk_idx, "")
            if canonical_id:
                setattr(evidence, "chunk_id", canonical_id)
        if not canonical_id:
            chunk_pk = getattr(evidence, "chunk_pk", None)
            if chunk_pk:
                canonical_id = chunk_pk_map.get(str(chunk_pk), "")
                if canonical_id:
                    setattr(evidence, "chunk_id", canonical_id)
        if not canonical_id and chunk_id:
            repaired = _fuzzy_match_chunk_id(str(chunk_id), chunk_lookup)
            if repaired:
                setattr(evidence, "chunk_id", repaired)
                canonical_id = repaired
                errors.append("chunk_id_repaired")
        if not canonical_id:
            repaired = _repair_chunk_reference(str(quote), chunk_lookup)
            if repaired:
                setattr(evidence, "chunk_id", repaired)
                canonical_id = repaired
                errors.append("chunk_id_repaired_by_quote")
        if not canonical_id:
            errors.append("missing_chunk_id")
            return True, errors, "weak", "missing_chunk_id"
        chunk_meta = chunk_lookup.get(canonical_id)
        if not chunk_meta:
            errors.append("unknown_chunk_id")
            return True, errors, "weak", "unknown_chunk_id"
        if not page and chunk_meta.get("page_start") is not None:
            page = chunk_meta.get("page_start")
            setattr(evidence, "page", page)
        if not chunk_id:
            setattr(evidence, "chunk_id", canonical_id)
        if getattr(evidence, "chunk_pk", None) is None and chunk_meta.get("chunk_pk"):
            setattr(evidence, "chunk_pk", chunk_meta.get("chunk_pk"))
        if getattr(evidence, "chunk_idx", None) is None and chunk_meta.get("chunk_idx") is not None:
            setattr(evidence, "chunk_idx", chunk_meta.get("chunk_idx"))
        if not quote or not page:
            errors.append("missing_quote_or_page")
            continue
        page_start = chunk_meta.get("page_start")
        page_end = chunk_meta.get("page_end")
        if page_start is not None and page_end is not None:
            if int(page) < int(page_start) or int(page) > int(page_end):
                errors.append("page_outside_chunk")
                return True, errors, "weak", "page_outside_chunk"
        chunk_text_raw = str(chunk_meta.get("text_raw") or chunk_meta.get("text") or "")
        if str(quote) in chunk_text_raw:
            setattr(evidence, "validation_mode", "exact")
            return True, [], "exact", "exact_match"
        normalized_quote = normalize_for_matching(str(quote))
        normalized_chunk = normalize_for_matching(
            normalize_unicode(str(chunk_meta.get("text_norm") or chunk_meta.get("text") or chunk_text_raw))
        )
        if normalized_quote and normalized_quote in normalized_chunk:
            setattr(evidence, "validation_mode", "normalized")
            return True, [], "normalized", "normalized_match"
        salvaged = _salvage_quote_from_chunk(str(quote), chunk_text_raw)
        if salvaged:
            setattr(evidence, "quote", salvaged)
            setattr(evidence, "validation_mode", "salvaged")
            errors.append("quote_salvaged")
            return True, errors, "salvaged", "salvaged_quote"
        if _quote_has_ellipsis(str(quote)):
            fragments = _split_quote_fragments(str(quote))
            for fragment in fragments:
                normalized_fragment = normalize_for_matching(fragment)
                if normalized_fragment and normalized_fragment in normalized_chunk:
                    setattr(evidence, "validation_mode", "ellipsis_fragment")
                    return True, [], "ellipsis_fragment", "ellipsis_fragment_match"
            errors.append("quote_has_ellipsis")
        errors.append("quote_not_in_chunk")
    return True, errors, "weak", errors[0] if errors else None


def _repair_chunk_reference(quote: str, chunk_lookup: dict[str, dict[str, Any]]) -> str | None:
    if not quote:
        return None
    normalized_quote = normalize_for_matching(quote)
    if not normalized_quote:
        return None
    for chunk_id, chunk_meta in chunk_lookup.items():
        if chunk_id.startswith("_"):
            continue
        chunk_text = str(chunk_meta.get("text_norm") or chunk_meta.get("text") or "")
        if normalized_quote and normalized_quote in normalize_for_matching(chunk_text):
            return chunk_id
    return None


def _fuzzy_match_chunk_id(chunk_id: str, chunk_lookup: dict[str, dict[str, Any]]) -> str | None:
    normalized = normalize_chunk_id(chunk_id)
    candidates = [key for key in chunk_lookup.keys() if not key.startswith("_")]
    if not candidates:
        return None
    match = process.extractOne(normalized, candidates, scorer=fuzz.ratio)
    if not match or match[1] < 80:
        return None
    return match[0]


def _derive_evidence_quality(
    evidence_list: list[Any],
    has_evidence: bool,
    errors: list[str],
) -> str:
    if not evidence_list:
        return "none"
    if has_evidence and not errors:
        return "strong"
    return "weak"


def _dedupe_search_hints(hints: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for hint in hints:
        normalized = str(hint).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _quote_has_ellipsis(quote: str) -> bool:
    return "…" in quote or "..." in quote


def _split_quote_fragments(quote: str) -> list[str]:
    if not quote:
        return []
    parts = re.split(r"(?:\\.{3}|…)", quote)
    return [part.strip() for part in parts if len(part.strip()) >= 6]


def _has_ellipsis_quote(evidence_list: list[Any]) -> bool:
    for evidence in evidence_list:
        quote = getattr(evidence, "quote", None)
        if quote and _quote_has_ellipsis(str(quote)):
            return True
    return False


def _salvage_quote_from_chunk(quote: str, chunk_text: str, threshold: int = 78) -> str | None:
    if not quote or not chunk_text:
        return None
    quote_words = _normalize_words(quote)
    if not quote_words:
        return None
    tokens = list(re.finditer(r"\S+", chunk_text))
    if not tokens:
        return None
    token_entries = []
    for token in tokens:
        words = _normalize_words(token.group(0))
        if words:
            token_entries.append((token, words[0]))
    if not token_entries:
        return None
    normalized_tokens = [entry[1] for entry in token_entries]
    min_size = max(len(quote_words) - 2, 3)
    max_size = min(len(quote_words) + 2, 12)
    best_score = 0
    best_span: tuple[int, int] | None = None
    target = " ".join(quote_words)
    for window_size in range(min_size, max_size + 1):
        for start in range(len(normalized_tokens) - window_size + 1):
            window = normalized_tokens[start : start + window_size]
            score = fuzz.ratio(target, " ".join(window))
            if score > best_score:
                best_score = score
                best_span = (start, start + window_size)
    if best_span is None or best_score < threshold:
        return None
    start_idx = token_entries[best_span[0]][0].start()
    end_idx = token_entries[best_span[1] - 1][0].end()
    return chunk_text[start_idx:end_idx].strip()


def _normalize_words(text: str) -> list[str]:
    cleaned = normalize_for_matching(normalize_unicode(text))
    cleaned = re.sub(r"[^0-9a-z]+", " ", cleaned).strip().lower()
    return [word for word in cleaned.split() if word]
