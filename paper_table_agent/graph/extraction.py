from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz, process
from paper_table_agent.llm.client import LlmClient, estimate_tokens
from paper_table_agent.llm.models import GroupExtractionResult, ProposalItem, VerifyResult
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


@dataclass
class ExtractPromptBatch:
    group: GroupContext
    prompt: str
    chunks: list[dict[str, Any]]
    prompt_meta: dict[str, Any]
    col_ids: list[int]


def extract_group(
    client: LlmClient,
    row_context: dict[str, Any],
    group: GroupContext,
    chunks_by_column: dict[str, list[dict[str, Any]]],
    mapping_dependent: bool,
    full_chunk_lookup: dict[str, dict[str, Any]] | None = None,
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
    page_text: list[str] | None = None,
    prompt_meta: dict[str, Any] | None = None,
    prompt_override: str | None = None,
    trimmed_chunks: list[dict[str, Any]] | None = None,
) -> GroupExtractionResult:
    merged_chunks = _merge_chunks(chunks_by_column)
    if prompt_override:
        prompt = prompt_override
    else:
        prompt, trimmed_chunks = _build_extract_prompt(
            client,
            row_context,
            group,
            merged_chunks,
            pdf_id=pdf_id,
            context_mode=context_mode,
            context_payload=context_payload,
            prompt_meta=prompt_meta,
        )
    if trimmed_chunks is not None:
        merged_chunks = trimmed_chunks
    result = client.complete_json(prompt, GroupExtractionResult)
    result = _coerce_group_columns(result, group)
    result = _ensure_group_coverage(result, group.columns)
    chunk_lookup = None if context_mode != "retrieval" else (full_chunk_lookup or _build_chunk_lookup(chunks_by_column))
    for proposal in result.proposals:
        proposal.flags.setdefault("mapping_dependent", mapping_dependent)
        if proposal.column and proposal.column in group.schema:
            proposal.flags.setdefault("column_description", group.schema.get(proposal.column))
        _apply_evidence_rules(proposal, chunk_lookup, page_text=page_text)
    return result


def build_extract_prompt(
    client: LlmClient,
    row_context: dict[str, Any],
    group: GroupContext,
    chunks_by_column: dict[str, list[dict[str, Any]]],
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
    prompt_meta: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    merged_chunks = _merge_chunks(chunks_by_column)
    batches = build_extract_prompt_batches(
        client,
        row_context,
        group,
        merged_chunks,
        pdf_id=pdf_id,
        context_mode=context_mode,
        context_payload=context_payload,
        prompt_meta=prompt_meta,
    )
    if not batches:
        prompt, trimmed_chunks = _build_extract_prompt(
            client,
            row_context,
            group,
            merged_chunks,
            pdf_id=pdf_id,
            context_mode=context_mode,
            context_payload=context_payload,
            prompt_meta=prompt_meta,
        )
        return prompt, trimmed_chunks or merged_chunks
    return batches[0].prompt, batches[0].chunks


def _build_extract_prompt(
    client: LlmClient,
    row_context: dict[str, Any],
    group: GroupContext,
    merged_chunks: list[dict[str, Any]],
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
    prompt_meta: dict[str, Any] | None = None,
) -> tuple[str, list[dict[str, Any]] | None]:
    batches = build_extract_prompt_batches(
        client,
        row_context,
        group,
        merged_chunks,
        pdf_id=pdf_id,
        context_mode=context_mode,
        context_payload=context_payload,
        prompt_meta=prompt_meta,
    )
    if not batches:
        prompt = _render_extract_prompt(
            row_context,
            group.columns_payload,
            _sanitize_chunks_for_prompt(merged_chunks),
            group.name,
            pdf_id=pdf_id,
            context_mode=context_mode,
            context_payload=context_payload,
        )[0]
        if prompt_meta is not None:
            prompt_meta["prompt_hash"] = hashlib.sha1(prompt.encode("utf-8")).hexdigest()
            prompt_meta["prompt_chars"] = len(prompt)
            prompt_meta["prompt_tokens"] = estimate_tokens(prompt)
        return prompt, None
    batch = batches[0]
    if prompt_meta is not None:
        prompt_meta.update(batch.prompt_meta)
    return batch.prompt, batch.chunks


def build_extract_prompt_batches(
    client: LlmClient,
    row_context: dict[str, Any],
    group: GroupContext,
    merged_chunks: list[dict[str, Any]],
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
    prompt_meta: dict[str, Any] | None = None,
) -> list[ExtractPromptBatch]:
    sanitized_chunks = _sanitize_chunks_for_prompt(merged_chunks)
    columns_payload = json.loads(json.dumps(group.columns_payload))
    batches = _build_prompt_batches_for_columns(
        client,
        row_context,
        group,
        columns_payload,
        sanitized_chunks,
        pdf_id=pdf_id,
        context_mode=context_mode,
        context_payload=context_payload,
    )
    batch_total = len(batches)
    for idx, batch in enumerate(batches):
        batch.prompt_meta.setdefault("prompt_batch_idx", idx + 1)
        batch.prompt_meta.setdefault("prompt_batch_total", batch_total)
        batch.prompt_meta.setdefault("prompt_has_chunks", bool(batch.chunks))
        if prompt_meta is not None and idx == 0:
            prompt_meta.update(batch.prompt_meta)
    return batches


def _build_prompt_batches_for_columns(
    client: LlmClient,
    row_context: dict[str, Any],
    group: GroupContext,
    columns_payload: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
) -> list[ExtractPromptBatch]:
    prompt, adjusted_columns, adjusted_chunks, meta, exceeds = _fit_prompt_budget(
        client,
        row_context,
        columns_payload,
        chunks,
        group.name,
        pdf_id=pdf_id,
        context_mode=context_mode,
        context_payload=context_payload,
    )
    columns = [column.get("name") for column in adjusted_columns]
    if not exceeds or len(columns) <= 1:
        batch_group = _build_group_subset(group, adjusted_columns)
        col_ids = [column.get("col_id") for column in adjusted_columns if column.get("col_id") is not None]
        return [
            ExtractPromptBatch(
                group=batch_group,
                prompt=prompt,
                chunks=adjusted_chunks,
                prompt_meta=meta,
                col_ids=col_ids,
            )
        ]
    mid = max(1, len(columns_payload) // 2)
    first = columns_payload[:mid]
    second = columns_payload[mid:]
    batches: list[ExtractPromptBatch] = []
    batches.extend(
        _build_prompt_batches_for_columns(
            client,
            row_context,
            group,
            first,
            chunks,
            pdf_id=pdf_id,
            context_mode=context_mode,
            context_payload=context_payload,
        )
    )
    batches.extend(
        _build_prompt_batches_for_columns(
            client,
            row_context,
            group,
            second,
            chunks,
            pdf_id=pdf_id,
            context_mode=context_mode,
            context_payload=context_payload,
        )
    )
    return batches


def _fit_prompt_budget(
    client: LlmClient,
    row_context: dict[str, Any],
    columns_payload: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    group_name: str,
    *,
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], bool]:
    max_tokens = client.config.max_prompt_tokens
    max_chars = client.config.max_prompt_chars
    meta: dict[str, Any] = {
        "prompt_trimmed": False,
        "trimmed_chunks": 0,
        "trimmed_total_chunks": len(chunks),
        "trimmed_chunk_chars": None,
        "trimmed_examples": None,
        "prompt_budget_exceeded": False,
    }
    adjusted_columns = json.loads(json.dumps(columns_payload))
    adjusted_chunks = list(chunks)
    prompt, prompt_tokens = _render_extract_prompt(
        row_context,
        adjusted_columns,
        adjusted_chunks,
        group_name,
        pdf_id=pdf_id,
        context_mode=context_mode,
        context_payload=context_payload,
    )
    if context_mode == "retrieval":
        while len(adjusted_chunks) > 1 and _prompt_exceeds_budget(prompt_tokens, len(prompt), max_tokens, max_chars):
            adjusted_chunks.pop()
            meta["prompt_trimmed"] = True
            meta["trimmed_chunks"] = meta["trimmed_chunks"] + 1
            prompt, prompt_tokens = _render_extract_prompt(
                row_context,
                adjusted_columns,
                adjusted_chunks,
                group_name,
                pdf_id=pdf_id,
                context_mode=context_mode,
                context_payload=context_payload,
            )
        if _prompt_exceeds_budget(prompt_tokens, len(prompt), max_tokens, max_chars):
            adjusted_chunks, max_chunk_chars = _trim_chunk_text_until_fit(
                row_context,
                adjusted_columns,
                adjusted_chunks,
                group_name,
                pdf_id=pdf_id,
                max_tokens=max_tokens,
                max_chars=max_chars,
                context_mode=context_mode,
                context_payload=context_payload,
            )
            if max_chunk_chars is not None:
                meta["prompt_trimmed"] = True
                meta["trimmed_chunk_chars"] = max_chunk_chars
            prompt, prompt_tokens = _render_extract_prompt(
                row_context,
                adjusted_columns,
                adjusted_chunks,
                group_name,
                pdf_id=pdf_id,
                context_mode=context_mode,
                context_payload=context_payload,
            )
    if _prompt_exceeds_budget(prompt_tokens, len(prompt), max_tokens, max_chars):
        for max_examples in (1, 0):
            adjusted_columns = _trim_examples_per_column(adjusted_columns, max_examples)
            meta["prompt_trimmed"] = True
            meta["trimmed_examples"] = max_examples
            prompt, prompt_tokens = _render_extract_prompt(
                row_context,
                adjusted_columns,
                adjusted_chunks,
                group_name,
                pdf_id=pdf_id,
                context_mode=context_mode,
                context_payload=context_payload,
            )
            if not _prompt_exceeds_budget(prompt_tokens, len(prompt), max_tokens, max_chars):
                break
    if _prompt_exceeds_budget(prompt_tokens, len(prompt), max_tokens, max_chars):
        meta["prompt_budget_exceeded"] = True
    meta["prompt_hash"] = hashlib.sha1(prompt.encode("utf-8")).hexdigest()
    meta["prompt_chars"] = len(prompt)
    meta["prompt_tokens"] = prompt_tokens
    return prompt, adjusted_columns, adjusted_chunks, meta, meta["prompt_budget_exceeded"]


def _render_extract_prompt(
    row_context: dict[str, Any],
    columns_payload: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    group_name: str,
    *,
    pdf_id: str | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
) -> tuple[str, int]:
    payload = context_payload if context_payload is not None else json.dumps(chunks, indent=2)
    prompt = render_prompt(
        "extract_column.md",
        _prompt_meta={"pdf_id": pdf_id, "group": group_name},
        row_context=json.dumps(row_context, indent=2),
        columns=json.dumps(columns_payload, indent=2),
        context_mode=context_mode,
        context_payload=payload,
    )
    return prompt, estimate_tokens(prompt)


def _trim_chunk_text_until_fit(
    row_context: dict[str, Any],
    columns_payload: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    group_name: str,
    *,
    pdf_id: str | None = None,
    max_tokens: int | None = None,
    max_chars: int | None = None,
    context_mode: str = "retrieval",
    context_payload: str | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    if not chunks:
        return chunks, None
    max_text_len = max(len(str(chunk.get("text") or "")) for chunk in chunks)
    if max_text_len <= 0:
        return chunks, None
    max_chars_limit = max(max_text_len, 200)
    min_chars_limit = 120
    step = max(40, max_text_len // 10)
    trimmed_chunks = chunks
    while max_chars_limit >= min_chars_limit:
        trimmed_chunks = _trim_chunk_text(trimmed_chunks, max_chars_limit)
        prompt, prompt_tokens = _render_extract_prompt(
            row_context,
            columns_payload,
            trimmed_chunks,
            group_name,
            pdf_id=pdf_id,
            context_mode=context_mode,
            context_payload=context_payload,
        )
        if not _prompt_exceeds_budget(prompt_tokens, len(prompt), max_tokens, max_chars):
            return trimmed_chunks, max_chars_limit
        max_chars_limit -= step
    return trimmed_chunks, max_chars_limit


def _trim_chunk_text(chunks: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for chunk in chunks:
        entry = dict(chunk)
        text = str(entry.get("text") or "")
        if text and len(text) > max_chars:
            entry["text"] = text[:max_chars].strip()
        trimmed.append(entry)
    return trimmed


def _trim_examples_per_column(columns_payload: list[dict[str, Any]], max_examples: int) -> list[dict[str, Any]]:
    trimmed: list[dict[str, Any]] = []
    for column in columns_payload:
        entry = dict(column)
        examples = entry.get("examples") or []
        if isinstance(examples, list) and max_examples >= 0:
            entry["examples"] = examples[:max_examples]
        trimmed.append(entry)
    return trimmed


def _sanitize_chunks_for_prompt(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for chunk in chunks:
        text = chunk.get("text") or chunk.get("text_raw") or ""
        sanitized.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "chunk_idx": chunk.get("chunk_idx"),
                "chunk_pk": chunk.get("chunk_pk"),
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "text": text,
            }
        )
    return sanitized


def _build_group_subset(group: GroupContext, columns_payload: list[dict[str, Any]]) -> GroupContext:
    columns = [column.get("name") for column in columns_payload if column.get("name")]
    schema = {name: group.schema.get(name, "") for name in columns}
    examples = {name: group.examples.get(name, []) for name in columns}
    column_id_map = {
        int(column["col_id"]): str(column.get("name"))
        for column in columns_payload
        if column.get("col_id") is not None
    }
    column_key_map = {normalize_key(name): name for name in columns}
    return GroupContext(
        name=group.name,
        columns=columns,
        schema=schema,
        examples=examples,
        columns_payload=columns_payload,
        column_id_map=column_id_map,
        column_key_map=column_key_map,
    )


def _prompt_exceeds_budget(
    token_count: int,
    char_count: int,
    max_tokens: int | None,
    max_chars: int | None,
) -> bool:
    if max_tokens and token_count > max_tokens:
        return True
    if max_chars and char_count > max_chars:
        return True
    return False


def build_proposal_records(pdf_id: str, row_id: str, result: GroupExtractionResult) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for proposal in result.proposals:
        _ensure_evidence_pdf_id(proposal.evidence, pdf_id)
        flags = dict(proposal.flags)
        if proposal.needs_more_evidence is not None:
            flags["needs_more_evidence"] = proposal.needs_more_evidence
        if proposal.evidence_quality:
            flags["evidence_quality"] = proposal.evidence_quality
        if proposal.search_hints:
            flags["search_hints"] = proposal.search_hints
        if proposal.col_id is not None:
            flags["col_id"] = proposal.col_id
        if proposal.needs_more_context is not None:
            flags["needs_more_context"] = proposal.needs_more_context
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
                "flags": flags,
            }
        )
    return records


def _apply_evidence_rules(
    proposal: Any,
    chunk_lookup: dict[str, dict[str, Any]] | None,
    *,
    page_text: list[str] | None = None,
) -> None:
    status = proposal.status or "unclear"
    has_evidence, errors, mode, reason = _validate_evidence_list(proposal.evidence, chunk_lookup, page_text=page_text)
    quality_errors = _evidence_quality_floor(proposal, page_text=page_text)
    if quality_errors:
        errors.extend(quality_errors)
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
    if getattr(proposal, "needs_more_context", None):
        proposal.flags["needs_more_context"] = True
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
        proposal.needs_more_evidence = True
    if _should_downgrade_unanchored_found(proposal):
        proposal.status = "inferred"
        proposal.needs_more_evidence = True
        proposal.flags["found_unanchored_downgraded"] = True
        proposal.flags.setdefault("failure_reason", "found_value_unanchored")
        if not proposal.reasoning:
            proposal.reasoning = "Value inferred; no evidence quote contains the proposed value."
    if proposal.status == "found" and proposal.evidence_quality != "strong":
        proposal.status = "inferred"
        proposal.needs_more_evidence = True
        proposal.flags["found_weak_evidence_downgraded"] = True
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
    error_class: str | None = None,
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
        if error_class:
            flags["error_class"] = error_class
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
        _ensure_evidence_pdf_id(result.evidence, pdf_id)
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
    client: LlmClient | None,
    proposals: list[dict[str, Any]],
    pdf_id: str | None = None,
) -> list[dict[str, Any]]:
    for proposal in proposals:
        column = proposal.get("column")
        proposed_value = proposal.get("proposed_value")
        evidence = proposal.get("evidence") or []
        flags = proposal.setdefault("flags", {})
        quote_texts = [
            str(item.get("quote") or item.get("quote_text") or "")
            for item in evidence
            if str(item.get("quote") or item.get("quote_text") or "").strip()
        ]
        if not proposed_value or not quote_texts:
            flags["verification_status"] = "unclear"
            flags["verification_needs_more_evidence"] = True
            flags["verification_rationale"] = "Missing proposed value or evidence quotes."
            proposal["status"] = "inferred" if proposed_value else proposal.get("status")
            flags["needs_more_evidence"] = True
            continue
        supports = _evidence_supports_value(proposed_value, quote_texts, column=column)
        if supports:
            flags["verification_status"] = "supports"
            flags["verification_needs_more_evidence"] = False
            flags["verification_rationale"] = "Evidence quote contains the proposed value or key terms."
        else:
            flags["verification_status"] = "unclear"
            flags["verification_needs_more_evidence"] = True
            flags["verification_rationale"] = "Evidence quotes lack key terms or numeric overlap."
            proposal["status"] = "inferred"
        flags["needs_more_evidence"] = _reconcile_needs_more_evidence(proposal)
    return proposals


def _reconcile_needs_more_evidence(proposal: dict[str, Any]) -> bool:
    flags = proposal.get("flags", {})
    evidence = proposal.get("evidence") or []
    evidence_quality = flags.get("evidence_quality") or proposal.get("evidence_quality")
    verification_status = flags.get("verification_status")
    hard_rule = bool(
        flags.get("evidence_missing")
        or flags.get("evidence_validation_errors")
        or flags.get("needs_more_context")
    )
    if verification_status == "supports" and evidence_quality == "strong" and not hard_rule:
        return False
    if not evidence:
        return True
    if evidence_quality in {"weak", "none"}:
        return True
    return bool(flags.get("verification_needs_more_evidence"))


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
                legacy_pk = _legacy_chunk_pk(chunk_id)
                if legacy_pk:
                    pk_lookup.setdefault(legacy_pk, canonical_id)
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
    *,
    page_text: list[str] | None = None,
) -> tuple[bool, list[str], str | None, str | None]:
    if not evidence_list:
        return False, ["missing_evidence"], "missing", "missing_evidence"
    errors: list[str] = []
    for evidence in evidence_list:
        quote = getattr(evidence, "quote", None)
        page = getattr(evidence, "page", None)
        chunk_id = getattr(evidence, "chunk_id", None)
        chunk_idx = getattr(evidence, "chunk_idx", None)
        source_ref = getattr(evidence, "source_ref", None)
        anchor_id = getattr(evidence, "anchor_id", None)
        if anchor_id and not chunk_id:
            anchor_payload = _parse_anchor_id(anchor_id)
            if anchor_payload.get("chunk_id"):
                chunk_id = anchor_payload["chunk_id"]
                setattr(evidence, "chunk_id", chunk_id)
            if anchor_payload.get("page") and not page:
                page = anchor_payload["page"]
                setattr(evidence, "page", page)
        if source_ref and not chunk_id:
            parsed_chunk = _parse_source_ref(source_ref)
            if parsed_chunk.get("chunk_id"):
                chunk_id = parsed_chunk["chunk_id"]
                setattr(evidence, "chunk_id", chunk_id)
            if parsed_chunk.get("page") and not page:
                page = parsed_chunk["page"]
                setattr(evidence, "page", page)
        if quote:
            normalized_quote = normalize_for_matching(normalize_unicode(str(quote)))
            setattr(evidence, "quote_raw", str(quote))
            setattr(evidence, "quote_normalized", normalized_quote)
        if chunk_lookup is None:
            if page_text and quote and page:
                page_idx = int(page) - 1
                if 0 <= page_idx < len(page_text) and str(quote) in page_text[page_idx]:
                    setattr(evidence, "validation_mode", "page_text_exact")
                    return True, [], "page_text_exact", "page_text_exact"
                normalized_quote = normalize_for_matching(str(quote))
                if (
                    0 <= page_idx < len(page_text)
                    and normalized_quote
                    and normalized_quote in normalize_for_matching(page_text[page_idx])
                ):
                    setattr(evidence, "validation_mode", "page_text_normalized")
                    return True, [], "page_text_normalized", "page_text_normalized"
                errors.append("quote_not_in_page_text")
                return True, errors, "weak", "quote_not_in_page_text"
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
                corrected_page = int(page_start)
                setattr(evidence, "page", corrected_page)
                page = corrected_page
                errors.append("page_outside_chunk_corrected")
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


def _parse_source_ref(source_ref: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    if not source_ref:
        return parsed
    ref = str(source_ref).strip()
    if ref.startswith("page:"):
        try:
            parsed["page"] = int(ref.split(":", 1)[1])
        except ValueError:
            return parsed
    if ref.startswith("chunk_id:"):
        parsed["chunk_id"] = ref.split(":", 1)[1]
    if ref.startswith("chunk:"):
        parsed["chunk_id"] = ref.split(":", 1)[1]
    return parsed


def _parse_anchor_id(anchor_id: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    if not anchor_id:
        return parsed
    anchor = str(anchor_id).strip()
    if anchor.startswith("page-"):
        try:
            parsed["page"] = int(anchor.split("-", 1)[1])
        except ValueError:
            return parsed
    if anchor.startswith("chunk-"):
        parsed["chunk_id"] = anchor.split("-", 1)[1]
    if anchor.startswith("chunk_id:"):
        parsed["chunk_id"] = anchor.split(":", 1)[1]
    if anchor.startswith("para-") or anchor.startswith("section-"):
        parsed["chunk_id"] = anchor
    return parsed


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


def _evidence_quality_floor(proposal: Any, *, page_text: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    column = str(getattr(proposal, "column", "") or "")
    bibliographic = _is_bibliographic_column(column)
    for evidence in getattr(proposal, "evidence", None) or []:
        quote = str(getattr(evidence, "quote", None) or getattr(evidence, "quote_text", None) or "").strip()
        if not quote:
            errors.append("missing_quote")
            continue
        if len(quote) < 8 or len(quote.split()) < 2:
            errors.append("quote_too_short")
        alnum = sum(1 for char in quote if char.isalnum())
        if alnum / max(len(quote), 1) < 0.25:
            errors.append("quote_low_signal")
        quote_start = getattr(evidence, "quote_start", None)
        page = getattr(evidence, "page", None)
        if _looks_like_header_footer(quote, quote_start, page_text, page):
            errors.append("quote_header_footer")
            if quote_start == 0 and not bibliographic:
                errors.append("quote_start_header_footer")
        if quote_start == 0 and not bibliographic:
            errors.append("quote_start_disallowed")
    return errors


def _looks_like_header_footer(
    quote: str,
    quote_start: int | None,
    page_text: list[str] | None,
    page: int | None,
) -> bool:
    header_tokens = re.compile(
        r"(?i)\\b(?:doi|vol\\.?|volume|issue|no\\.|pages?|journal|published|copyright|"
        r"preprint|correspondence|supplementary|issn|www\\.|http|of\\s+\\d+)\\b"
    )
    if header_tokens.search(quote):
        return True
    if quote_start == 0:
        newline_density = quote.count("\n") / max(len(quote), 1)
        if newline_density > 0.02 or quote.count("\n") >= 2:
            return True
        if page_text and page and 0 < page <= len(page_text):
            page_start = page_text[page - 1][:200]
            if page_start and header_tokens.search(page_start):
                return True
            lines = [line.strip() for line in page_text[page - 1].splitlines() if line.strip()]
            edges = lines[:2] + lines[-2:]
            normalized_quote = normalize_for_matching(quote)
            for line in edges:
                line_norm = normalize_for_matching(line)
                if normalized_quote and (normalized_quote in line_norm or line_norm in normalized_quote):
                    return True
    return False


def _is_bibliographic_column(column: str) -> bool:
    normalized = normalize_for_matching(column)
    tokens = (
        "doi",
        "title",
        "author",
        "journal",
        "volume",
        "issue",
        "page",
        "year",
        "publisher",
        "citation",
        "reference",
    )
    return any(token in normalized for token in tokens)


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


def _ensure_evidence_pdf_id(evidence_list: list[Any], pdf_id: str) -> None:
    for evidence in evidence_list:
        if getattr(evidence, "pdf_id", None) != pdf_id:
            setattr(evidence, "pdf_id", pdf_id)
        quote = getattr(evidence, "quote", None) or getattr(evidence, "quote_text", None) or getattr(evidence, "quote_raw", None)
        if quote and not getattr(evidence, "quote", None):
            setattr(evidence, "quote", str(quote))


def _legacy_chunk_pk(chunk_id: str) -> str | None:
    if not chunk_id:
        return None
    normalized = normalize_chunk_id(chunk_id)
    if not normalized:
        return None
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def _should_downgrade_unanchored_found(proposal: Any) -> bool:
    status = str(getattr(proposal, "status", "") or "")
    if status != "found":
        return False
    proposed_value = getattr(proposal, "proposed_value", None)
    if proposed_value is None or str(proposed_value).strip() == "":
        return False
    evidence_list = getattr(proposal, "evidence", None) or []
    if not evidence_list:
        return True
    quotes = [
        str(getattr(evidence, "quote", None) or getattr(evidence, "quote_text", None) or "")
        for evidence in evidence_list
    ]
    return not _evidence_supports_value(proposed_value, quotes, column=getattr(proposal, "column", None))


def _evidence_supports_value(
    proposed_value: str | object,
    quotes: list[str],
    *,
    column: str | None = None,
) -> bool:
    value = str(proposed_value).strip()
    if not value or not quotes:
        return False
    value_norm = normalize_for_matching(value)
    if not value_norm:
        return False
    numeric_parts = _extract_numeric_parts(value)
    units = _extract_units(value)
    for quote in quotes:
        quote_text = str(quote or "")
        quote_norm = normalize_for_matching(quote_text)
        if not quote_norm:
            continue
        if value_norm in quote_norm:
            return True
        if numeric_parts:
            if any(part in quote_text for part in numeric_parts):
                if units:
                    if any(unit in quote_text.lower() for unit in units):
                        return True
                else:
                    return True
        else:
            key_terms = _extract_key_terms(value)
            if key_terms and any(term in quote_norm for term in key_terms):
                return True
    return False


def _extract_numeric_parts(text: str) -> list[str]:
    return re.findall(r"\\d+(?:\\.\\d+)?", text)


def _extract_units(text: str) -> list[str]:
    units: list[str] = []
    for match in re.finditer(r"\\d+(?:\\.\\d+)?\\s*([a-zA-Z%µμ°]+)", text):
        unit = match.group(1).lower()
        if unit:
            units.append(unit)
    return units


def _extract_key_terms(text: str) -> list[str]:
    normalized = normalize_for_matching(normalize_unicode(text))
    if not normalized:
        return []
    tokens = re.findall(r"[a-z0-9]{3,}", normalized)
    return tokens[:6]
