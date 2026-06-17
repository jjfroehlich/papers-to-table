"""Batch 3: Extraction orchestrator — per-cell proposal generation with evidence.

T053  – Extraction request builder
T053a – Concise markdown-bullet rationale
T054  – Text-model structured payload
T055  – Vision-model structured payload
T056  – Proposal/evidence serialization
T057  – Per-cell extraction orchestrator
T057a – Long-text field handling
T058  – Proposal state handling (found/inferred/unclear/blocked/error/skipped)
T058a – Anti-guessing rule
T059  – Text-evidence anchoring and highlight production
T060  – Evidence-recovery pass
T061  – Weak-but-reviewable proposals with quote+page fallback
T062  – Proactive figure review when vision model is configured
T063  – Figure input package
T064  – Persist figure-derived evidence distinctly
T065  – Reviewer-facing support-label mapping and evidence type labeling
T066  – Verify mode uses same extraction path
"""

from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from .artifacts import (
    EVIDENCE_RECORD_SCHEMA_VERSION,
    append_jsonl,
    hash_json_data,
    read_json,
    read_jsonl,
    write_json,
)
from .ids import generate_evidence_id, generate_proposal_id
from .prompts import get_prompt_bundle, load_prompt_text, render_prompt_template
from .provider import (
    ProviderAdapter,
)
from .retrieval import RetrievalResult
from .schemas import (
    EvidenceStatus,
    EvidenceSourceType,
    NumericValueForm,
    ProposalStatus,
    ReviewBucket,
    SchemaFieldType,
)
from .metadata import resolve_metadata_field
from .proposal_semantics import (
    ANCHOR_FALLBACK,
    APPROXIMATE_ANCHOR,
    CALCULATION,
    CELL_NOT_TARGETED,
    CONFLICTING_EVIDENCE,
    INSUFFICIENT_EVIDENCE,
    INVALID_MODEL_OUTPUT,
    PROVIDER_ERROR,
    RETRIEVAL_EMPTY,
    build_semantics,
    semantics_from_extraction,
    validate_proposal_semantics,
)
from .style_profiles import StyleProfile


# ---------------------------------------------------------------------------
# Evidence record (extended contract for Batch 3)
# ---------------------------------------------------------------------------

class EvidenceRecord(BaseModel):
    evidence_schema_version: str = EVIDENCE_RECORD_SCHEMA_VERSION
    evidence_id: str
    run_id: str
    proposal_id: str
    pdf_id: str
    source_type: EvidenceSourceType
    quote_text: Optional[str] = None
    page_number: Optional[int] = None
    exact_highlight_regions: Optional[list[dict]] = None   # [{x0,y0,x1,y1,page}]
    approximate_highlight_regions: Optional[list[dict]] = None
    figure_ref: Optional[str] = None
    caption_text: Optional[str] = None
    crop_path: Optional[str] = None
    full_page_path: Optional[str] = None
    anchor_confidence: float = 0.0
    evidence_rank: int = 1   # 1 = primary, higher = supporting
    reasoning: Optional[str] = None
    is_primary: bool = False
    is_figure_derived: bool = False
    run_mode: str = "normal"
    prompt_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    schema_hash: Optional[str] = None
    schema_version: Optional[str] = None
    config_hash: Optional[str] = None
    config_snapshot_path: Optional[str] = None
    parser_identity: Optional[str] = None
    parser_version: Optional[str] = None
    text_model_id: Optional[str] = None
    vision_model_id: Optional[str] = None
    vision_context_bundle: Optional[dict] = None
    vision_trigger_reasons: Optional[list[str]] = None
    shortlist_metadata: Optional[dict] = None
    created_at: str


# ---------------------------------------------------------------------------
# Proposal record (extended contract for Batch 3)
# ---------------------------------------------------------------------------

class ProposalRecord(BaseModel):
    proposal_id: str
    run_id: str
    pdf_id: str
    row_id: str
    column_name: str
    cell_id: str
    proposal_status: ProposalStatus
    evidence_status: EvidenceStatus
    review_bucket: ReviewBucket
    reason_codes: list[str] = []
    proposed_value: Optional[str] = None
    rationale: Optional[str] = None
    calculation: Optional[str] = None
    primary_evidence_id: Optional[str] = None
    ordered_supporting_evidence_ids: list[str] = []
    evidence_ids: list[str] = []
    warning_flags: list[str] = []
    needs_more_evidence: bool = False
    is_verify_mode: bool = False
    existing_value: Optional[str] = None   # for verify mode comparison
    field_type: Optional[SchemaFieldType] = None
    allowed_values: Optional[list[str]] = None
    numeric_value_form: Optional[NumericValueForm] = None
    recall_rescue_used: bool = False
    whole_document_used: bool = False
    provider_mode: str = "unknown"
    run_mode: str = "normal"
    prompt_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    schema_hash: Optional[str] = None
    schema_version: Optional[str] = None
    config_hash: Optional[str] = None
    config_snapshot_path: Optional[str] = None
    parser_identity: Optional[str] = None
    parser_version: Optional[str] = None
    text_model_id: Optional[str] = None
    vision_model_id: Optional[str] = None
    gold_table_source_reference: Optional[str] = None
    gold_table_hash: Optional[str] = None
    gold_table_snapshot_path: Optional[str] = None
    masked_working_table_path: Optional[str] = None
    masked_working_table_hash: Optional[str] = None
    vision_trigger_reasons: list[str] = []
    vision_shortlist: Optional[list[dict]] = None
    provider_diagnostics: Optional[dict] = None
    retrieval_diagnostics: Optional[dict] = None
    figure_review_diagnostics: Optional[dict] = None
    figure_planner_diagnostics: Optional[dict] = None
    extraction_lane: str = "content"
    failure_attribution: Optional[str] = None
    fallback_reasons: list[str] = []
    metadata_diagnostics: Optional[dict] = None
    style_profile_mode: Optional[str] = None
    candidate_answers: Optional[list[dict]] = None
    selection_diagnostics: Optional[dict] = None
    created_at: str

    @model_validator(mode="after")
    def _validate_semantics(self) -> "ProposalRecord":
        semantics = validate_proposal_semantics(
            self.proposal_status,
            self.evidence_status,
            self.review_bucket,
            self.reason_codes,
        )
        self.reason_codes = semantics.reason_codes
        return self


class CandidateAnswer(BaseModel):
    candidate_id: str
    value: Optional[str] = None
    candidate_status: str = "unclear"
    source: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence_rationale: Optional[str] = None
    warning_flags: list[str] = Field(default_factory=list)


class RecallRescueDecision(BaseModel):
    eligible: bool
    trigger_reasons: list[str] = Field(default_factory=list)
    skip_reason: Optional[str] = None


class FigureReviewHit(BaseModel):
    proposed_value: str
    state: str = "inferred"
    rationale: Optional[str] = None
    numeric_value_form: Optional[NumericValueForm] = None
    evidence: EvidenceRecord
    warning_flags: list[str] = Field(default_factory=list)


class FigurePlannerTarget(BaseModel):
    figure_ref: str
    preferred_image: str = "crop"
    reason: Optional[str] = None


class FigurePlannerDecision(BaseModel):
    attempted: bool = False
    succeeded: bool = False
    needs_vision: bool = False
    target_figures: list[FigurePlannerTarget] = Field(default_factory=list)
    rejected_figures: list[dict] = Field(default_factory=list)
    vision_question: Optional[str] = None
    planner_confidence: Optional[str] = None
    skip_reason: Optional[str] = None
    fallback_to_heuristic_shortlist: bool = False
    failure_reason: Optional[str] = None


@dataclass
class FigureImageSelection:
    image_b64: Optional[str]
    image_source: Optional[str]
    image_path: Optional[str]
    failure_reason: Optional[str]
    crop_quality: Optional[str]
    fallback_reason: Optional[str]


@dataclass
class FigureReference:
    reference_text: str
    figure_numbers: list[int]
    panel_hint: Optional[str]
    context_snippet: str


@dataclass
class FigureShortlistCandidate:
    figure: dict
    total_score: float
    caption_score: float
    reference_score: float
    nearby_context_score: float
    confidence: str
    matched_reference_snippets: list[str]
    retrieved_context_snippets: list[str]
    nearby_context_excerpt: Optional[str]
    section_context: Optional[str]
    rationale: list[str]


# ---------------------------------------------------------------------------
EVIDENCE_TYPE_DISPLAY = {
    EvidenceSourceType.direct_quote: "Direct quote",
    EvidenceSourceType.inferred_reasoning: "Inferred reasoning",
    EvidenceSourceType.calculation: "Calculation",
    EvidenceSourceType.approximate_highlight: "Approximate highlight",
    EvidenceSourceType.quote_plus_page: "Quote + page (fallback)",
    EvidenceSourceType.caption_grounded_figure_evidence: "Caption-grounded figure evidence",
    EvidenceSourceType.visual_interpretation_figure_evidence: "Visual-interpretation figure evidence",
}


def evidence_type_display(source_type: EvidenceSourceType) -> str:
    return EVIDENCE_TYPE_DISPLAY.get(source_type, source_type.value)


# ---------------------------------------------------------------------------
# Structured output schemas (T054, T055)
# ---------------------------------------------------------------------------

# Text-model extraction response schema
TEXT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "proposed_value": {
            "type": ["string", "null"],
            "description": "The extracted value. null if not found.",
        },
        "state": {
            "type": "string",
            "enum": ["found", "inferred", "unclear"],
            "description": "Extraction outcome state.",
        },
        "rationale": {
            "type": ["string", "null"],
            "description": "Concise markdown-bullet rationale (≤3 bullets). null if not applicable.",
        },
        "calculation": {
            "type": ["string", "null"],
            "description": "Calculation or derivation if value was computed. null otherwise.",
        },
        "numeric_value_form": {
            "type": ["string", "null"],
            "enum": ["exact", "range", "approximate", None],
            "description": "Required when the target field is numeric.",
        },
        "quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "page": {"type": ["integer", "null"]},
                    "source_type": {
                        "type": "string",
                        "enum": [
                            "direct_quote",
                            "inferred_reasoning",
                            "calculation",
                        ],
                    },
                },
                "required": ["text", "source_type"],
            },
            "description": "Evidence quotes supporting the proposed value.",
        },
    },
    "required": ["proposed_value", "state", "rationale", "calculation", "numeric_value_form", "quotes"],
}

COMPACT_DEGRADED_TEXT_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "proposed_value": {
            "type": ["string", "null"],
            "description": "The extracted value. null if not found.",
        },
        "state": {
            "type": "string",
            "enum": ["found", "inferred", "unclear"],
            "description": "Extraction outcome state.",
        },
        "numeric_value_form": {
            "type": ["string", "null"],
            "enum": ["exact", "range", "approximate", None],
            "description": "Required when the target field is numeric.",
        },
        "primary_quote": {
            "type": ["string", "null"],
            "description": "One best supporting quote. null if unclear.",
        },
        "primary_quote_page": {
            "type": ["integer", "null"],
            "description": "Page number for the supporting quote when known.",
        },
        "evidence_kind": {
            "type": "string",
            "enum": ["direct_quote", "inferred_reasoning", "calculation", "none"],
            "description": "Evidence type for the primary supporting quote.",
        },
        "rationale": {
            "type": ["string", "null"],
            "description": "Optional concise markdown-bullet rationale.",
        },
        "calculation": {
            "type": ["string", "null"],
            "description": "Optional calculation or derivation if value was computed.",
        },
    },
    "required": [
        "proposed_value",
        "state",
        "numeric_value_form",
        "primary_quote",
        "primary_quote_page",
        "evidence_kind",
    ],
}

# Vision-model extraction response schema (T055) — same structure, different context
VISION_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "proposed_value": {
            "type": ["string", "null"],
        },
        "state": {
            "type": "string",
            "enum": ["found", "inferred", "unclear"],
        },
        "rationale": {
            "type": ["string", "null"],
        },
        "numeric_value_form": {
            "type": ["string", "null"],
            "enum": ["exact", "range", "approximate", None],
        },
        "figure_description": {
            "type": ["string", "null"],
            "description": "What the figure shows that supports the value.",
        },
        "caption_relevant": {
            "type": ["boolean", "null"],
            "description": "Whether the figure caption directly supports the value.",
        },
    },
    "required": [
        "proposed_value",
        "state",
        "rationale",
        "numeric_value_form",
        "figure_description",
    ],
}

FIGURE_PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_vision": {"type": "boolean"},
        "target_figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "figure_ref": {"type": "string"},
                    "preferred_image": {"type": "string", "enum": ["crop", "full_page"]},
                    "reason": {"type": ["string", "null"]},
                },
                "required": ["figure_ref", "preferred_image", "reason"],
            },
        },
        "rejected_figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "figure_ref": {"type": "string"},
                    "reason": {"type": ["string", "null"]},
                },
                "required": ["figure_ref", "reason"],
            },
        },
        "vision_question": {"type": ["string", "null"]},
        "planner_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "skip_reason": {"type": ["string", "null"]},
    },
    "required": [
        "needs_vision",
        "target_figures",
        "rejected_figures",
        "vision_question",
        "planner_confidence",
        "skip_reason",
    ],
}

CANDIDATE_SELECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_candidate_id": {"type": ["string", "null"]},
        "selected_value": {"type": ["string", "null"]},
        "selected_state": {"type": "string", "enum": ["found", "inferred", "unclear"]},
        "rejected_candidate_ids": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": ["string", "null"]},
        "needs_more_evidence": {"type": "boolean"},
    },
    "required": [
        "selected_candidate_id",
        "selected_value",
        "selected_state",
        "rejected_candidate_ids",
        "rationale",
        "needs_more_evidence",
    ],
}


def _select_text_extraction_schema(caps: Any) -> tuple[dict[str, Any], str]:
    structured_mode = getattr(caps, "structured_output_mode", None)
    if structured_mode == "json_schema":
        return TEXT_EXTRACTION_SCHEMA, "full"
    return COMPACT_DEGRADED_TEXT_EXTRACTION_SCHEMA, "compact_degraded"


def _normalize_text_extraction_result(raw_result: dict[str, Any], schema_profile: str) -> dict[str, Any]:
    normalized = dict(raw_result)
    if schema_profile == "full":
        return normalized

    if "quotes" not in normalized:
        primary_quote = _coerce_text_value(normalized.get("primary_quote"), joiner=" ")
        evidence_kind = _coerce_text_value(normalized.get("evidence_kind"), joiner="_") or "none"
        if primary_quote and evidence_kind != "none":
            normalized["quotes"] = [
                {
                    "text": primary_quote,
                    "page": normalized.get("primary_quote_page"),
                    "source_type": evidence_kind,
                }
            ]
        else:
            normalized["quotes"] = []

    normalized.setdefault("rationale", None)
    normalized.setdefault("calculation", None)
    normalized.setdefault("numeric_value_form", None)
    return normalized


# ---------------------------------------------------------------------------
# Prompt building (T053, T053a, T057a)
# ---------------------------------------------------------------------------

PROMPT_VERSION: Optional[str] = None


def get_prompt_identity(
    *,
    prompt_bundle_name: Optional[str] = None,
    prompt_bundle_path: Optional[str] = None,
) -> dict[str, object]:
    prompt_bundle = get_prompt_bundle(bundle=prompt_bundle_name, bundle_path=prompt_bundle_path)
    payload = {
        "prompt_bundle_hash": prompt_bundle["bundle_hash"],
        "prompt_manifest_hash": prompt_bundle["manifest_hash"],
        "prompt_bundle_id": prompt_bundle["bundle_id"],
        "prompt_bundle_version": prompt_bundle.get("bundle_version"),
        "prompt_keys": prompt_bundle.get("prompt_keys", []),
        "prompt_files": prompt_bundle["prompt_files"],
        "text_schema": TEXT_EXTRACTION_SCHEMA,
        "figure_schema": VISION_EXTRACTION_SCHEMA,
    }
    return {
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": hash_json_data(payload),
        "prompt_bundle_id": prompt_bundle["bundle_id"],
        "prompt_bundle_version": prompt_bundle.get("bundle_version"),
        "prompt_bundle_path": prompt_bundle["bundle_path"],
        "prompt_manifest_hash": prompt_bundle["manifest_hash"],
        "prompt_bundle_hash": prompt_bundle["bundle_hash"],
        "prompt_keys_used": prompt_bundle.get("prompt_keys", []),
        "prompt_files": prompt_bundle["prompt_files"],
    }


def _build_style_guidance(profile: Optional[StyleProfile]) -> str:
    if profile is None:
        return ""
    parts = ["\nFormat guidance (shape and style only, not content):"]
    parts.append(f"- Expected length: {profile.expected_length}")
    parts.append(f"- Value shape: {profile.value_shape}")
    if profile.unit_style:
        parts.append(f"- Unit style: {profile.unit_style}")
    if profile.format_notes:
        parts.append(f"- Format notes: {profile.format_notes}")
    return "\n".join(parts)


def _build_context_block(retrieval: Optional[RetrievalResult]) -> str:
    if retrieval is None or not retrieval.chunks:
        return "No retrieved context available."
    parts = ["Relevant passages from the paper:"]
    for i, chunk in enumerate(retrieval.chunks[:10], 1):
        tag_parts = [chunk.chunk_type.upper(), f"page {chunk.page_number}"]
        if chunk.section_context:
            tag_parts.append(f"section: {chunk.section_context}")
        if chunk.figure_ref:
            tag_parts.append(f"figure: {chunk.figure_ref}")
        if chunk.chunk_type == "table_region":
            tag_parts.append("table")
        tag = f"[{'; '.join(tag_parts)}]"
        neighbor_tag = " (context)" if chunk.is_neighbor else ""
        parts.append(f"\n--- Passage {i}{neighbor_tag} {tag} ---\n{chunk.display_text}")
    return "\n".join(parts)


def _build_field_contract(
    field_type: Optional[SchemaFieldType],
    allowed_values: Optional[list[str]],
) -> str:
    if field_type is None:
        return ""
    parts = [f"\nSchema contract:\n- field_type: {field_type.value}"]
    if field_type == SchemaFieldType.categorical and allowed_values:
        parts.append("- allowed_values: " + ", ".join(allowed_values))
    elif field_type == SchemaFieldType.number:
        parts.append("- numeric_value_form: exact, range, or approximate")
    return "\n".join(parts)


def build_text_extraction_prompt(
    column_name: str,
    column_description: str,
    row_context: dict,
    retrieval: Optional[RetrievalResult],
    style_profile: Optional[StyleProfile],
    field_type: Optional[SchemaFieldType] = None,
    allowed_values: Optional[list[str]] = None,
    whole_document_text: Optional[str] = None,
    is_verify_mode: bool = False,
    existing_value: Optional[str] = None,
    is_long_text: bool = False,
    prompt_bundle_name: Optional[str] = None,
    prompt_bundle_path: Optional[str] = None,
) -> list[dict]:
    """Build the text-model extraction prompt (T053, T053a, T057a)."""

    # Row context (metadata only — Title, Authors, Year if present)
    row_lines = []
    for key in ("Title", "Authors", "Publication Year"):
        if key in row_context and row_context[key]:
            row_lines.append(f"  {key}: {row_context[key]}")
    row_block = "\n".join(row_lines) if row_lines else "  (no row metadata)"

    verify_block = ""
    if is_verify_mode and existing_value:
        verify_block = (
            f"\n\nVerify mode: The existing table value is '{existing_value}'. "
            "Compare the evidence to this existing value and report whether the paper supports, "
            "contradicts, or is ambiguous about it."
        )

    # T057a: long-text fields get explicit instruction to return full text
    long_text_note = ""
    if is_long_text:
        long_text_note = (
            "\nThis field expects a longer narrative answer. "
            "Return the full extracted text without truncation. "
            "Do not summarize to a single sentence unless the paper only contains a sentence."
        )

    style_block = _build_style_guidance(style_profile)
    field_contract = _build_field_contract(field_type, allowed_values)
    context_block = _build_context_block(retrieval)
    whole_document_block = ""
    if whole_document_text:
        whole_document_block = (
            "\n\nWhole-document rescue context (use only because the first pass needed more evidence):\n"
            f"{whole_document_text}"
        )

    user_content = render_prompt_template(
        "text_extraction_user",
        {
            "column_name": column_name,
            "column_description": column_description,
            "row_block": row_block,
            "verify_block": verify_block,
            "long_text_note": long_text_note,
            "field_contract": field_contract,
            "style_block": style_block,
            "context_block": context_block,
            "whole_document_block": whole_document_block,
        },
        bundle=prompt_bundle_name,
        bundle_path=prompt_bundle_path,
    )

    return [
        {
            "role": "system",
            "content": load_prompt_text(
                "text_extraction_system",
                bundle=prompt_bundle_name,
                bundle_path=prompt_bundle_path,
            ),
        },
        {"role": "user", "content": user_content},
    ]


def build_figure_extraction_prompt(
    column_name: str,
    column_description: str,
    caption_text: Optional[str],
    nearby_text: Optional[str],
    retrieved_context_snippets: Optional[list[str]] = None,
    figure_reference_snippets: Optional[list[str]] = None,
    section_context: Optional[str] = None,
    field_type: Optional[SchemaFieldType] = None,
    allowed_values: Optional[list[str]] = None,
    prompt_bundle_name: Optional[str] = None,
    prompt_bundle_path: Optional[str] = None,
) -> list[dict]:
    """Build the vision-model figure extraction prompt (T063)."""
    caption_block = f"Figure caption: {caption_text}" if caption_text else "No caption available."
    nearby_block = f"Nearby text: {nearby_text[:400]}" if nearby_text else ""
    retrieval_block = ""
    if retrieved_context_snippets:
        retrieval_block = "\n".join(f"- {snippet}" for snippet in retrieved_context_snippets[:4])
        retrieval_block = f"Retrieved field passages:\n{retrieval_block}"
    reference_block = ""
    if figure_reference_snippets:
        reference_block = "\n".join(f"- {snippet}" for snippet in figure_reference_snippets[:4])
        reference_block = f"Figure-reference snippets from the paper:\n{reference_block}"
    section_block = f"Likely section context: {section_context}" if section_context else ""

    user_content = render_prompt_template(
        "figure_extraction_user",
        {
            "column_name": column_name,
            "column_description": column_description,
            "field_contract": _build_field_contract(field_type, allowed_values),
            "caption_block": caption_block,
            "nearby_block": nearby_block,
            "retrieval_block": retrieval_block,
            "reference_block": reference_block,
            "section_block": section_block,
        },
        bundle=prompt_bundle_name,
        bundle_path=prompt_bundle_path,
    )
    if retrieval_block and "Retrieved field passages:" not in user_content:
        user_content = f"{user_content.rstrip()}\n\n{retrieval_block}"
    if reference_block and "Figure-reference snippets from the paper:" not in user_content:
        user_content = f"{user_content.rstrip()}\n\n{reference_block}"
    if section_block and section_block not in user_content:
        user_content = f"{user_content.rstrip()}\n\n{section_block}"
    required_value_instruction = (
        "If state is 'found' or 'inferred', proposed_value must contain the extracted answer itself. "
        "Do not leave proposed_value null, blank, or filled with a placeholder when returning found/inferred."
    )
    if required_value_instruction not in user_content:
        user_content = f"{user_content.rstrip()}\n\n{required_value_instruction}"

    return [
        {
            "role": "system",
            "content": load_prompt_text(
                "figure_extraction_system",
                bundle=prompt_bundle_name,
                bundle_path=prompt_bundle_path,
            ),
        },
        {"role": "user", "content": user_content},
    ]


def build_candidate_selection_prompt(
    *,
    column_name: str,
    column_description: str,
    row_context: dict,
    candidates: list[CandidateAnswer],
) -> list[dict]:
    row_lines = []
    for key in ("Title", "Authors", "Publication Year"):
        if row_context.get(key):
            row_lines.append(f"- {key}: {row_context[key]}")
    candidate_payload = [candidate.model_dump(mode="json") for candidate in candidates]
    user = (
        "Select the best final answer for this table cell using only the candidate answers and their evidence IDs.\n"
        "Do not invent a new answer. If no candidate is adequately supported, select null and state unclear.\n\n"
        f"Column: {column_name}\n"
        f"Column description: {column_description}\n"
        f"Row context:\n{chr(10).join(row_lines) if row_lines else '- (none)'}\n\n"
        f"Candidate answers JSON:\n{json.dumps(candidate_payload, ensure_ascii=False, indent=2)}"
    )
    return [
        {
            "role": "system",
            "content": (
                "Return JSON only. Compare generic text, recovered, rescued, and figure candidates against the column contract. "
                "Do not select a figure-derived candidate over strong direct text evidence unless the figure candidate directly "
                "answers the requested field. Reject candidates that are related but answer a different semantic question."
            ),
        },
        {"role": "user", "content": user},
    ]


def _build_compact_figure_catalog(figures: list[dict], max_items: int = 40) -> list[dict]:
    catalog: list[dict] = []
    for figure in figures[:max_items]:
        catalog.append(
            {
                "figure_ref": figure.get("figure_id"),
                "page": figure.get("page_number"),
                "caption": str(figure.get("caption_text") or "")[:700],
                "section_context": figure.get("section_context"),
                "crop_available": bool(figure.get("crop_path")),
                "full_page_available": bool(figure.get("full_page_path")),
            }
        )
    return catalog


def _build_retrieved_snippet_payload(retrieval: Optional[RetrievalResult], max_items: int = 10) -> list[dict]:
    if retrieval is None:
        return []
    snippets: list[dict] = []
    for chunk in retrieval.chunks[:max_items]:
        snippets.append(
            {
                "chunk_type": chunk.chunk_type,
                "figure_ref": chunk.figure_ref,
                "page": chunk.page_number,
                "text": str(chunk.display_text or "")[:500],
            }
        )
    return snippets


def build_figure_planner_prompt(
    *,
    column_name: str,
    column_description: str,
    row_context: dict,
    proposed_value: Optional[str],
    rationale: Optional[str],
    retrieval: Optional[RetrievalResult],
    figures: list[dict],
) -> list[dict]:
    row_lines = []
    for key in ("Title", "Authors", "Publication Year"):
        if row_context.get(key):
            row_lines.append(f"- {key}: {row_context[key]}")
    payload = {
        "column_name": column_name,
        "column_description": column_description,
        "row_context": row_lines,
        "first_pass": {
            "proposed_value": proposed_value,
            "rationale": rationale,
        },
        "retrieved_snippets": _build_retrieved_snippet_payload(retrieval),
        "figure_catalog": _build_compact_figure_catalog(figures),
    }
    user = (
        "Decide whether image-based figure review is needed for this table cell. "
        "If it is needed, choose the most relevant available figures to inspect. "
        "Select figures that directly answer the cell request; do not select figures merely because they share a related keyword. "
        "Do not request vision for non-visual fields when retrieved text or caption snippets already answer the question. "
        "For text-primary fields, set needs_vision=false unless the text evidence is weak, unclear, contradictory, or missing. "
        "Selected figures must directly answer the requested field, not merely provide background context. "
        "Use full_page when the request depends on layout, panel counting, or full-figure context; otherwise prefer crop. "
        "Select at most two figures. Return JSON only.\n\n"
        f"Planning payload JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a generic figure-review planner for scientific table extraction. "
                "You choose whether vision is needed and which figures should be inspected. "
                "Do not invent figure refs; use only figure_ref values from the catalog."
            ),
        },
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Field-type helpers (T057a)
# ---------------------------------------------------------------------------

_LONG_TEXT_KEYWORDS = frozenset({
    "abstract", "description", "notes", "comment", "summary", "method",
    "protocol", "procedure", "conclusion", "discussion", "background",
    "introduction", "objective", "aim", "findings",
})


def is_long_text_field(column_name: str, column_description: str) -> bool:
    """Heuristic: is this field expected to hold a long narrative value?"""
    combined = (column_name + " " + column_description).lower()
    return any(kw in combined for kw in _LONG_TEXT_KEYWORDS)


def _normalize_numeric_value_form(
    raw_value: Optional[str],
    field_type: Optional[SchemaFieldType],
) -> Optional[NumericValueForm]:
    if field_type != SchemaFieldType.number or not raw_value:
        return None
    try:
        return NumericValueForm(raw_value)
    except ValueError:
        return None


def build_whole_document_context(
    doc_dict: dict,
    max_chars: int,
) -> Optional[str]:
    full_text = str(doc_dict.get("full_text", "") or "").strip()
    if not full_text or len(full_text) > max_chars:
        return None
    return full_text


# ---------------------------------------------------------------------------
# Text-evidence anchoring (T059)
# ---------------------------------------------------------------------------

def _normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def find_exact_highlight_regions(
    quote_text: str,
    doc_dict: dict,
    target_page: Optional[int] = None,
) -> tuple[list[dict], float, Optional[int]]:
    """Attempt exact quote matching against rendered page text.

    Returns (exact_regions, confidence, page_number).
    confidence=1.0 means exact match found, 0.0 means no match.

    T059: exact match from page text layer → exact_highlight_regions.
    """
    if not quote_text:
        return [], 0.0, None

    blocks = doc_dict.get("blocks", [])
    quote_norm = _normalize_for_match(quote_text[:500])   # cap for matching

    best_score = 0.0
    best_page: Optional[int] = None
    best_bbox: Optional[list[float]] = None

    for block in blocks:
        if target_page and block.get("page_number") != target_page:
            continue
        block_norm = _normalize_for_match(block.get("normalized_text", ""))
        if not block_norm:
            continue

        # Exact containment check
        if quote_norm in block_norm:
            best_score = 1.0
            best_page = block.get("page_number")
            best_bbox = block.get("bbox")
            break

        # Partial overlap (longest common substring ratio)
        overlap = _lcs_ratio(quote_norm[:100], block_norm[:500])
        if overlap > best_score:
            best_score = overlap
            best_page = block.get("page_number")
            best_bbox = block.get("bbox")

    if best_score >= 1.0 and best_bbox:
        region = {
            "x0": best_bbox[0], "y0": best_bbox[1],
            "x1": best_bbox[2], "y1": best_bbox[3],
            "page": best_page,
        }
        return [region], 1.0, best_page
    return [], best_score, best_page


def find_approximate_highlight_regions(
    quote_text: str,
    doc_dict: dict,
    target_page: Optional[int] = None,
) -> tuple[list[dict], float, Optional[int]]:
    """Derive approximate regions from parser geometry when exact match fails.

    T059: approximate match → approximate_highlight_regions.
    Labeled as approximate, never presented as exact.
    """
    if not quote_text:
        return [], 0.0, None

    blocks = doc_dict.get("blocks", [])
    quote_norm = _normalize_for_match(quote_text[:300])
    query_terms = set(quote_norm.split())

    best_overlap = 0.0
    best_page: Optional[int] = None
    best_bbox: Optional[list[float]] = None

    for block in blocks:
        if target_page and block.get("page_number") != target_page:
            continue
        if not block.get("bbox"):
            continue
        block_norm = _normalize_for_match(block.get("normalized_text", ""))
        block_terms = set(block_norm.split())
        if not block_terms:
            continue
        overlap = len(query_terms & block_terms) / max(len(query_terms), 1)
        if overlap > best_overlap:
            best_overlap = overlap
            best_page = block.get("page_number")
            best_bbox = block.get("bbox")

    if best_overlap >= 0.3 and best_bbox:
        region = {
            "x0": best_bbox[0], "y0": best_bbox[1],
            "x1": best_bbox[2], "y1": best_bbox[3],
            "page": best_page,
            "is_approximate": True,
        }
        return [region], best_overlap, best_page
    return [], 0.0, None


def _lcs_ratio(s1: str, s2: str) -> float:
    """Simple longest-common-substring ratio."""
    if not s1 or not s2:
        return 0.0
    # Fast word overlap as proxy
    w1 = set(s1.split())
    w2 = set(s2.split())
    if not w1:
        return 0.0
    return len(w1 & w2) / len(w1)


def anchor_evidence(
    quote_text: str,
    page_number: Optional[int],
    doc_dict: dict,
) -> tuple[EvidenceSourceType, list[dict], list[dict], float]:
    """Attempt evidence anchoring, returning (source_type, exact_regions, approx_regions, confidence).

    T059 anchoring chain:
    1. exact_highlight → source_type=direct_quote, confidence=1.0
    2. approximate_highlight → source_type=approximate_highlight, confidence<1.0
    3. quote_plus_page → source_type=quote_plus_page, confidence=0.0
    """
    exact_regions, exact_conf, found_page = find_exact_highlight_regions(
        quote_text, doc_dict, target_page=page_number
    )
    if exact_conf >= 0.9 and exact_regions:
        return EvidenceSourceType.direct_quote, exact_regions, [], exact_conf

    approx_regions, approx_conf, approx_page = find_approximate_highlight_regions(
        quote_text, doc_dict, target_page=page_number or found_page
    )
    if approx_conf >= 0.3 and approx_regions:
        return EvidenceSourceType.approximate_highlight, [], approx_regions, approx_conf

    # Fall back to quote+page (T061)
    return EvidenceSourceType.quote_plus_page, [], [], 0.0


# ---------------------------------------------------------------------------
# Evidence ranking (T065 + FR-6)
# ---------------------------------------------------------------------------

_EVIDENCE_AUTHORITY = {
    EvidenceSourceType.direct_quote: 1,
    EvidenceSourceType.calculation: 2,
    EvidenceSourceType.caption_grounded_figure_evidence: 3,
    EvidenceSourceType.inferred_reasoning: 4,
    EvidenceSourceType.visual_interpretation_figure_evidence: 5,
    EvidenceSourceType.approximate_highlight: 6,
    EvidenceSourceType.quote_plus_page: 7,
}


def rank_evidence(items: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Rank evidence items by source authority, assign evidence_rank.

    T065: most authoritative item gets rank=1 and is_primary=True.
    Authority order: direct_quote > calculation > caption_grounded_figure > inferred >
    visual_interpretation_figure > approx > q+p.
    """
    if not items:
        return items
    # Sort by authority (lower authority number = higher authority)
    sorted_items = sorted(
        items,
        key=lambda e: (_EVIDENCE_AUTHORITY.get(e.source_type, 99), e.evidence_rank),
    )
    result = []
    for i, ev in enumerate(sorted_items):
        result.append(ev.model_copy(update={"evidence_rank": i + 1, "is_primary": i == 0}))
    return result


# ---------------------------------------------------------------------------
# Proposal state adjudication (T058, T058a)
# ---------------------------------------------------------------------------

def adjudicate_state(
    raw_state: str,
    proposed_value: Optional[str],
    quotes: list[dict],
    is_verify_mode: bool = False,
) -> tuple[str, str]:
    """Map raw model state to str + str.

    T058a: prefer unclear over guesses with weak support.
    """
    normalized_value = _coerce_text_value(proposed_value, joiner="; ")
    if not normalized_value:
        return "unclear", "blocked"

    has_any_quote = bool(quotes)

    if raw_state == "found":
        if any(q.get("source_type") == "direct_quote" for q in quotes):
            return "found", "direct_evidence"
        if any(q.get("source_type") != "direct_quote" for q in quotes):
            return "found", "inferred_from_evidence"
        else:
            return "inferred", "inferred_from_evidence"

    elif raw_state == "inferred":
        if has_any_quote:
            return "inferred", "inferred_from_evidence"
        else:
            return "inferred", "weak_evidence"

    else:  # unclear or unknown
        return "unclear", "blocked"


def determine_support_label(
    state: str,
    evidence_records: list[EvidenceRecord],
    proposed_value: Optional[str] = None,
    field_type: Optional[SchemaFieldType] = None,
) -> str:
    if state == "error":
        return "error"
    if state in ("blocked", "skipped", "unclear"):
        return "blocked"
    if any(
        ev.source_type == EvidenceSourceType.direct_quote
        and _quote_directly_supports_value(ev.quote_text, proposed_value, field_type)
        for ev in evidence_records
    ):
        return "direct_evidence"
    if evidence_records:
        return "inferred_from_evidence"
    return "weak_evidence"


def _evidence_status_from_internal_support(
    *,
    state: str,
    support: str,
    evidence_records: list[EvidenceRecord],
    proposed_value: Optional[str],
    reason_codes: list[str],
) -> EvidenceStatus:
    if state == "error" or support == "error":
        return EvidenceStatus.not_applicable
    if state in {"blocked", "skipped"}:
        return EvidenceStatus.not_applicable
    if not evidence_records:
        return EvidenceStatus.no_evidence
    inferred = support == "inferred_from_evidence" or any(
        ev.source_type in {EvidenceSourceType.inferred_reasoning, EvidenceSourceType.calculation}
        for ev in evidence_records
    )
    weak = (
        support == "weak_evidence"
        or INSUFFICIENT_EVIDENCE in reason_codes
        or any(ev.source_type in {EvidenceSourceType.quote_plus_page, EvidenceSourceType.approximate_highlight} for ev in evidence_records)
    )
    if inferred:
        return EvidenceStatus.inferred_weak if weak else EvidenceStatus.inferred_strong
    return EvidenceStatus.direct_weak if weak else EvidenceStatus.direct_strong


def _canonical_semantics_kwargs(
    *,
    state: str,
    support: str,
    proposed_value: Optional[str],
    evidence_records: list[EvidenceRecord],
    reason_codes: list[str],
) -> dict[str, object]:
    evidence_status = _evidence_status_from_internal_support(
        state=state,
        support=support,
        evidence_records=evidence_records,
        proposed_value=proposed_value,
        reason_codes=reason_codes,
    )
    semantics = semantics_from_extraction(
        raw_state=state,
        evidence_status_hint=evidence_status.value,
        proposed_value=proposed_value,
        evidence_count=len(evidence_records),
        reason_codes=reason_codes,
    )
    return {
        "proposal_status": semantics.proposal_status,
        "evidence_status": semantics.evidence_status,
        "review_bucket": semantics.review_bucket,
        "reason_codes": semantics.reason_codes,
    }


def _semantics_fields(
    proposal_status: ProposalStatus | str,
    evidence_status: EvidenceStatus | str,
    reason_codes: list[str] | None = None,
) -> dict[str, object]:
    semantics = build_semantics(proposal_status, evidence_status, reason_codes or [])
    return {
        "proposal_status": semantics.proposal_status,
        "evidence_status": semantics.evidence_status,
        "review_bucket": semantics.review_bucket,
        "reason_codes": semantics.reason_codes,
    }


def _normalize_support_text(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = re.sub(r"[^a-z0-9.%\s-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _normalize_support_tokens(text: Optional[str]) -> set[str]:
    normalized = _normalize_support_text(text)
    tokens = set()
    for token in normalized.split():
        if len(token) > 3 and token.endswith("s"):
            token = token[:-1]
        tokens.add(token)
    return tokens


def _quote_directly_supports_value(
    quote_text: Optional[str],
    proposed_value: Optional[str],
    field_type: Optional[SchemaFieldType],
) -> bool:
    if not quote_text or not proposed_value:
        return False
    quote_norm = _normalize_support_text(quote_text)
    value_norm = _normalize_support_text(proposed_value)
    if not quote_norm or not value_norm:
        return False
    if value_norm in quote_norm:
        return True

    quote_tokens = _normalize_support_tokens(quote_text)
    value_tokens = _normalize_support_tokens(proposed_value)
    if not value_tokens:
        return False
    overlap = len(quote_tokens & value_tokens) / len(value_tokens)
    # Numeric answers should match all normalized value tokens exactly, while
    # text/categorical answers allow limited phrasing variation once most of the
    # proposed-value tokens are grounded in the quote.
    threshold = 1.0 if field_type == SchemaFieldType.number else 0.66
    return overlap >= threshold


# ---------------------------------------------------------------------------
# Evidence recovery pass (T060)
# ---------------------------------------------------------------------------

async def attempt_evidence_recovery(
    proposal_id: str,
    run_id: str,
    pdf_id: str,
    column_name: str,
    column_description: str,
    retrieval: Optional[RetrievalResult],
    doc_dict: dict,
    provider: ProviderAdapter,
    text_model_id: str,
    caps,  # ProviderCapabilities
    prompt_bundle_name: Optional[str] = None,
    prompt_bundle_path: Optional[str] = None,
) -> Optional[EvidenceRecord]:
    """One narrow recovery pass when initial evidence is missing or unusable.

    T060: single bounded recovery attempt, not a retry loop.
    Asks the model to produce a quote that can be anchored.
    """
    if retrieval is None or not retrieval.chunks:
        return None

    context_passages = "\n".join(
        f"[page {c.page_number}] {c.display_text}" for c in retrieval.chunks[:6]
    )
    recovery_messages = [
        {
            "role": "system",
            "content": load_prompt_text(
                "evidence_recovery_system",
                bundle=prompt_bundle_name,
                bundle_path=prompt_bundle_path,
            ),
        },
        {
            "role": "user",
            "content": render_prompt_template(
                "evidence_recovery_user",
                {
                    "column_name": column_name,
                    "column_description": column_description,
                    "context_passages": context_passages,
                },
                bundle=prompt_bundle_name,
                bundle_path=prompt_bundle_path,
            ),
        },
    ]

    recovery_schema = {
        "type": "object",
        "properties": {
            "quote": {"type": "string"},
            "page": {"type": ["integer", "null"]},
        },
        "required": ["quote", "page"],
    }

    try:
        result = await provider.chat_complete_structured(
            messages=recovery_messages,
            response_schema=recovery_schema,
            model_id=text_model_id,
            max_tokens=256,
        )
        quote_text = _coerce_text_value(result.get("quote"), joiner=" ") or ""
        page_num = result.get("page")
        if not quote_text:
            return None

        source_type, exact_regions, approx_regions, confidence = anchor_evidence(
            quote_text, page_num, doc_dict
        )
        resolved_page = (
            (exact_regions[0].get("page") if exact_regions else None)
            or (approx_regions[0].get("page") if approx_regions else None)
            or page_num
        )

        ev_id = generate_evidence_id(proposal_id)
        return EvidenceRecord(
            evidence_id=ev_id,
            run_id=run_id,
            proposal_id=proposal_id,
            pdf_id=pdf_id,
            source_type=source_type,
            quote_text=quote_text,
            page_number=resolved_page,
            exact_highlight_regions=exact_regions or None,
            approximate_highlight_regions=approx_regions or None,
            anchor_confidence=confidence,
            evidence_rank=99,  # will be re-ranked
            is_primary=False,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Figure review (T062, T063, T064)
# ---------------------------------------------------------------------------

def _caption_relevance_score(caption: Optional[str], column_name: str, column_description: str) -> float:
    """Heuristic relevance of a figure caption to a column query."""
    if not caption:
        return 0.0
    query_terms = set(re.findall(r"[a-z0-9]+", (column_name + " " + column_description).lower()))
    caption_terms = set(re.findall(r"[a-z0-9]+", caption.lower()))
    if not query_terms:
        return 0.0
    overlap = len(query_terms & caption_terms) / len(query_terms)
    return overlap


_FIGURE_REF_PATTERN = re.compile(
    r"\b(?:fig(?:ure)?\.?\s*)(\d+)([a-z])?(?:\s*[-–]\s*([a-z]))?\b",
    re.IGNORECASE,
)


def _extract_figure_number(figure: dict) -> Optional[int]:
    for source in (figure.get("caption_text"), figure.get("figure_id")):
        if not source:
            continue
        match = re.search(r"(?:fig(?:ure)?\D*)(\d+)", str(source), flags=re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return None


def _extract_figure_references_from_text(text: str) -> list[FigureReference]:
    references: list[FigureReference] = []
    if not text:
        return references
    for m in _FIGURE_REF_PATTERN.finditer(text):
        nums: list[int] = []
        try:
            nums.append(int(m.group(1)))
        except ValueError:
            continue
        panel_hint = None
        start_panel = m.group(2)
        end_panel = m.group(3)
        if start_panel and end_panel:
            panel_hint = f"{start_panel}-{end_panel}"
        elif start_panel:
            panel_hint = start_panel

        start = max(0, m.start() - 140)
        end = min(len(text), m.end() + 220)
        snippet = text[start:end].strip()
        references.append(
            FigureReference(
                reference_text=m.group(0),
                figure_numbers=nums,
                panel_hint=panel_hint,
                context_snippet=snippet[:500],
            )
        )
    return references


def _safe_overlap_score(source_text: str, query_terms: set[str]) -> float:
    if not source_text or not query_terms:
        return 0.0
    src_terms = set(re.findall(r"[a-z0-9]+", source_text.lower()))
    if not src_terms:
        return 0.0
    return len(src_terms & query_terms) / len(query_terms)


def _collect_retrieved_context_snippets(retrieval: Optional[RetrievalResult], max_items: int = 4) -> list[str]:
    if retrieval is None:
        return []
    snippets: list[str] = []
    for chunk in retrieval.chunks[:max_items]:
        snippets.append(chunk.display_text[:300])
    return snippets


def _collect_retrieval_reference_snippets(retrieval: Optional[RetrievalResult]) -> list[FigureReference]:
    if retrieval is None:
        return []
    refs: list[FigureReference] = []
    for chunk in retrieval.chunks:
        refs.extend(_extract_figure_references_from_text(chunk.display_text))
    return refs


def _retrieved_figure_chunk_score(figure: dict, retrieval: Optional[RetrievalResult]) -> float:
    if retrieval is None:
        return 0.0
    figure_ref = str(figure.get("figure_id") or "")
    figure_no = _extract_figure_number(figure)
    for chunk in retrieval.chunks:
        if chunk.chunk_type != "figure":
            continue
        if figure_ref and chunk.figure_ref == figure_ref:
            return 1.0
        if figure_no is not None and figure_no == _extract_figure_number({"figure_id": chunk.figure_ref, "caption_text": chunk.caption_text}):
            return 0.85
    return 0.0


def _collect_document_reference_snippets(doc_dict: dict) -> list[FigureReference]:
    refs: list[FigureReference] = []
    for block in doc_dict.get("blocks", []):
        if block.get("block_type") not in ("paragraph", "caption", "section_heading", "heading"):
            continue
        refs.extend(_extract_figure_references_from_text(str(block.get("text", ""))))
    return refs


def _score_figure_candidate(
    figure: dict,
    column_name: str,
    column_description: str,
    retrieval: Optional[RetrievalResult],
    doc_dict: dict,
) -> FigureShortlistCandidate:
    query_terms = set(re.findall(r"[a-z0-9]+", (column_name + " " + column_description).lower()))
    caption = str(figure.get("caption_text") or "")
    caption_score = _caption_relevance_score(caption, column_name, column_description)

    retrieval_refs = _collect_retrieval_reference_snippets(retrieval)
    document_refs = _collect_document_reference_snippets(doc_dict)
    all_refs = retrieval_refs + document_refs

    figure_no = _extract_figure_number(figure)
    matched_refs: list[FigureReference] = []
    if figure_no is not None:
        matched_refs = [ref for ref in all_refs if figure_no in ref.figure_numbers]
    reference_score = min(1.0, 0.25 * len(matched_refs)) if matched_refs else 0.0

    nearby_context = _find_nearby_text(str(figure.get("figure_id", "")), doc_dict, window=3)
    nearby_context_score = _safe_overlap_score(nearby_context or "", query_terms)
    retrieved_figure_score = _retrieved_figure_chunk_score(figure, retrieval)

    total = (
        (0.35 * caption_score)
        + (0.25 * reference_score)
        + (0.20 * nearby_context_score)
        + (0.20 * retrieved_figure_score)
    )
    if total >= 0.65:
        confidence = "high"
    elif total >= 0.35:
        confidence = "medium"
    else:
        confidence = "low"

    rationale: list[str] = []
    if caption_score > 0:
        rationale.append(f"caption_overlap={caption_score:.2f}")
    if reference_score > 0:
        rationale.append(f"figure_refs={len(matched_refs)}")
    if nearby_context_score > 0:
        rationale.append(f"nearby_context_overlap={nearby_context_score:.2f}")
    if retrieved_figure_score > 0:
        rationale.append(f"retrieved_figure_chunk={retrieved_figure_score:.2f}")

    retrieved_context_snippets = _collect_retrieved_context_snippets(retrieval)
    section_context = None
    if retrieval is not None and retrieval.chunks:
        section_context = next((c.section_context for c in retrieval.chunks if c.section_context), None)

    return FigureShortlistCandidate(
        figure=figure,
        total_score=total,
        caption_score=caption_score,
        reference_score=reference_score,
        nearby_context_score=nearby_context_score,
        confidence=confidence,
        matched_reference_snippets=[ref.context_snippet for ref in matched_refs[:4]],
        retrieved_context_snippets=retrieved_context_snippets,
        nearby_context_excerpt=(nearby_context[:500] if nearby_context else None),
        section_context=section_context,
        rationale=rationale,
    )


def select_relevant_figures(
    figures: list[dict],
    column_name: str,
    column_description: str,
    retrieval: Optional[RetrievalResult] = None,
    doc_dict: Optional[dict] = None,
    max_figures: int = 5,
) -> list[dict]:
    """Select relevant figures using caption + references + local context scoring."""
    if not figures:
        return []
    parsed_doc = doc_dict or {"blocks": [], "figures": figures}
    candidates = [
        _score_figure_candidate(
            figure=fig,
            column_name=column_name,
            column_description=column_description,
            retrieval=retrieval,
            doc_dict=parsed_doc,
        )
        for fig in figures
    ]
    candidates.sort(key=lambda c: c.total_score, reverse=True)

    selected: list[FigureShortlistCandidate] = []
    if candidates and candidates[0].confidence == "high":
        selected.append(candidates[0])
        if len(candidates) > 1 and candidates[1].total_score >= (candidates[0].total_score - 0.12):
            selected.append(candidates[1])
    elif candidates and candidates[0].confidence == "medium":
        selected.extend(candidates[:2])
    elif candidates:
        # Bounded widening only when confidence is low.
        selected.extend(candidates[: min(2, len(candidates))])

    return [candidate.figure for candidate in selected[:max_figures]]


def build_figure_shortlist(
    figures: list[dict],
    column_name: str,
    column_description: str,
    retrieval: Optional[RetrievalResult],
    doc_dict: dict,
    max_figures: int,
) -> list[FigureShortlistCandidate]:
    candidates = [
        _score_figure_candidate(
            figure=fig,
            column_name=column_name,
            column_description=column_description,
            retrieval=retrieval,
            doc_dict=doc_dict,
        )
        for fig in figures
    ]
    candidates.sort(key=lambda c: c.total_score, reverse=True)
    if not candidates:
        return []

    shortlist: list[FigureShortlistCandidate] = []
    if candidates[0].confidence == "high":
        shortlist.append(candidates[0])
        if len(candidates) > 1 and candidates[1].total_score >= (candidates[0].total_score - 0.12):
            shortlist.append(candidates[1])
    elif candidates[0].confidence == "medium":
        shortlist.extend(candidates[: min(2, len(candidates))])
    else:
        shortlist.extend(candidates[: min(2, len(candidates))])

    return shortlist[:max_figures]


async def run_figure_planner(
    *,
    provider: ProviderAdapter,
    text_model_id: str,
    column_name: str,
    column_description: str,
    row_context: dict,
    proposed_value: Optional[str],
    rationale: Optional[str],
    retrieval: Optional[RetrievalResult],
    figures: list[dict],
    max_figures: int,
) -> FigurePlannerDecision:
    if not figures:
        return FigurePlannerDecision(attempted=False, skip_reason="no_figures")
    messages = build_figure_planner_prompt(
        column_name=column_name,
        column_description=column_description,
        row_context=row_context,
        proposed_value=proposed_value,
        rationale=rationale,
        retrieval=retrieval,
        figures=figures,
    )
    result = await provider.chat_complete_structured(
        messages=messages,
        response_schema=FIGURE_PLANNER_SCHEMA,
        model_id=text_model_id,
        max_tokens=1400,
    )
    valid_refs = {str(figure.get("figure_id")) for figure in figures if figure.get("figure_id")}
    targets: list[FigurePlannerTarget] = []
    for raw_target in result.get("target_figures") or []:
        ref = str(raw_target.get("figure_ref") or "")
        if ref not in valid_refs:
            continue
        preferred = str(raw_target.get("preferred_image") or "crop")
        if preferred not in {"crop", "full_page"}:
            preferred = "crop"
        targets.append(
            FigurePlannerTarget(
                figure_ref=ref,
                preferred_image=preferred,
                reason=raw_target.get("reason"),
            )
        )
        if len(targets) >= max_figures:
            break
    return FigurePlannerDecision(
        attempted=True,
        succeeded=True,
        needs_vision=bool(result.get("needs_vision")),
        target_figures=targets,
        rejected_figures=list(result.get("rejected_figures") or []),
        vision_question=result.get("vision_question"),
        planner_confidence=result.get("planner_confidence"),
        skip_reason=result.get("skip_reason") if not targets else None,
        fallback_to_heuristic_shortlist=bool(result.get("needs_vision")) and not targets,
    )


def _shortlist_from_planner(
    *,
    planner_decision: FigurePlannerDecision,
    figures: list[dict],
    retrieval: Optional[RetrievalResult],
    doc_dict: dict,
) -> list[FigureShortlistCandidate]:
    if not planner_decision.target_figures:
        return []
    figure_by_id = {str(figure.get("figure_id")): figure for figure in figures if figure.get("figure_id")}
    selected: list[FigureShortlistCandidate] = []
    for target in planner_decision.target_figures:
        figure = figure_by_id.get(target.figure_ref)
        if not figure:
            continue
        candidate = _score_figure_candidate(
            figure=figure,
            column_name="",
            column_description="",
            retrieval=retrieval,
            doc_dict=doc_dict,
        )
        candidate.rationale = [f"planner_selected={target.preferred_image}"]
        if target.reason:
            candidate.rationale.append(str(target.reason)[:240])
        selected.append(candidate)
    return selected


def _looks_like_explicit_figure_request(column_name: str, column_description: str) -> bool:
    text = f"{column_name} {column_description}"
    return bool(re.search(r"\b(?:fig(?:ure)?\.?|extended data fig(?:ure)?\.?)\s*\d+\b", text, flags=re.IGNORECASE))


def _resolve_artifact_path(run_dir: pathlib.Path, artifact_path: Optional[str]) -> Optional[pathlib.Path]:
    if not artifact_path:
        return None
    path = pathlib.Path(artifact_path)
    return path if path.is_absolute() else run_dir / path


def _display_artifact_path(run_dir: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(run_dir)).replace("\\", "/")
    except ValueError:
        return str(path)


def _encode_image_file_b64(path: pathlib.Path) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None


def _assess_crop_quality(path: pathlib.Path) -> tuple[bool, str]:
    try:
        from PIL import Image, ImageStat

        with Image.open(path) as image:
            width, height = image.size
            if width < 120 or height < 120:
                return False, "too_small"
            grayscale = image.convert("L")
            stat = ImageStat.Stat(grayscale)
            extrema = grayscale.getextrema()
            variance = float(stat.var[0] if stat.var else 0.0)
            if extrema[1] - extrema[0] < 10 or variance < 8.0:
                return False, "mostly_blank"
    except Exception:
        return False, "unreadable"
    return True, "ok"


def _select_figure_image(
    figure: dict,
    run_dir: pathlib.Path,
    *,
    column_name: str,
    column_description: str,
    preferred_image: Optional[str] = None,
) -> FigureImageSelection:
    """Select the image sent to vision for a figure review attempt."""
    crop_path = _resolve_artifact_path(run_dir, figure.get("crop_path"))
    full_page_path = _resolve_artifact_path(run_dir, figure.get("full_page_path"))
    full_page_exists = bool(full_page_path and full_page_path.exists())

    if preferred_image == "full_page" and full_page_exists and full_page_path:
        image_b64 = _encode_image_file_b64(full_page_path)
        if image_b64:
            return FigureImageSelection(
                image_b64=image_b64,
                image_source="full_page_preferred",
                image_path=_display_artifact_path(run_dir, full_page_path),
                failure_reason=None,
                crop_quality="not_checked",
                fallback_reason="planner_preferred_full_page",
            )

    if preferred_image is None and _looks_like_explicit_figure_request(column_name, column_description) and full_page_exists and full_page_path:
        image_b64 = _encode_image_file_b64(full_page_path)
        if image_b64:
            return FigureImageSelection(
                image_b64=image_b64,
                image_source="full_page_preferred",
                image_path=_display_artifact_path(run_dir, full_page_path),
                failure_reason=None,
                crop_quality="not_checked",
                fallback_reason="explicit_figure_request",
            )

    fallback_reason: Optional[str] = None
    crop_quality: Optional[str] = None
    if crop_path is None:
        fallback_reason = "missing_crop_path"
    elif not crop_path.exists():
        fallback_reason = "missing_figure_crop"
    else:
        crop_ok, crop_quality = _assess_crop_quality(crop_path)
        if crop_ok:
            image_b64 = _encode_image_file_b64(crop_path)
            if image_b64:
                return FigureImageSelection(
                    image_b64=image_b64,
                    image_source="crop",
                    image_path=_display_artifact_path(run_dir, crop_path),
                    failure_reason=None,
                    crop_quality=crop_quality,
                    fallback_reason=None,
                )
            fallback_reason = "crop_read_failed"
            crop_quality = "unreadable"
        else:
            fallback_reason = f"suspicious_crop_{crop_quality}"

    if full_page_exists and full_page_path:
        image_b64 = _encode_image_file_b64(full_page_path)
        if image_b64:
            return FigureImageSelection(
                image_b64=image_b64,
                image_source="full_page_fallback",
                image_path=_display_artifact_path(run_dir, full_page_path),
                failure_reason=None,
                crop_quality=crop_quality,
                fallback_reason=fallback_reason,
            )

    return FigureImageSelection(
        image_b64=None,
        image_source=None,
        image_path=None,
        failure_reason=fallback_reason or "missing_figure_image",
        crop_quality=crop_quality,
        fallback_reason=fallback_reason,
    )


def _normalize_value_for_compare(value: Optional[str]) -> str:
    if not value:
        return ""
    lowered = unicodedata.normalize("NFKD", value.lower())
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _values_match(left: Optional[str], right: Optional[str]) -> bool:
    left_norm = _normalize_value_for_compare(left)
    right_norm = _normalize_value_for_compare(right)
    return bool(left_norm and right_norm and left_norm == right_norm)


def _candidate_value_key(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _candidate_selection_needed(
    *,
    candidates: list[CandidateAnswer],
    support: str,
    needs_more_evidence: bool,
    recall_rescue_used: bool,
    state: str,
) -> bool:
    valued = [candidate for candidate in candidates if candidate.value]
    distinct_values = {_candidate_value_key(candidate.value) for candidate in valued if candidate.value}
    has_figure = any(candidate.source == "figure_review" for candidate in candidates)
    has_text = any(candidate.source in {"first_pass_text", "rescued_text", "evidence_recovery"} for candidate in candidates)
    text_figure_conflict = has_figure and has_text and len(distinct_values) > 1
    if len(distinct_values) <= 1:
        return False
    return (
        len(distinct_values) > 1
        or support == "weak_evidence"
        or needs_more_evidence
        or text_figure_conflict
        or (recall_rescue_used and len(valued) > 1)
        or state == "unclear"
        or (has_figure and len(valued) > 1)
    )


async def run_candidate_selection(
    *,
    provider: ProviderAdapter,
    text_model_id: str,
    column_name: str,
    column_description: str,
    row_context: dict,
    candidates: list[CandidateAnswer],
) -> dict:
    messages = build_candidate_selection_prompt(
        column_name=column_name,
        column_description=column_description,
        row_context=row_context,
        candidates=candidates,
    )
    return await provider.chat_complete_structured(
        messages=messages,
        response_schema=CANDIDATE_SELECTION_SCHEMA,
        model_id=text_model_id,
        max_tokens=1024,
    )


async def run_figure_review(
    proposal_id: str,
    run_id: str,
    pdf_id: str,
    column_name: str,
    column_description: str,
    doc_dict: dict,
    run_dir: pathlib.Path,
    provider: ProviderAdapter,
    text_model_id: Optional[str],
    vision_model_id: str,
    row_context: Optional[dict] = None,
    retrieval: Optional[RetrievalResult] = None,
    current_proposed_value: Optional[str] = None,
    current_rationale: Optional[str] = None,
    field_type: Optional[SchemaFieldType] = None,
    allowed_values: Optional[list[str]] = None,
    trigger_reasons: Optional[list[str]] = None,
    max_figures: int = 5,
    max_calls: Optional[int] = None,
    max_retries: int = 1,
    planner_enabled: bool = False,
    max_planner_calls: int = 1,
    planner_diagnostics: Optional[dict] = None,
    prompt_bundle_name: Optional[str] = None,
    prompt_bundle_path: Optional[str] = None,
    attempt_diagnostics: Optional[list[dict]] = None,
) -> list[FigureReviewHit]:
    """Proactive figure review (T062): run vision model over relevant figures.

    Targeted: only relevant figures by caption heuristic.
    Returns figure hits that can either support a text proposal or rescue an empty one.
    """
    figures = doc_dict.get("figures", [])
    if not figures:
        return []

    planner_decision = FigurePlannerDecision(attempted=False, skip_reason="disabled")
    if planner_enabled and max_planner_calls > 0 and text_model_id:
        try:
            planner_decision = await run_figure_planner(
                provider=provider,
                text_model_id=text_model_id,
                column_name=column_name,
                column_description=column_description,
                row_context=row_context or {},
                proposed_value=current_proposed_value,
                rationale=current_rationale,
                retrieval=retrieval,
                figures=figures,
                max_figures=max_figures,
            )
        except Exception as exc:
            planner_decision = FigurePlannerDecision(
                attempted=True,
                succeeded=False,
                needs_vision=True,
                fallback_to_heuristic_shortlist=True,
                failure_reason=type(exc).__name__,
            )
    if planner_diagnostics is not None:
        planner_diagnostics.update(planner_decision.model_dump(mode="json"))

    if (
        planner_decision.attempted
        and planner_decision.succeeded
        and not planner_decision.needs_vision
        and not planner_decision.fallback_to_heuristic_shortlist
    ):
        return []

    planner_preferred_by_ref = {
        target.figure_ref: target.preferred_image for target in planner_decision.target_figures
    }
    shortlist = _shortlist_from_planner(
        planner_decision=planner_decision,
        figures=figures,
        retrieval=retrieval,
        doc_dict=doc_dict,
    )
    if not shortlist:
        if planner_diagnostics is not None and planner_decision.attempted:
            planner_diagnostics["fallback_to_heuristic_shortlist"] = True
        shortlist = build_figure_shortlist(
            figures=figures,
            column_name=column_name,
            column_description=column_description,
            retrieval=retrieval,
            doc_dict=doc_dict,
            max_figures=max_figures,
        )
    if not shortlist:
        return []

    figure_hits: list[FigureReviewHit] = []

    calls_attempted = 0
    for candidate in shortlist:
        if max_calls is not None and calls_attempted >= max_calls:
            break
        figure = candidate.figure
        fig_id = figure.get("figure_id", "unknown")
        caption = figure.get("caption_text", "")
        nearby_text = candidate.nearby_context_excerpt or _find_nearby_text(fig_id, doc_dict)

        image_selection = _select_figure_image(
            figure,
            run_dir,
            column_name=column_name,
            column_description=column_description,
            preferred_image=planner_preferred_by_ref.get(str(fig_id)),
        )
        if image_selection.image_b64 is None:
            if attempt_diagnostics is not None:
                attempt_diagnostics.append(
                    {
                        "figure_id": fig_id,
                        "attempted": False,
                        "succeeded": False,
                        "failure_reason": image_selection.failure_reason or "missing_figure_image",
                        "image_source": image_selection.image_source,
                        "image_path": image_selection.image_path,
                        "crop_quality": image_selection.crop_quality,
                        "fallback_reason": image_selection.fallback_reason,
                    }
                )
            continue

        # Build vision prompt (T063)
        messages = build_figure_extraction_prompt(
            column_name,
            column_description,
            caption,
            nearby_text,
            retrieved_context_snippets=candidate.retrieved_context_snippets,
            figure_reference_snippets=candidate.matched_reference_snippets,
            section_context=candidate.section_context,
            field_type=field_type,
            allowed_values=allowed_values,
            prompt_bundle_name=prompt_bundle_name,
            prompt_bundle_path=prompt_bundle_path,
        )

        try:
            calls_attempted += 1
            result = await provider.vision_complete_structured(
                messages=messages,
                response_schema=VISION_EXTRACTION_SCHEMA,
                model_id=vision_model_id,
                image_b64=image_selection.image_b64,
                retry_malformed_structured_response=max_retries > 0,
            )
            fig_state = str(result.get("state") or "unclear")
            fig_value = result.get("proposed_value")
            fig_value_text = _coerce_text_value(fig_value, joiner="; ")
            fig_rationale = result.get("rationale")
            fig_description = result.get("figure_description", "")
            fig_numeric_form = _normalize_numeric_value_form(result.get("numeric_value_form"), field_type)
            promoted_unclear_value = bool(fig_state == "unclear" and fig_value_text)
            if attempt_diagnostics is not None:
                attempt_diagnostics.append(
                    {
                        "figure_id": fig_id,
                        "attempted": True,
                        "succeeded": True,
                        "failure_reason": None,
                        "image_source": image_selection.image_source,
                        "image_path": image_selection.image_path,
                        "crop_quality": image_selection.crop_quality,
                        "fallback_reason": image_selection.fallback_reason,
                        "result_state": fig_state,
                        "result_value_present": bool(fig_value_text),
                        "result_value_preview": fig_value_text[:120] if fig_value_text else None,
                        "promoted_unclear_value": promoted_unclear_value,
                    }
                )

            if not fig_value_text:
                if attempt_diagnostics is not None and attempt_diagnostics:
                    attempt_diagnostics[-1]["dropped_reason"] = "missing_proposed_value"
                continue  # This figure doesn't support the field
            if fig_state == "unclear" and not promoted_unclear_value:
                if attempt_diagnostics is not None and attempt_diagnostics:
                    attempt_diagnostics[-1]["dropped_reason"] = "unclear_without_value"
                continue  # This figure doesn't support the field
            hit_state = "inferred" if promoted_unclear_value else (fig_state if fig_state in {"found", "inferred"} else "inferred")

            figure_source_type = (
                EvidenceSourceType.caption_grounded_figure_evidence
                if result.get("caption_relevant")
                else EvidenceSourceType.visual_interpretation_figure_evidence
            )
            ev_id = generate_evidence_id(proposal_id)
            ev = EvidenceRecord(
                evidence_id=ev_id,
                run_id=run_id,
                proposal_id=proposal_id,
                pdf_id=pdf_id,
                source_type=figure_source_type,
                quote_text=fig_description or caption or None,
                page_number=figure.get("page_number"),
                caption_text=caption or None,
                figure_ref=fig_id,
                crop_path=figure.get("crop_path"),
                full_page_path=figure.get("full_page_path"),
                reasoning=fig_rationale,
                anchor_confidence=0.7,
                evidence_rank=99,
                is_primary=False,
                is_figure_derived=True,
                vision_context_bundle={
                    "caption_text": caption or None,
                    "nearby_text": nearby_text,
                    "retrieved_context_snippets": candidate.retrieved_context_snippets,
                    "figure_reference_snippets": candidate.matched_reference_snippets,
                    "section_context": candidate.section_context,
                },
                vision_trigger_reasons=list(trigger_reasons or []),
                shortlist_metadata={
                    "figure_id": fig_id,
                    "total_score": candidate.total_score,
                    "caption_score": candidate.caption_score,
                    "reference_score": candidate.reference_score,
                    "nearby_context_score": candidate.nearby_context_score,
                    "confidence": candidate.confidence,
                    "rationale": candidate.rationale,
                },
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            figure_hits.append(
                FigureReviewHit(
                    proposed_value=fig_value_text,
                    state=hit_state,
                    rationale=fig_rationale,
                    numeric_value_form=fig_numeric_form,
                    evidence=ev,
                    warning_flags=(["vision_state_unclear_with_value"] if promoted_unclear_value else []),
                )
            )
            if attempt_diagnostics is not None and attempt_diagnostics:
                attempt_diagnostics[-1]["accepted_as_hit"] = True
        except Exception as exc:
            if attempt_diagnostics is not None:
                attempt_diagnostics.append(
                    {
                        "figure_id": fig_id,
                        "attempted": True,
                        "succeeded": False,
                        "failure_reason": type(exc).__name__,
                        "failure_message": str(exc)[:240],
                        "image_source": image_selection.image_source,
                        "image_path": image_selection.image_path,
                        "crop_quality": image_selection.crop_quality,
                        "fallback_reason": image_selection.fallback_reason,
                    }
                )
            # Single figure failure does not abort the rest (T052)
            continue

    return figure_hits


def _find_nearby_text(figure_id: str, doc_dict: dict, window: int = 2) -> Optional[str]:
    """Find text blocks near a figure (by reading_order proximity)."""
    figures = {f.get("figure_id"): f for f in doc_dict.get("figures", [])}
    fig = figures.get(figure_id)
    if not fig:
        return None

    blocks = sorted(doc_dict.get("blocks", []), key=lambda b: b.get("reading_order", 0))
    # Find block closest in reading order to the figure's page
    fig_page = fig.get("page_number", 1)
    page_blocks = [b for b in blocks if b.get("page_number") == fig_page]
    if not page_blocks:
        return None
    # Return text of last few blocks on that page as nearby context
    nearby = page_blocks[-window:]
    return " ".join(b.get("text", "") for b in nearby)[:500]


def _has_numeric_conflict_in_quotes(quotes: list[dict]) -> bool:
    numeric_values: set[str] = set()
    for quote in quotes:
        text = str(quote.get("text", "") or "")
        for num in re.findall(r"\b\d+(?:\.\d+)?%?\b", text):
            numeric_values.add(num)
    return len(numeric_values) >= 2


def _retrieval_looks_figure_promising(retrieval: Optional[RetrievalResult]) -> bool:
    if retrieval is None:
        return False
    marker = re.compile(r"\b(fig(?:ure)?\.?\s*\d+|panel\s*[a-z]|chart|plot|graph|image|microscopy)\b", re.IGNORECASE)
    for chunk in retrieval.chunks[:8]:
        text = chunk.display_text or ""
        if chunk.chunk_type in {"caption", "figure"}:
            return True
        if marker.search(text):
            return True
    return False


def _retrieval_has_direct_figure_context(retrieval: Optional[RetrievalResult]) -> bool:
    if retrieval is None:
        return False
    return any(chunk.chunk_type in {"caption", "figure"} for chunk in retrieval.chunks[:8])


def _cell_request_looks_visual(column_name: str, column_description: str) -> bool:
    text = f"{column_name} {column_description}".lower()
    return bool(
        re.search(
            r"\b(figure|fig\.?|panel|plot|chart|graph|schematic|image|microscopy|visual|spatial map|heatmap|umap)\b",
            text,
        )
    )


def _has_usable_quote_payload(quotes: list[dict]) -> bool:
    return any(str(quote.get("text") or "").strip() for quote in quotes)


def should_run_recall_rescue(
    *,
    recall_rescue_enabled: bool,
    rescue_already_used: bool,
    state: str,
    support: Optional[str] = None,
    quotes: Optional[list[dict]] = None,
    retrieval: Optional[RetrievalResult] = None,
    needs_more_evidence: bool = False,
    figure_evidence_count: int = 0,
    text_figure_conflict: bool = False,
    candidate_selection_needs_more_evidence: bool = False,
) -> RecallRescueDecision:
    reasons: list[str] = []
    quote_items = quotes or []
    if state == "unclear":
        reasons.append("unclear_state")
    if needs_more_evidence or not _has_usable_quote_payload(quote_items):
        reasons.append("missing_usable_evidence")
    if support in {"weak_evidence", "inferred_from_evidence"}:
        reasons.append("weak_or_inferred_evidence")
    if _retrieval_looks_figure_promising(retrieval) and figure_evidence_count == 0:
        reasons.append("figure_relevant_without_figure_evidence")
    if text_figure_conflict:
        reasons.append("text_figure_conflict")
    if candidate_selection_needs_more_evidence:
        reasons.append("candidate_selection_requested_more_evidence")

    ordered: list[str] = []
    for reason in reasons:
        if reason not in ordered:
            ordered.append(reason)

    if not ordered:
        return RecallRescueDecision(eligible=False, skip_reason="not_needed")
    if rescue_already_used:
        return RecallRescueDecision(eligible=True, trigger_reasons=ordered, skip_reason="already_used")
    if not recall_rescue_enabled:
        return RecallRescueDecision(eligible=True, trigger_reasons=ordered, skip_reason="disabled")
    return RecallRescueDecision(eligible=True, trigger_reasons=ordered)


def decide_vision_trigger_reasons(
    state: str,
    support: str,
    quotes: list[dict],
    retrieval: Optional[RetrievalResult],
    needs_more_evidence: bool,
    proposed_value: Optional[str],
    column_name: str = "",
    column_description: str = "",
) -> list[str]:
    reasons: list[str] = []
    text_unclear = state == "unclear"
    text_weak = support == "weak_evidence" or needs_more_evidence
    text_contradictory = _has_numeric_conflict_in_quotes(quotes)
    direct_figure_context = _retrieval_has_direct_figure_context(retrieval)
    visual_request = _cell_request_looks_visual(column_name, column_description) and _retrieval_looks_figure_promising(retrieval)
    missing_value = proposed_value is None
    if text_unclear:
        reasons.append("text_unclear")
    if text_weak:
        reasons.append("text_weak")
    if text_contradictory:
        reasons.append("text_contradictory")
    if visual_request:
        reasons.append("visual_request")
    if direct_figure_context and (text_unclear or text_weak or text_contradictory or missing_value or visual_request):
        reasons.append("direct_figure_context")
    if missing_value and direct_figure_context:
        reasons.append("figure_rescue_candidate")
    # Stable order + dedupe
    ordered: list[str] = []
    for reason in reasons:
        if reason not in ordered:
            ordered.append(reason)
    return ordered


# ---------------------------------------------------------------------------
# Serialization / persistence (T056)
# ---------------------------------------------------------------------------

def persist_proposal(
    run_dir: pathlib.Path,
    proposal: ProposalRecord,
) -> pathlib.Path:
    """Persist a proposal record to proposals.jsonl plus a lookup index."""
    p_dir = _safe_run_subpath(run_dir, "proposals")
    p_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = _safe_run_subpath(run_dir, "proposals", "proposals.jsonl")
    index_path = _safe_run_subpath(run_dir, "proposals", "proposal_index.json")

    record = proposal.model_dump(mode="json")
    append_jsonl(jsonl_path, record)

    index = {}
    if index_path.exists():
        try:
            index = read_json(index_path)
        except Exception:
            index = {}
    if index:
        line_count = len(index) + 1
    else:
        with jsonl_path.open("r", encoding="utf-8") as handle:
            line_count = sum(1 for line in handle if line.strip())
    index[proposal.proposal_id] = {
        "proposal_id": proposal.proposal_id,
        "row_id": proposal.row_id,
        "column_name": proposal.column_name,
        "pdf_id": proposal.pdf_id,
        "proposal_status": proposal.proposal_status.value,
        "evidence_status": proposal.evidence_status.value,
        "review_bucket": proposal.review_bucket.value,
        "reason_codes": list(proposal.reason_codes),
        "warning_flags": proposal.warning_flags,
        "line_number": line_count,
    }
    write_json(index_path, index)
    return jsonl_path


def persist_evidence(
    run_dir: pathlib.Path,
    evidence: EvidenceRecord,
) -> pathlib.Path:
    """Persist an evidence record as JSON under evidence/."""
    e_dir = _safe_run_subpath(run_dir, "evidence")
    e_dir.mkdir(parents=True, exist_ok=True)
    path = _safe_run_subpath(run_dir, "evidence", f"{_safe_evidence_filename(evidence.evidence_id)}.json")
    record = evidence.model_dump(mode="json")
    write_json(path, record)
    append_jsonl(_safe_run_subpath(run_dir, "evidence", "evidence.jsonl"), record)
    return path


def load_proposals(run_dir: pathlib.Path) -> list[ProposalRecord]:
    """Load all proposal records from proposals.jsonl."""
    path = _safe_run_subpath(run_dir, "proposals", "proposals.jsonl")
    if not path.exists():
        return []
    deduped: dict[str, ProposalRecord] = {}
    for record in read_jsonl(path):
        try:
            proposal = ProposalRecord.model_validate(record)
            if proposal.proposal_id in deduped:
                del deduped[proposal.proposal_id]
            deduped[proposal.proposal_id] = proposal
        except Exception:
            pass
    return list(deduped.values())


def load_evidence(run_dir: pathlib.Path) -> list[EvidenceRecord]:
    """Load all evidence records from the run directory."""
    e_dir = _safe_run_subpath(run_dir, "evidence")
    if not e_dir.exists():
        return []
    results = []
    from .artifacts import read_json
    for p in sorted(e_dir.glob("*.json")):
        try:
            data = read_json(p)
            results.append(EvidenceRecord.model_validate(data))
        except Exception:
            pass
    return results


# ---------------------------------------------------------------------------
# Per-cell extraction orchestrator (T057)
# ---------------------------------------------------------------------------

async def extract_cell(
    run_id: str,
    pdf_id: str,
    row_id: str,
    cell_id: str,
    column_name: str,
    column_description: str,
    row_context: dict,
    doc_dict: dict,
    run_dir: pathlib.Path,
    provider: ProviderAdapter,
    text_model_id: str,
    retrieval: Optional[RetrievalResult] = None,
    style_profile: Optional[StyleProfile] = None,
    field_type: Optional[SchemaFieldType] = None,
    allowed_values: Optional[list[str]] = None,
    caps=None,  # ProviderCapabilities
    vision_model_id: Optional[str] = None,
    is_verify_mode: bool = False,
    existing_value: Optional[str] = None,
    recall_rescue_enabled: bool = True,
    typed_scoring_context: str = "none",
    whole_document_mode: bool = False,
    whole_document_max_chars: int = 12000,
    provider_mode_str: str = "unknown",
    artifact_context: Optional[dict] = None,
    max_figures_for_review: int = 5,
    max_figure_review_calls_per_cell: Optional[int] = None,
    max_figure_review_retries_per_cell: int = 1,
    figure_planner_enabled: bool = True,
    max_figure_planner_calls_per_cell: int = 1,
    skip_figure_review_when_prompt_only_degraded: bool = False,
    candidate_selection_enabled: bool = True,
    max_candidate_selection_calls_per_cell: int = 1,
    stats_sink: Optional[dict[str, object]] = None,
    retrieval_cache: Optional[dict[tuple[str, bool, bool], Any]] = None,
) -> ProposalRecord:
    """Extract one cell value and produce a proposal with evidence.

    T057: orchestrates row context, column def, style profile, retrieval, and provider.
    T058: handles all proposal states.
    T066: verify mode uses the same extraction path.
    """
    proposal_id = generate_proposal_id(run_id, cell_id)
    now = datetime.now(timezone.utc).isoformat()
    if field_type is not None and not isinstance(field_type, SchemaFieldType):
        try:
            field_type = SchemaFieldType(str(field_type))
        except ValueError:
            field_type = None
    artifact_context = artifact_context or {}
    cell_started = perf_counter()
    text_model_ms = 0.0
    evidence_anchoring_ms = 0.0
    figure_review_ms = 0.0
    evidence_recovery_ms = 0.0
    recall_rescue_retrieval_ms = 0.0
    recall_rescue_retrieval_prep_ms = 0.0
    text_model_calls = 0
    evidence_anchor_attempts = 0
    figure_review_calls = 0
    recall_rescue_used = False
    whole_document_used = False
    recall_rescue_decision = RecallRescueDecision(eligible=False, skip_reason="not_evaluated")
    whole_document_decision: dict[str, object] = {
        "eligible": False,
        "used": False,
        "skip_reason": "not_evaluated",
    }
    needs_more = False
    figure_hits: list[FigureReviewHit] = []
    figure_attempts: list[dict] = []
    candidate_selection_calls = 0
    candidate_selection_value_changed = False
    candidate_answers_payload: Optional[list[dict]] = None
    selection_diagnostics: Optional[dict] = None
    figure_planner_diagnostics: Optional[dict] = None
    provider_diag_cursor = _get_provider_diagnostics_cursor(provider)
    provider_diag_summary: Optional[dict] = None
    retrieval_diag_summary: Optional[dict] = None
    figure_review_diag_summary: Optional[dict] = None

    def finalize_stats(proposal: Optional[ProposalRecord] = None) -> None:
        if stats_sink is None:
            return
        stats_sink.update(
            {
                "response_schema_profile": response_schema_profile,
                "cell_total_ms": round((perf_counter() - cell_started) * 1000.0, 3),
                "text_model_ms": round(text_model_ms, 3),
                "text_model_calls": text_model_calls,
                "evidence_anchoring_ms": round(evidence_anchoring_ms, 3),
                "evidence_anchor_attempts": evidence_anchor_attempts,
                "figure_review_ms": round(figure_review_ms, 3),
                "figure_review_calls": figure_review_calls,
                "evidence_recovery_ms": round(evidence_recovery_ms, 3),
                "recall_rescue_retrieval_ms": round(recall_rescue_retrieval_ms, 3),
                "recall_rescue_retrieval_prep_ms": round(recall_rescue_retrieval_prep_ms, 3),
                "recall_rescue_used": recall_rescue_used,
                "whole_document_used": whole_document_used,
                "recall_rescue_eligible": recall_rescue_decision.eligible,
                "recall_rescue_trigger_reasons": list(recall_rescue_decision.trigger_reasons),
                "recall_rescue_skip_reason": recall_rescue_decision.skip_reason,
                "whole_document_eligible": bool(whole_document_decision.get("eligible")),
                "whole_document_skip_reason": whole_document_decision.get("skip_reason"),
                "needs_more_evidence": needs_more,
                "figure_hits_count": len(figure_hits),
                "figure_review_attempted": any(bool(item.get("attempted")) for item in figure_attempts),
                "figure_review_succeeded": any(bool(item.get("succeeded")) for item in figure_attempts),
                "figure_review_failed": any(bool(item.get("attempted")) and not bool(item.get("succeeded")) for item in figure_attempts),
                "candidate_selection_calls": candidate_selection_calls,
                "candidate_selection_value_changed": candidate_selection_value_changed,
                "selection_diagnostics": selection_diagnostics,
                "provider_diagnostics": provider_diag_summary,
                "retrieval_diagnostics": retrieval_diag_summary,
                "figure_review_diagnostics": figure_review_diag_summary,
                "figure_planner_diagnostics": figure_planner_diagnostics,
            }
        )
        if proposal is not None:
            stats_sink["proposal_status"] = proposal.proposal_status.value
            stats_sink["evidence_status"] = proposal.evidence_status.value
            stats_sink["review_bucket"] = proposal.review_bucket.value
            stats_sink["reason_codes"] = list(proposal.reason_codes)
            stats_sink["warning_flags"] = list(proposal.warning_flags)
            stats_sink["figure_review_triggered"] = bool((proposal.figure_review_diagnostics or {}).get("triggered"))
            stats_sink["figure_review_useful"] = bool((proposal.figure_review_diagnostics or {}).get("useful"))
            stats_sink["figure_review_rescued"] = bool((proposal.figure_review_diagnostics or {}).get("rescued_value"))

    run_mode = str(artifact_context.get("run_mode") or ("verify" if is_verify_mode else "normal"))
    prompt_bundle_name = artifact_context.get("prompt_bundle_name")
    prompt_bundle_path = artifact_context.get("prompt_bundle_path")
    prompt_version = artifact_context.get("prompt_version")
    prompt_hash = artifact_context.get("prompt_hash")
    schema_hash = artifact_context.get("schema_hash")
    schema_version = artifact_context.get("schema_version")
    config_hash = artifact_context.get("config_hash")
    config_snapshot_path = artifact_context.get("config_snapshot_path")
    parser_identity = artifact_context.get("parser_identity")
    parser_version = artifact_context.get("parser_version")
    style_profile_mode = artifact_context.get("style_profile_mode")
    gold_table_source_reference = artifact_context.get("gold_table_source_reference")
    gold_table_hash = artifact_context.get("gold_table_hash")
    gold_table_snapshot_path = artifact_context.get("gold_table_snapshot_path")
    masked_working_table_path = artifact_context.get("masked_working_table_path")
    masked_working_table_hash = artifact_context.get("masked_working_table_hash")

    long_text = is_long_text_field(column_name, column_description)
    response_schema, response_schema_profile = _select_text_extraction_schema(caps)
    metadata_resolution = resolve_metadata_field(column_name, column_description, doc_dict)

    if metadata_resolution is not None and metadata_resolution.state == "found":
        metadata_evidence_ids: list[str] = []
        evidence_rank = 1
        if metadata_resolution.quote_text:
            evidence_id = generate_evidence_id(proposal_id)
            evidence = EvidenceRecord(
                evidence_id=evidence_id,
                run_id=run_id,
                proposal_id=proposal_id,
                pdf_id=pdf_id,
                source_type=(
                    EvidenceSourceType.direct_quote
                    if metadata_resolution.source_type == "direct_quote"
                    else EvidenceSourceType.quote_plus_page
                ),
                quote_text=metadata_resolution.quote_text,
                page_number=metadata_resolution.page_number,
                anchor_confidence=1.0 if metadata_resolution.source_type == "direct_quote" else 0.6,
                evidence_rank=evidence_rank,
                is_primary=True,
                run_mode=run_mode,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                schema_hash=schema_hash,
                schema_version=schema_version,
                config_hash=config_hash,
                config_snapshot_path=config_snapshot_path,
                parser_identity=parser_identity,
                parser_version=parser_version,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            persist_evidence(run_dir, evidence)
            metadata_evidence_ids.append(evidence_id)

        proposal = ProposalRecord(
            proposal_id=proposal_id,
            run_id=run_id,
            pdf_id=pdf_id,
            row_id=row_id,
            column_name=column_name,
            cell_id=cell_id,
            **_semantics_fields(ProposalStatus.value_proposed, EvidenceStatus.direct_strong, []),
            proposed_value=metadata_resolution.proposed_value,
            rationale=_normalize_rationale(
                f"Resolved from parser-first {metadata_resolution.field_kind} metadata before retrieval/model extraction."
            ),
            primary_evidence_id=metadata_evidence_ids[0] if metadata_evidence_ids else None,
            ordered_supporting_evidence_ids=[],
            evidence_ids=metadata_evidence_ids,
            warning_flags=[],
            needs_more_evidence=False,
            is_verify_mode=is_verify_mode,
            existing_value=existing_value,
            field_type=field_type,
            allowed_values=allowed_values,
            provider_mode=provider_mode_str,
            run_mode=run_mode,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            schema_hash=schema_hash,
            schema_version=schema_version,
            config_hash=config_hash,
            config_snapshot_path=config_snapshot_path,
            parser_identity=parser_identity,
            parser_version=parser_version,
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            gold_table_source_reference=gold_table_source_reference,
            gold_table_hash=gold_table_hash,
            gold_table_snapshot_path=gold_table_snapshot_path,
            masked_working_table_path=masked_working_table_path,
            masked_working_table_hash=masked_working_table_hash,
            provider_diagnostics=None,
            retrieval_diagnostics={
                "metadata_front_matter": True,
                "metadata_source": metadata_resolution.source,
            },
            extraction_lane=metadata_resolution.extraction_lane,
            failure_attribution=None,
            fallback_reasons=[],
            metadata_diagnostics=metadata_resolution.diagnostics,
            style_profile_mode=style_profile_mode,
            created_at=now,
        )
        persist_proposal(run_dir, proposal)
        finalize_stats(proposal)
        return proposal

    if metadata_resolution is not None and metadata_resolution.failure_attribution == "evidence_ambiguity":
        proposal = ProposalRecord(
            proposal_id=proposal_id,
            run_id=run_id,
            pdf_id=pdf_id,
            row_id=row_id,
            column_name=column_name,
            cell_id=cell_id,
            **_semantics_fields(ProposalStatus.unresolved, EvidenceStatus.no_evidence, [CONFLICTING_EVIDENCE]),
            proposed_value=None,
            rationale=_normalize_rationale(
                "Parser-first metadata/front-matter inspection found conflicting candidates, so the cell stayed unclear."
            ),
            evidence_ids=[],
            warning_flags=["metadata_ambiguity"],
            needs_more_evidence=False,
            is_verify_mode=is_verify_mode,
            existing_value=existing_value,
            field_type=field_type,
            allowed_values=allowed_values,
            provider_mode=provider_mode_str,
            run_mode=run_mode,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            schema_hash=schema_hash,
            schema_version=schema_version,
            config_hash=config_hash,
            config_snapshot_path=config_snapshot_path,
            parser_identity=parser_identity,
            parser_version=parser_version,
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            gold_table_source_reference=gold_table_source_reference,
            gold_table_hash=gold_table_hash,
            gold_table_snapshot_path=gold_table_snapshot_path,
            masked_working_table_path=masked_working_table_path,
            masked_working_table_hash=masked_working_table_hash,
            extraction_lane=metadata_resolution.extraction_lane,
            failure_attribution=metadata_resolution.failure_attribution,
            fallback_reasons=list(metadata_resolution.fallback_reasons),
            metadata_diagnostics=metadata_resolution.diagnostics,
            style_profile_mode=style_profile_mode,
            created_at=now,
        )
        persist_proposal(run_dir, proposal)
        finalize_stats(proposal)
        return proposal

    # Build extraction prompt (T053, T057a)
    messages = build_text_extraction_prompt(
        column_name=column_name,
        column_description=column_description,
        row_context=row_context,
        retrieval=retrieval,
        style_profile=style_profile,
        field_type=field_type,
        allowed_values=allowed_values,
        is_verify_mode=is_verify_mode,
        existing_value=existing_value,
        is_long_text=long_text,
        prompt_bundle_name=prompt_bundle_name,
        prompt_bundle_path=prompt_bundle_path,
    )

    # T057a: long text fields get more tokens
    max_tokens = 4096 if long_text else 2048

    try:
        request_started = perf_counter()
        raw_result = await provider.chat_complete_structured(
            messages=messages,
            response_schema=response_schema,
            model_id=text_model_id,
            max_tokens=max_tokens,
        )
        text_model_ms += (perf_counter() - request_started) * 1000.0
        text_model_calls += 1
    except Exception as e:
        # Hard provider error — record error proposal
        provider_diag_summary = _summarize_provider_attempts(
            _get_provider_diagnostics_since(provider, provider_diag_cursor)
        )
        proposal = ProposalRecord(
            proposal_id=proposal_id,
            run_id=run_id,
            pdf_id=pdf_id,
            row_id=row_id,
            column_name=column_name,
            cell_id=cell_id,
            **_semantics_fields(ProposalStatus.error, EvidenceStatus.not_applicable, [PROVIDER_ERROR]),
            proposed_value=None,
            rationale=f"Provider error: {e}",
            evidence_ids=[],
            warning_flags=["provider_error"],
            provider_mode=provider_mode_str,
            is_verify_mode=is_verify_mode,
            existing_value=existing_value,
            run_mode=run_mode,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            schema_hash=schema_hash,
            schema_version=schema_version,
            config_hash=config_hash,
            config_snapshot_path=config_snapshot_path,
            parser_identity=parser_identity,
            parser_version=parser_version,
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            gold_table_source_reference=gold_table_source_reference,
            gold_table_hash=gold_table_hash,
            gold_table_snapshot_path=gold_table_snapshot_path,
            masked_working_table_path=masked_working_table_path,
            masked_working_table_hash=masked_working_table_hash,
            provider_diagnostics=provider_diag_summary,
            extraction_lane=(metadata_resolution.extraction_lane if metadata_resolution is not None else "content"),
            failure_attribution="extraction_miss",
            fallback_reasons=(list(metadata_resolution.fallback_reasons) if metadata_resolution is not None else []),
            metadata_diagnostics=(metadata_resolution.diagnostics if metadata_resolution is not None else None),
            style_profile_mode=style_profile_mode,
            created_at=now,
        )
        persist_proposal(run_dir, proposal)
        finalize_stats(proposal)
        return proposal

    first_pass_result = _normalize_text_extraction_result(raw_result, response_schema_profile)
    first_pass_value = _coerce_text_value(first_pass_result.get("proposed_value"), joiner="; ")
    first_pass_quotes = _normalize_quotes_payload(first_pass_result.get("quotes"))
    first_pass_state, _ = adjudicate_state(
        str(first_pass_result.get("state", "unclear") or "unclear"),
        first_pass_value,
        first_pass_quotes,
        is_verify_mode,
    )
    first_pass_has_direct_quote = any(
        str(quote.get("source_type") or "direct_quote") == "direct_quote"
        and str(quote.get("text") or "").strip()
        for quote in first_pass_quotes
    )
    first_pass_has_inferred_quote = any(
        str(quote.get("source_type") or "") in {"inferred_reasoning", "calculation"}
        and str(quote.get("text") or "").strip()
        for quote in first_pass_quotes
    )
    first_pass_support = (
        "direct_evidence"
        if first_pass_state != "unclear" and first_pass_has_direct_quote
        else "inferred_from_evidence"
        if first_pass_state != "unclear" and first_pass_has_inferred_quote
        else determine_support_label(
            first_pass_state,
            [],
            proposed_value=first_pass_value,
            field_type=field_type,
        )
    )
    first_pass_needs_more = bool(first_pass_value and not _has_usable_quote_payload(first_pass_quotes))
    recall_rescue_decision = should_run_recall_rescue(
        recall_rescue_enabled=recall_rescue_enabled,
        rescue_already_used=recall_rescue_used,
        state=first_pass_state,
        support=first_pass_support,
        quotes=first_pass_quotes,
        retrieval=retrieval,
        needs_more_evidence=first_pass_needs_more,
    )
    if recall_rescue_decision.eligible and recall_rescue_decision.skip_reason is None:
        recall_rescue_used = True
        rescue_retrieval = retrieval
        if retrieval is not None and doc_dict:
            from .retrieval import run_retrieval_for_cell

            rescue_retrieval = run_retrieval_for_cell(
                run_id=run_id,
                pdf_id=pdf_id,
                column_name=column_name,
                column_description=column_description,
                doc_dict=doc_dict,
                run_dir=run_dir,
                top_k=max((retrieval.top_k if retrieval else 6) + 3, 9),
                mode="recall_rescue",
                rescue_reason=",".join(recall_rescue_decision.trigger_reasons) or "evidence_quality",
                retrieval_cache=retrieval_cache,
                cache_key=pdf_id,
                typed_scoring_context=typed_scoring_context,
            )
            rescue_stats = rescue_retrieval.stats if isinstance(rescue_retrieval.stats, dict) else {}
            recall_rescue_retrieval_ms += float(rescue_stats.get("total_ms", 0.0) or 0.0)
            recall_rescue_retrieval_prep_ms += float(rescue_stats.get("chunk_build_ms", 0.0) or 0.0)
            recall_rescue_retrieval_prep_ms += float(rescue_stats.get("idf_build_ms", 0.0) or 0.0)
        whole_document_text = None
        whole_document_decision = {
            "eligible": bool(whole_document_mode),
            "used": False,
            "skip_reason": None,
        }
        if whole_document_mode:
            whole_document_text = build_whole_document_context(doc_dict, whole_document_max_chars)
            whole_document_used = whole_document_text is not None
            whole_document_decision["used"] = whole_document_used
            if not whole_document_used:
                whole_document_decision["skip_reason"] = "document_missing_or_exceeds_limit"
        else:
            whole_document_decision["skip_reason"] = "disabled"
        rescue_messages = build_text_extraction_prompt(
            column_name=column_name,
            column_description=column_description,
            row_context=row_context,
            retrieval=rescue_retrieval,
            style_profile=style_profile,
            field_type=field_type,
            allowed_values=allowed_values,
            whole_document_text=whole_document_text,
            is_verify_mode=is_verify_mode,
            existing_value=existing_value,
            is_long_text=long_text,
            prompt_bundle_name=prompt_bundle_name,
            prompt_bundle_path=prompt_bundle_path,
        )
        try:
            rescue_request_started = perf_counter()
            raw_result = await provider.chat_complete_structured(
                messages=rescue_messages,
                response_schema=response_schema,
                model_id=text_model_id,
                max_tokens=max_tokens,
            )
            text_model_ms += (perf_counter() - rescue_request_started) * 1000.0
            text_model_calls += 1
        except Exception as e:
            provider_diag_summary = _summarize_provider_attempts(
                _get_provider_diagnostics_since(provider, provider_diag_cursor)
            )
            proposal = ProposalRecord(
                proposal_id=proposal_id,
                run_id=run_id,
                pdf_id=pdf_id,
                row_id=row_id,
                column_name=column_name,
                cell_id=cell_id,
                **_semantics_fields(ProposalStatus.error, EvidenceStatus.not_applicable, [INVALID_MODEL_OUTPUT]),
                proposed_value=None,
                rationale=f"Provider error: {e}",
                evidence_ids=[],
                warning_flags=["provider_error"],
                provider_mode=provider_mode_str,
                is_verify_mode=is_verify_mode,
                existing_value=existing_value,
                field_type=field_type,
                allowed_values=allowed_values,
                recall_rescue_used=recall_rescue_used,
                whole_document_used=whole_document_used,
                run_mode=run_mode,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                schema_hash=schema_hash,
                schema_version=schema_version,
                config_hash=config_hash,
                config_snapshot_path=config_snapshot_path,
                parser_identity=parser_identity,
                parser_version=parser_version,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
                gold_table_source_reference=gold_table_source_reference,
                gold_table_hash=gold_table_hash,
                gold_table_snapshot_path=gold_table_snapshot_path,
                masked_working_table_path=masked_working_table_path,
                masked_working_table_hash=masked_working_table_hash,
                provider_diagnostics=provider_diag_summary,
                extraction_lane=(metadata_resolution.extraction_lane if metadata_resolution is not None else "content"),
                failure_attribution="extraction_miss",
                fallback_reasons=(list(metadata_resolution.fallback_reasons) if metadata_resolution is not None else []),
                metadata_diagnostics=(metadata_resolution.diagnostics if metadata_resolution is not None else None),
                style_profile_mode=style_profile_mode,
                created_at=now,
            )
            persist_proposal(run_dir, proposal)
            finalize_stats(proposal)
            return proposal
    elif recall_rescue_decision.eligible and recall_rescue_decision.skip_reason == "disabled":
        whole_document_decision = {"eligible": bool(whole_document_mode), "used": False, "skip_reason": "recall_rescue_skipped"}

    # Parse and adjudicate result (T058)
    normalized_result = _normalize_text_extraction_result(raw_result, response_schema_profile)
    raw_state = str(normalized_result.get("state", "unclear") or "unclear")
    proposed_value = _coerce_text_value(normalized_result.get("proposed_value"), joiner="; ")
    rationale = _coerce_text_value(normalized_result.get("rationale"), joiner="\n")
    calculation = _coerce_text_value(normalized_result.get("calculation"), joiner="\n")
    numeric_value_form = _normalize_numeric_value_form(
        normalized_result.get("numeric_value_form"),
        field_type,
    )
    quotes = _normalize_quotes_payload(normalized_result.get("quotes"))

    # T053a: ensure rationale is compact bullets
    rationale = _normalize_rationale(rationale)

    state, _ = adjudicate_state(raw_state, proposed_value, quotes, is_verify_mode)

    # Build evidence records from quotes (T059)
    evidence_records: list[EvidenceRecord] = []

    for q in quotes:
        quote_text = _coerce_text_value(q.get("text"), joiner=" ") or ""
        page_num = q.get("page")
        raw_source_type = q.get("source_type", "direct_quote")

        if not quote_text:
            continue

        # For inferred_reasoning and calculation, skip anchoring (T059)
        if raw_source_type in ("inferred_reasoning", "calculation"):
            ev_source = (
                EvidenceSourceType.inferred_reasoning
                if raw_source_type == "inferred_reasoning"
                else EvidenceSourceType.calculation
            )
            ev_id = generate_evidence_id(proposal_id)
            ev = EvidenceRecord(
                evidence_id=ev_id,
                run_id=run_id,
                proposal_id=proposal_id,
                pdf_id=pdf_id,
                source_type=ev_source,
                quote_text=quote_text,
                page_number=page_num,
                reasoning=rationale,
                anchor_confidence=0.0,
                evidence_rank=99,
                is_primary=False,
                run_mode=run_mode,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                schema_hash=schema_hash,
                schema_version=schema_version,
                config_hash=config_hash,
                config_snapshot_path=config_snapshot_path,
                parser_identity=parser_identity,
                parser_version=parser_version,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            # Attempt anchoring (T059)
            anchor_started = perf_counter()
            anchored_type, exact_regions, approx_regions, confidence = anchor_evidence(
                quote_text, page_num, doc_dict
            )
            evidence_anchoring_ms += (perf_counter() - anchor_started) * 1000.0
            evidence_anchor_attempts += 1
            resolved_page = (
                (exact_regions[0].get("page") if exact_regions else None)
                or (approx_regions[0].get("page") if approx_regions else None)
                or page_num
            )
            ev_id = generate_evidence_id(proposal_id)
            ev = EvidenceRecord(
                evidence_id=ev_id,
                run_id=run_id,
                proposal_id=proposal_id,
                pdf_id=pdf_id,
                source_type=anchored_type,
                quote_text=quote_text,
                page_number=resolved_page,
                exact_highlight_regions=exact_regions or None,
                approximate_highlight_regions=approx_regions or None,
                anchor_confidence=confidence,
                evidence_rank=99,
                is_primary=False,
                run_mode=run_mode,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                schema_hash=schema_hash,
                schema_version=schema_version,
                config_hash=config_hash,
                config_snapshot_path=config_snapshot_path,
                parser_identity=parser_identity,
                parser_version=parser_version,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        evidence_records.append(ev)

    # Evidence recovery pass (T060): if no usable evidence, try once
    has_usable_evidence = any(
        ev.source_type not in (EvidenceSourceType.quote_plus_page,)
        or ev.quote_text
        for ev in evidence_records
    )
    needs_more = not has_usable_evidence and state != "unclear"

    if needs_more and proposed_value:
        recovery_started = perf_counter()
        recovery_ev = await attempt_evidence_recovery(
            proposal_id=proposal_id,
            run_id=run_id,
            pdf_id=pdf_id,
            column_name=column_name,
            column_description=column_description,
            retrieval=retrieval,
            doc_dict=doc_dict,
            provider=provider,
            text_model_id=text_model_id,
            caps=caps,
            prompt_bundle_name=prompt_bundle_name,
            prompt_bundle_path=prompt_bundle_path,
        )
        recovery_elapsed_ms = (perf_counter() - recovery_started) * 1000.0
        evidence_recovery_ms += recovery_elapsed_ms
        text_model_ms += recovery_elapsed_ms
        text_model_calls += 1
        if recovery_ev:
            evidence_records.append(recovery_ev)
            needs_more = False

    # Proactive figure review (T062): when vision model configured
    preliminary_support = determine_support_label(
        state,
        evidence_records,
        proposed_value=proposed_value,
        field_type=field_type,
    )
    vision_trigger_reasons = decide_vision_trigger_reasons(
        state=state,
        support=preliminary_support,
        quotes=quotes,
        retrieval=retrieval,
        needs_more_evidence=needs_more,
        proposed_value=proposed_value,
        column_name=column_name,
        column_description=column_description,
    )
    figure_review_suppressed_reason: Optional[str] = None
    figure_review_triggered = bool(doc_dict.get("figures") and vision_trigger_reasons)
    should_run_vision = bool(vision_model_id and figure_review_triggered)
    if figure_review_triggered and not vision_model_id:
        figure_review_suppressed_reason = "vision_not_configured"
    if (
        should_run_vision
        and skip_figure_review_when_prompt_only_degraded
        and getattr(caps, "vision_structured_output_mode", None) == "none"
    ):
        should_run_vision = False
        figure_review_suppressed_reason = "prompt_only_provider_mode"

    shortlist_metadata: list[dict] = []
    if should_run_vision:
        shortlist_preview = build_figure_shortlist(
            figures=doc_dict.get("figures", []),
            column_name=column_name,
            column_description=column_description,
            retrieval=retrieval,
            doc_dict=doc_dict,
            max_figures=max_figures_for_review,
        )
        shortlist_metadata = [
            {
                "figure_id": str(item.figure.get("figure_id", "unknown")),
                "score": item.total_score,
                "confidence": item.confidence,
                "rationale": item.rationale,
            }
            for item in shortlist_preview
        ]

    if should_run_vision:
        figure_planner_diagnostics = {}
        try:
            figure_review_started = perf_counter()
            figure_hits = await run_figure_review(
                proposal_id=proposal_id,
                run_id=run_id,
                pdf_id=pdf_id,
                column_name=column_name,
                column_description=column_description,
                doc_dict=doc_dict,
                run_dir=run_dir,
                provider=provider,
                text_model_id=text_model_id,
                vision_model_id=vision_model_id,
                row_context=row_context,
                retrieval=retrieval,
                current_proposed_value=proposed_value,
                current_rationale=rationale,
                field_type=field_type,
                allowed_values=allowed_values,
                trigger_reasons=vision_trigger_reasons,
                max_figures=max_figures_for_review,
                max_calls=max_figure_review_calls_per_cell,
                max_retries=max_figure_review_retries_per_cell,
                planner_enabled=figure_planner_enabled,
                max_planner_calls=max_figure_planner_calls_per_cell,
                planner_diagnostics=figure_planner_diagnostics,
                prompt_bundle_name=prompt_bundle_name,
                prompt_bundle_path=prompt_bundle_path,
                attempt_diagnostics=figure_attempts,
            )
            figure_review_ms += (perf_counter() - figure_review_started) * 1000.0
            figure_review_calls += sum(1 for item in figure_attempts if bool(item.get("attempted")))
        except Exception as exc:
            figure_attempts.append(
                {
                    "figure_id": None,
                    "attempted": False,
                    "succeeded": False,
                    "failure_reason": type(exc).__name__,
                    "failure_message": str(exc)[:240],
                }
            )
            pass  # Figure review failure does not abort the proposal

    figure_evidence = [hit.evidence for hit in figure_hits]
    for ev in figure_evidence:
        ev.run_mode = run_mode
        ev.prompt_version = prompt_version
        ev.prompt_hash = prompt_hash
        ev.schema_hash = schema_hash
        ev.schema_version = schema_version
        ev.config_hash = config_hash
        ev.config_snapshot_path = config_snapshot_path
        ev.parser_identity = parser_identity
        ev.parser_version = parser_version
        ev.text_model_id = text_model_id
        ev.vision_model_id = vision_model_id

    all_evidence = evidence_records + figure_evidence

    # Rank evidence (T065)
    ranked_evidence = rank_evidence(all_evidence)

    # Allow figure evidence to rescue an empty text proposal (T062)
    proposed_value_before_figure = proposed_value
    if figure_hits and not proposed_value:
        best_figure_hit = figure_hits[0]
        proposed_value = best_figure_hit.proposed_value
        if field_type == SchemaFieldType.number and best_figure_hit.numeric_value_form is not None:
            numeric_value_form = best_figure_hit.numeric_value_form
        if not rationale:
            rationale = _normalize_rationale(best_figure_hit.rationale)
        state = "inferred"
        needs_more = False

    support = determine_support_label(
        state,
        ranked_evidence,
        proposed_value=proposed_value,
        field_type=field_type,
    )

    candidate_answers: list[CandidateAnswer] = []
    seen_candidate_keys: set[tuple[str, str]] = set()
    candidate_numeric_forms: dict[str, Optional[NumericValueForm]] = {}

    def add_candidate(
        *,
        value: Optional[str],
        candidate_state: str,
        source: str,
        evidence_ids: list[str],
        rationale_text: Optional[str],
        warning_flags_for_candidate: Optional[list[str]] = None,
        numeric_form: Optional[NumericValueForm] = None,
    ) -> None:
        candidate_value = _coerce_text_value(value, joiner="; ")
        if not candidate_value:
            return
        key = (source, _candidate_value_key(candidate_value))
        if key in seen_candidate_keys:
            return
        seen_candidate_keys.add(key)
        candidate_id = f"cand_{len(candidate_answers) + 1}"
        candidate_answers.append(
            CandidateAnswer(
                candidate_id=candidate_id,
                value=candidate_value,
                candidate_status=candidate_state if candidate_state in {"found", "inferred", "unclear"} else "unclear",
                source=source,
                evidence_ids=list(evidence_ids),
                confidence_rationale=_normalize_rationale(rationale_text),
                warning_flags=list(warning_flags_for_candidate or []),
            )
        )
        candidate_numeric_forms[candidate_id] = numeric_form

    first_pass_candidate_state = str(first_pass_result.get("state", "unclear") or "unclear")
    add_candidate(
        value=first_pass_value,
        candidate_state=first_pass_candidate_state,
        source="first_pass_text",
        evidence_ids=[] if recall_rescue_used else [ev.evidence_id for ev in evidence_records],
        rationale_text=_coerce_text_value(first_pass_result.get("rationale"), joiner="\n"),
        warning_flags_for_candidate=["first_pass"],
        numeric_form=_normalize_numeric_value_form(first_pass_result.get("numeric_value_form"), field_type),
    )
    if recall_rescue_used:
        add_candidate(
            value=proposed_value,
            candidate_state=state,
            source="rescued_text",
            evidence_ids=[ev.evidence_id for ev in evidence_records],
            rationale_text=rationale,
            warning_flags_for_candidate=["recall_rescue_used"],
            numeric_form=numeric_value_form,
        )
    if any(ev.source_type == EvidenceSourceType.quote_plus_page for ev in evidence_records):
        add_candidate(
            value=proposed_value,
            candidate_state=state,
            source="evidence_recovery",
            evidence_ids=[ev.evidence_id for ev in evidence_records],
            rationale_text=rationale,
            warning_flags_for_candidate=["fallback_evidence_used"],
            numeric_form=numeric_value_form,
        )
    for hit in figure_hits:
        flags = ["figure_derived"]
        flags.extend(hit.warning_flags)
        if proposed_value and not _values_match(hit.proposed_value, proposed_value):
            flags.append("competing_evidence")
        add_candidate(
            value=hit.proposed_value,
            candidate_state=hit.state,
            source="figure_review",
            evidence_ids=[hit.evidence.evidence_id],
            rationale_text=hit.rationale,
            warning_flags_for_candidate=flags,
            numeric_form=hit.numeric_value_form,
        )

    if (
        candidate_selection_enabled
        and max_candidate_selection_calls_per_cell > 0
        and candidate_answers
        and _candidate_selection_needed(
            candidates=candidate_answers,
            support=support,
            needs_more_evidence=needs_more,
            recall_rescue_used=recall_rescue_used,
            state=state,
        )
    ):
        previous_value = proposed_value
        pre_selection_state = state
        pre_selection_rationale = rationale
        pre_selection_numeric_value_form = numeric_value_form
        pre_selection_ranked_evidence = list(ranked_evidence)
        try:
            selection_started = perf_counter()
            selection_result = await run_candidate_selection(
                provider=provider,
                text_model_id=text_model_id,
                column_name=column_name,
                column_description=column_description,
                row_context=row_context,
                candidates=candidate_answers,
            )
            selection_elapsed_ms = (perf_counter() - selection_started) * 1000.0
            text_model_ms += selection_elapsed_ms
            text_model_calls += 1
            candidate_selection_calls += 1
            selected_value = _coerce_text_value(selection_result.get("selected_value"), joiner="; ")
            selected_state_raw = str(selection_result.get("selected_state") or "unclear")
            selected_candidate_id = _coerce_text_value(selection_result.get("selected_candidate_id"), joiner=" ")
            if selected_value:
                proposed_value = selected_value
            elif selected_state_raw == "unclear":
                proposed_value = None
                numeric_value_form = None
            if selected_state_raw in {"found", "inferred", "unclear"}:
                state = str(selected_state_raw)
            selected_candidate = next(
                (candidate for candidate in candidate_answers if candidate.candidate_id == selected_candidate_id),
                None,
            )
            conservative_figure_override_blocked = bool(
                selected_candidate
                and selected_candidate.source == "figure_review"
                and previous_value
                and not _values_match(previous_value, selected_value)
                and support == "direct_evidence"
                and not _cell_request_looks_visual(column_name, column_description)
            )
            if selected_candidate and selected_candidate.evidence_ids:
                selected_ids = set(selected_candidate.evidence_ids)
                ranked_evidence = sorted(
                    ranked_evidence,
                    key=lambda ev: (0 if ev.evidence_id in selected_ids else 1, ev.evidence_rank),
                )
                selected_numeric_form = candidate_numeric_forms.get(selected_candidate.candidate_id)
                if selected_numeric_form is not None:
                    numeric_value_form = selected_numeric_form
            if selection_result.get("rationale"):
                rationale = _normalize_rationale(selection_result.get("rationale"))
            needs_more = bool(selection_result.get("needs_more_evidence"))
            candidate_selection_value_changed = _candidate_value_key(previous_value) != _candidate_value_key(proposed_value)
            if conservative_figure_override_blocked:
                proposed_value = previous_value
                state = pre_selection_state
                rationale = pre_selection_rationale
                numeric_value_form = pre_selection_numeric_value_form
                ranked_evidence = pre_selection_ranked_evidence
                needs_more = False
                candidate_selection_value_changed = False
            selection_diagnostics = {
                "attempted": True,
                "succeeded": True,
                "selected_candidate_id": selected_candidate_id,
                "rejected_candidate_ids": list(selection_result.get("rejected_candidate_ids") or []),
                "needs_more_evidence": needs_more,
                "value_changed": candidate_selection_value_changed,
                "figure_override_blocked": conservative_figure_override_blocked,
            }
        except Exception as exc:
            selection_diagnostics = {
                "attempted": True,
                "succeeded": False,
                "failure_reason": type(exc).__name__,
                "failure_message": str(exc)[:240],
            }
    elif candidate_answers:
        selection_diagnostics = {
            "attempted": False,
            "succeeded": False,
            "skip_reason": "not_needed_or_disabled",
            "candidate_count": len(candidate_answers),
        }

    candidate_answers_payload = [candidate.model_dump(mode="json") for candidate in candidate_answers] or None

    support = determine_support_label(
        state,
        ranked_evidence,
        proposed_value=proposed_value,
        field_type=field_type,
    )

    if support == "weak_evidence" and proposed_value:
        state = "unclear"
        support = "blocked"

    warning_flags = []
    if needs_more:
        warning_flags.append("needs_more_evidence")
    if recall_rescue_used:
        warning_flags.append("recall_rescue_used")
    if whole_document_used:
        warning_flags.append("whole_document_used")
    if numeric_value_form == NumericValueForm.approximate:
        warning_flags.append("approximate_value")
    if numeric_value_form == NumericValueForm.range:
        warning_flags.append("range_value")

    reason_codes: list[str] = []
    if needs_more or support == "weak_evidence":
        reason_codes.append(INSUFFICIENT_EVIDENCE)
    if calculation:
        reason_codes.append(CALCULATION)
    if any(ev.source_type == EvidenceSourceType.quote_plus_page for ev in ranked_evidence):
        reason_codes.append(ANCHOR_FALLBACK)
    if any(ev.source_type == EvidenceSourceType.approximate_highlight for ev in ranked_evidence):
        reason_codes.append(APPROXIMATE_ANCHOR)
    retrieval_chunks = retrieval.chunks if retrieval is not None else []
    if not ranked_evidence and not retrieval_chunks:
        reason_codes.append(RETRIEVAL_EMPTY)

    fallback_reasons = list(metadata_resolution.fallback_reasons) if metadata_resolution is not None else []
    failure_attribution = _classify_failure_attribution(
        state=state,
        proposed_value=proposed_value,
        retrieval=retrieval,
        doc_dict=doc_dict,
        evidence_records=ranked_evidence,
        provider_mode_str=provider_mode_str,
        metadata_resolution=metadata_resolution,
        warning_flags=warning_flags,
    )

    provider_diag_summary = _summarize_provider_attempts(
        _get_provider_diagnostics_since(provider, provider_diag_cursor)
    )
    retrieval_diag_summary = _build_retrieval_diagnostics(
        doc_dict=doc_dict,
        retrieval=retrieval,
        state=state,
        support=support,
        proposed_value=proposed_value,
        quotes=quotes,
        evidence_records=ranked_evidence,
        needs_more_evidence=needs_more,
        recall_rescue_used=recall_rescue_used,
        recall_rescue_decision=recall_rescue_decision,
        whole_document_used=whole_document_used,
        whole_document_decision=whole_document_decision,
        warning_flags=warning_flags,
    )
    figure_review_diag_summary = _build_figure_review_diagnostics(
        triggered=figure_review_triggered,
        trigger_reasons=vision_trigger_reasons,
        shortlist_metadata=shortlist_metadata,
        figure_review_calls=figure_review_calls,
        figure_review_ms=figure_review_ms,
        figure_hits=figure_hits,
        attempt_diagnostics=figure_attempts,
        ranked_evidence=ranked_evidence,
        figure_rescued_value=bool(figure_hits and not proposed_value_before_figure and proposed_value),
        suppressed_reason=figure_review_suppressed_reason,
    )

    # Persist evidence records
    for ev in ranked_evidence:
        persist_evidence(run_dir, ev)

    # Build final proposal
    primary_ev_id = ranked_evidence[0].evidence_id if ranked_evidence else None
    supporting_ids = [ev.evidence_id for ev in ranked_evidence[1:]]
    all_ev_ids = [ev.evidence_id for ev in ranked_evidence]

    semantic_kwargs = _canonical_semantics_kwargs(
        state=state,
        support=support,
        proposed_value=proposed_value,
        evidence_records=ranked_evidence,
        reason_codes=reason_codes,
    )
    persisted_proposed_value = _proposal_value_for_persistence(
        proposal_status=semantic_kwargs["proposal_status"],
        proposed_value=proposed_value,
    )

    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        cell_id=cell_id,
        **semantic_kwargs,
        proposed_value=persisted_proposed_value,
        rationale=rationale,
        calculation=calculation,
        primary_evidence_id=primary_ev_id,
        ordered_supporting_evidence_ids=supporting_ids,
        evidence_ids=all_ev_ids,
        warning_flags=warning_flags,
        needs_more_evidence=needs_more,
        is_verify_mode=is_verify_mode,
        existing_value=existing_value,
        field_type=field_type,
        allowed_values=allowed_values,
        numeric_value_form=numeric_value_form,
        recall_rescue_used=recall_rescue_used,
        whole_document_used=whole_document_used,
        provider_mode=provider_mode_str,
        run_mode=run_mode,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        schema_hash=schema_hash,
        schema_version=schema_version,
        config_hash=config_hash,
        config_snapshot_path=config_snapshot_path,
        parser_identity=parser_identity,
        parser_version=parser_version,
        text_model_id=text_model_id,
        vision_model_id=vision_model_id,
        gold_table_source_reference=gold_table_source_reference,
        gold_table_hash=gold_table_hash,
        gold_table_snapshot_path=gold_table_snapshot_path,
        masked_working_table_path=masked_working_table_path,
        masked_working_table_hash=masked_working_table_hash,
        vision_trigger_reasons=vision_trigger_reasons,
        vision_shortlist=shortlist_metadata or None,
        provider_diagnostics=provider_diag_summary,
        retrieval_diagnostics=retrieval_diag_summary,
        figure_review_diagnostics=figure_review_diag_summary,
        figure_planner_diagnostics=figure_planner_diagnostics,
        extraction_lane=(metadata_resolution.extraction_lane if metadata_resolution is not None else "content"),
        failure_attribution=failure_attribution,
        fallback_reasons=fallback_reasons,
        metadata_diagnostics=(metadata_resolution.diagnostics if metadata_resolution is not None else None),
        style_profile_mode=style_profile_mode,
        candidate_answers=candidate_answers_payload,
        selection_diagnostics=selection_diagnostics,
        created_at=now,
    )

    persist_proposal(run_dir, proposal)
    finalize_stats(proposal)
    return proposal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _proposal_value_for_persistence(
    *,
    proposal_status: ProposalStatus,
    proposed_value: Optional[str],
) -> Optional[str]:
    if proposal_status == ProposalStatus.unresolved and str(proposed_value or "").strip().lower() in {
        "",
        "unclear",
        "no value proposed",
        "not_found",
        "not found",
    }:
        return None
    return proposed_value


def _normalize_rationale(rationale: Optional[str]) -> Optional[str]:
    """Ensure rationale is compact markdown bullets (T053a)."""
    if isinstance(rationale, list):
        bullet_lines = []
        for item in rationale[:3]:
            text = _coerce_text_value(item, joiner=" ")
            if not text:
                continue
            bullet_lines.append(f"- {_ensure_terminal_punctuation(text)}")
        return "\n".join(bullet_lines) or None

    rationale_text = _coerce_text_value(rationale, joiner="\n")
    if not rationale_text:
        return None
    stripped = rationale_text.strip()
    # If it's already bullet-formatted, return as-is
    if stripped.startswith("- ") or stripped.startswith("* "):
        return stripped

    line_items = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(line_items) > 1:
        return "\n".join(f"- {_ensure_terminal_punctuation(line)}" for line in line_items[:3])

    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", stripped) if item.strip()]
    if not sentences:
        return None
    bullet_lines = [f"- {_ensure_terminal_punctuation(sentence)}" for sentence in sentences[:3]]
    if len(sentences) > 3:
        bullet_lines.append("- ...")
    return "\n".join(bullet_lines)


def _ensure_terminal_punctuation(text: str) -> str:
    value = text.strip()
    if not value:
        return value
    if value[-1] in ".!?":
        return value
    return f"{value}."


def _coerce_text_value(value: Any, joiner: str = "\n") -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        parts = [part for item in value if (part := _coerce_text_value(item, joiner=joiner))]
        text = joiner.join(parts)
    elif isinstance(value, dict):
        if "text" in value:
            return _coerce_text_value(value.get("text"), joiner=joiner)
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    stripped = text.strip()
    return stripped or None


def _classify_failure_attribution(
    *,
    state: str,
    proposed_value: Optional[str],
    retrieval: Optional[RetrievalResult],
    doc_dict: dict,
    evidence_records: list[EvidenceRecord],
    provider_mode_str: str,
    metadata_resolution: Optional[object],
    warning_flags: list[str],
) -> Optional[str]:
    if state not in {"unclear", "error", "blocked"}:
        return None
    if metadata_resolution is not None:
        failure_attribution = getattr(metadata_resolution, "failure_attribution", None)
        if isinstance(failure_attribution, str) and failure_attribution:
            return failure_attribution
    if provider_mode_str in {"unavailable", "disabled"}:
        return "contract_invalid"
    if evidence_records:
        return "evidence_ambiguity"
    retrieval_chunks = retrieval.chunks if retrieval is not None else []
    if retrieval is not None and not retrieval_chunks:
        return "retrieval_miss"
    if not str(doc_dict.get("full_text") or "").strip():
        return "parser_gap"
    if "needs_more_evidence" in warning_flags:
        return "evidence_ambiguity"
    if proposed_value:
        return "evidence_ambiguity"
    return "extraction_miss"


def _get_provider_diagnostics_cursor(provider: ProviderAdapter) -> Optional[int]:
    if not any("get_diagnostics_cursor" in cls.__dict__ for cls in type(provider).mro()):
        return None
    getter = getattr(provider, "get_diagnostics_cursor", None)
    if not callable(getter):
        return None
    try:
        value = getter()
    except Exception:
        return None
    if hasattr(value, "__await__"):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _get_provider_diagnostics_since(provider: ProviderAdapter, cursor: Optional[int]) -> list[dict]:
    if cursor is None:
        return []
    if not any("get_diagnostics_since" in cls.__dict__ for cls in type(provider).mro()):
        return []
    getter = getattr(provider, "get_diagnostics_since", None)
    if not callable(getter):
        return []
    try:
        results = getter(cursor)
    except Exception:
        return []
    if hasattr(results, "__await__"):
        return []
    return [dict(item) for item in results or [] if isinstance(item, dict)]


def _summarize_provider_attempts(attempts: list[dict]) -> Optional[dict]:
    if not attempts:
        return None
    request_kinds: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    retry_count = 0
    repair_count = 0
    total_duration_ms = 0.0
    last_error: Optional[dict] = None
    for attempt in attempts:
        request_kind = str(attempt.get("request_kind") or "unknown")
        outcome = str(attempt.get("outcome") or "unknown")
        request_kinds[request_kind] = request_kinds.get(request_kind, 0) + 1
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if attempt.get("phase") == "retry":
            retry_count += 1
        details = attempt.get("error_details")
        if isinstance(details, dict) and details.get("degraded_normalization_used"):
            repair_count += 1
        total_duration_ms += float(attempt.get("duration_ms", 0.0) or 0.0)
        if outcome != "success":
            last_error = {
                "request_kind": request_kind,
                "structured_mode": attempt.get("structured_mode"),
                "error_reason": attempt.get("error_reason"),
                "error_message": attempt.get("error_message"),
                "http_status": attempt.get("http_status"),
            }
    return {
        "attempt_count": len(attempts),
        "failure_count": sum(1 for attempt in attempts if str(attempt.get("outcome") or "") != "success"),
        "total_duration_ms": round(total_duration_ms, 3),
        "request_kinds": request_kinds,
        "outcomes": outcomes,
        "retry_count": retry_count,
        "repair_count": repair_count,
        "last_error": last_error,
    }


def _normalized_text_for_match(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _value_mentioned_in_retrieval(text: Optional[str], retrieval: Optional[RetrievalResult]) -> bool:
    normalized = _normalized_text_for_match(text)
    if len(normalized) < 4 or retrieval is None:
        return False
    return any(
        normalized in _normalized_text_for_match((chunk.display_text or "") + " " + (chunk.retrieval_text or ""))
        for chunk in retrieval.chunks
    )


def _parser_gap_signals(doc_dict: dict) -> list[str]:
    signals: list[str] = []
    if doc_dict.get("fallback_used"):
        signals.append("parser_fallback_used")
    if doc_dict.get("ocr_used"):
        signals.append("ocr_used")
    if doc_dict.get("parse_warnings"):
        signals.append("parse_warnings_present")
    return signals


def _build_retrieval_diagnostics(
    *,
    doc_dict: dict,
    retrieval: Optional[RetrievalResult],
    state: str,
    support: str,
    proposed_value: Optional[str],
    quotes: list[dict],
    evidence_records: list[EvidenceRecord],
    needs_more_evidence: bool,
    recall_rescue_used: bool,
    recall_rescue_decision: RecallRescueDecision,
    whole_document_used: bool,
    whole_document_decision: dict[str, object],
    warning_flags: list[str],
) -> dict:
    parser_signals = _parser_gap_signals(doc_dict)
    retrieval_chunks = retrieval.chunks if retrieval is not None else []
    chunk_types = [str(chunk.chunk_type) for chunk in retrieval_chunks[:5]]
    exact_evidence = sum(1 for ev in evidence_records if ev.source_type == EvidenceSourceType.direct_quote)
    approximate_evidence = sum(1 for ev in evidence_records if ev.source_type == EvidenceSourceType.approximate_highlight)
    fallback_evidence = sum(1 for ev in evidence_records if ev.source_type == EvidenceSourceType.quote_plus_page)
    figure_evidence = sum(1 for ev in evidence_records if ev.is_figure_derived)
    quoted_text_present = any(_value_mentioned_in_retrieval(quote.get("text"), retrieval) for quote in quotes)
    proposed_value_present = _value_mentioned_in_retrieval(proposed_value, retrieval)

    signals = list(parser_signals)
    if not retrieval_chunks:
        signals.append("no_retrieval_chunks")
    if recall_rescue_used:
        signals.append("recall_rescue_used")
    if whole_document_used:
        signals.append("whole_document_used")
    if approximate_evidence:
        signals.append("approximate_highlight_only")
    if fallback_evidence:
        signals.append("quote_plus_page_fallback")
    if proposed_value_present:
        signals.append("proposed_value_seen_in_retrieval")
    if quoted_text_present:
        signals.append("quote_seen_in_retrieval")
    if figure_evidence:
        signals.append("figure_evidence_present")

    classification = "not_needed"
    if "provider_error" in warning_flags or state == "error":
        classification = "provider_failure"
    elif state in ("blocked", "skipped"):
        classification = "blocked_upstream"
    elif not retrieval_chunks:
        classification = "parser_source_gap" if parser_signals else "retrieval_miss"
    elif exact_evidence == 0 and (approximate_evidence > 0 or fallback_evidence > 0):
        classification = "evidence_anchoring_gap"
    elif recall_rescue_used or whole_document_used:
        classification = "retrieval_policy_limit"
    elif (state == "unclear" or needs_more_evidence or support == "weak_evidence") and (proposed_value_present or quoted_text_present):
        classification = "reasoning_gap"
    elif state == "unclear" or needs_more_evidence or support == "weak_evidence":
        classification = "retrieval_miss"
    elif parser_signals and exact_evidence == 0:
        classification = "parser_source_gap"

    return {
        "classification": classification,
        "signals": signals,
        "query": retrieval.query if retrieval is not None else None,
        "request_mode": retrieval.request_mode if retrieval is not None else None,
        "retrieval_mode": retrieval.mode if retrieval is not None else None,
        "top_k": retrieval.top_k if retrieval is not None else None,
        "retrieved_chunk_count": len(retrieval_chunks),
        "top_chunk_types": chunk_types,
        "parser_gap_signals": parser_signals,
        "quote_count": len(quotes),
        "exact_evidence_count": exact_evidence,
        "approximate_evidence_count": approximate_evidence,
        "fallback_evidence_count": fallback_evidence,
        "figure_evidence_count": figure_evidence,
        "proposed_value_seen_in_retrieval": proposed_value_present,
        "quoted_text_seen_in_retrieval": quoted_text_present,
        "recall_rescue_eligible": recall_rescue_decision.eligible,
        "recall_rescue_trigger_reasons": list(recall_rescue_decision.trigger_reasons),
        "recall_rescue_skip_reason": recall_rescue_decision.skip_reason,
        "whole_document_eligible": bool(whole_document_decision.get("eligible")),
        "whole_document_skip_reason": whole_document_decision.get("skip_reason"),
    }


def _build_figure_review_diagnostics(
    *,
    triggered: bool,
    trigger_reasons: list[str],
    shortlist_metadata: list[dict],
    figure_review_calls: int,
    figure_review_ms: float,
    figure_hits: list[FigureReviewHit],
    attempt_diagnostics: list[dict],
    ranked_evidence: list[EvidenceRecord],
    figure_rescued_value: bool,
    suppressed_reason: Optional[str] = None,
) -> dict:
    figure_evidence_persisted = sum(1 for ev in ranked_evidence if ev.is_figure_derived)
    useful = figure_evidence_persisted > 0 or figure_rescued_value
    attempted = any(bool(item.get("attempted")) for item in attempt_diagnostics)
    succeeded = any(bool(item.get("succeeded")) for item in attempt_diagnostics)
    failed = any(bool(item.get("attempted")) and not bool(item.get("succeeded")) for item in attempt_diagnostics)
    succeeded_without_hit = sum(
        1
        for item in attempt_diagnostics
        if bool(item.get("succeeded")) and item.get("dropped_reason")
    )
    promoted_unclear_values = sum(1 for item in attempt_diagnostics if bool(item.get("promoted_unclear_value")))
    accepted_hit_count = sum(1 for item in attempt_diagnostics if bool(item.get("accepted_as_hit")))
    value_present_count = sum(1 for item in attempt_diagnostics if bool(item.get("result_value_present")))
    dropped_reason_counts: dict[str, int] = {}
    result_state_counts: dict[str, int] = {}
    for item in attempt_diagnostics:
        result_state = item.get("result_state")
        if result_state:
            key = str(result_state)
            result_state_counts[key] = result_state_counts.get(key, 0) + 1
        dropped_reason = item.get("dropped_reason")
        if dropped_reason:
            key = str(dropped_reason)
            dropped_reason_counts[key] = dropped_reason_counts.get(key, 0) + 1
    failure_reason = next(
        (
            str(item.get("failure_reason"))
            for item in reversed(attempt_diagnostics)
            if item.get("failure_reason")
        ),
        None,
    )
    return {
        "triggered": triggered,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "suppressed": suppressed_reason is not None,
        "trigger_reasons": list(trigger_reasons),
        "suppressed_reason": suppressed_reason,
        "failure_reason": failure_reason,
        "shortlist_size": len(shortlist_metadata),
        "review_calls": figure_review_calls,
        "review_ms": round(figure_review_ms, 3),
        "hit_count": len(figure_hits),
        "succeeded_without_hit_count": succeeded_without_hit,
        "promoted_unclear_value_count": promoted_unclear_values,
        "accepted_hit_count": accepted_hit_count,
        "value_present_count": value_present_count,
        "dropped_reason_counts": dropped_reason_counts,
        "result_state_counts": result_state_counts,
        "useful": useful,
        "figure_evidence_persisted": figure_evidence_persisted,
        "rescued_value": figure_rescued_value,
        "attempts": attempt_diagnostics[:10],
    }


def _normalize_quotes_payload(value: Any) -> list[dict]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    normalized: list[dict] = []
    for item in raw_items:
        if isinstance(item, dict):
            quote_text = _coerce_text_value(item.get("text"), joiner=" ")
            if not quote_text:
                continue
            page = item.get("page")
            if isinstance(page, str) and page.strip().isdigit():
                page = int(page.strip())
            normalized.append(
                {
                    "text": quote_text,
                    "page": page,
                    "source_type": _coerce_text_value(item.get("source_type"), joiner="_") or "direct_quote",
                }
            )
        else:
            quote_text = _coerce_text_value(item, joiner=" ")
            if quote_text:
                normalized.append({"text": quote_text, "page": None, "source_type": "direct_quote"})
    return normalized


def _safe_run_subpath(run_dir: pathlib.Path, *parts: str) -> pathlib.Path:
    if not parts:
        raise ValueError("Artifact subpath parts are required.")
    base = run_dir.resolve()
    path = base.joinpath(*parts).resolve()
    if path == base or base not in path.parents:
        raise ValueError("Artifact path must stay within the run directory.")
    return path


def _safe_evidence_filename(evidence_id: str, max_len: int = 16) -> str:
    """Return a deterministic short filename stem for persisted evidence."""
    safe = re.sub(r'[\\/:*?"<>|]', "_", evidence_id)
    safe = safe.replace(" ", "_")
    safe = re.sub(r"_+", "_", safe).strip("._")
    if not safe:
        safe = "evidence"
    if len(safe) <= max_len:
        return safe
    digest = hashlib.sha1(evidence_id.encode("utf-8")).hexdigest()[:10]
    truncated = safe[:max_len].rstrip("._") or "evidence"
    return f"{truncated}_{digest}"


def reason_code_for_blocked(blocked_reason: str) -> str:
    text = str(blocked_reason or "").lower()
    if "provider" in text:
        return PROVIDER_ERROR
    if "parser" in text or "parse" in text:
        return INVALID_MODEL_OUTPUT
    if "retrieval" in text:
        return RETRIEVAL_EMPTY
    if "target" in text or "cell" in text:
        return CELL_NOT_TARGETED
    return INSUFFICIENT_EVIDENCE


def make_blocked_proposal(
    run_id: str,
    pdf_id: str,
    row_id: str,
    cell_id: str,
    column_name: str,
    blocked_reason: str,
    run_dir: pathlib.Path,
) -> ProposalRecord:
    """Create a blocked proposal record (T058: blocked state)."""
    proposal_id = generate_proposal_id(run_id, cell_id)
    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        cell_id=cell_id,
        **_semantics_fields(ProposalStatus.unresolved, EvidenceStatus.no_evidence, [reason_code_for_blocked(blocked_reason)]),
        proposed_value=None,
        rationale=blocked_reason,
        evidence_ids=[],
        warning_flags=["blocked"],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_proposal(run_dir, proposal)
    return proposal


def make_skipped_proposal(
    run_id: str,
    pdf_id: str,
    row_id: str,
    cell_id: str,
    column_name: str,
    skip_reason: str,
    run_dir: pathlib.Path,
) -> ProposalRecord:
    """Create a skipped proposal record (T058: skipped state)."""
    proposal_id = generate_proposal_id(run_id, cell_id)
    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        cell_id=cell_id,
        **_semantics_fields(ProposalStatus.not_attempted, EvidenceStatus.not_applicable, [CELL_NOT_TARGETED]),
        proposed_value=None,
        rationale=skip_reason,
        evidence_ids=[],
        warning_flags=["skipped"],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_proposal(run_dir, proposal)
    return proposal
