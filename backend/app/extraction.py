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
import json
import pathlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from .artifacts import (
    append_jsonl,
    read_json,
    read_jsonl,
    write_json,
)
from .ids import generate_evidence_id, generate_proposal_id
from .provider import (
    ProviderAdapter,
)
from .retrieval import RetrievalResult
from .schemas import (
    EvidenceSourceType,
    NumericValueForm,
    ProposalState,
    SchemaFieldType,
    SupportLabel,
)
from .style_profiles import StyleProfile


# ---------------------------------------------------------------------------
# Evidence record (extended contract for Batch 3)
# ---------------------------------------------------------------------------

class EvidenceRecord(BaseModel):
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
    state: ProposalState
    support: SupportLabel
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
    created_at: str


class FigureReviewHit(BaseModel):
    proposed_value: str
    rationale: Optional[str] = None
    evidence: EvidenceRecord


# ---------------------------------------------------------------------------
# Support-label mapping (T065)
# ---------------------------------------------------------------------------

SUPPORT_LABEL_DISPLAY = {
    SupportLabel.direct_evidence: "Direct evidence",
    SupportLabel.inferred_from_evidence: "Inferred from evidence",
    SupportLabel.weak_evidence: "Weak evidence",
    SupportLabel.blocked: "Blocked",
    SupportLabel.error: "Error",
}

EVIDENCE_TYPE_DISPLAY = {
    EvidenceSourceType.direct_quote: "Direct quote",
    EvidenceSourceType.inferred_reasoning: "Inferred reasoning",
    EvidenceSourceType.calculation: "Calculation",
    EvidenceSourceType.approximate_highlight: "Approximate highlight",
    EvidenceSourceType.quote_plus_page: "Quote + page (fallback)",
    EvidenceSourceType.caption_grounded_figure_evidence: "Caption-grounded figure evidence",
    EvidenceSourceType.visual_interpretation_figure_evidence: "Visual-interpretation figure evidence",
}


def proposal_support_display(support: SupportLabel) -> str:
    return SUPPORT_LABEL_DISPLAY.get(support, support.value)


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
            "type": "boolean",
            "description": "Whether the figure caption directly supports the value.",
        },
    },
    "required": [
        "proposed_value",
        "state",
        "rationale",
        "numeric_value_form",
        "figure_description",
        "caption_relevant",
    ],
}


# ---------------------------------------------------------------------------
# Prompt building (T053, T053a, T057a)
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = (
    "You are an expert scientific data extractor. "
    "Your job is to extract a specific piece of information from a scientific paper. "
    "Extract ONLY information that is actually stated or can be directly calculated from the paper. "
    "Do NOT guess based on common knowledge, general practice, or prior spreadsheet values. "
    "If the information is not clearly supported by the paper, return state='unclear'. "
    "Return concise markdown-bullet rationale (at most 3 bullets). "
    "Respond ONLY with valid JSON matching the required schema."
)

_FIGURE_SYSTEM = (
    "You are an expert scientific data extractor analyzing a figure from a scientific paper. "
    "Your job is to determine whether this figure provides evidence for a specific data field. "
    "Extract information ONLY from what is visible in the figure and its caption. "
    "If the figure does not contain useful evidence for this field, return state='unclear'. "
    "Respond ONLY with valid JSON matching the required schema."
)


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
        tag = f"[{chunk.chunk_type.upper()}, page {chunk.page_number}]"
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
            "\n\nWhole-document rescue context (use only because the first pass was unclear):\n"
            f"{whole_document_text}"
        )

    user_content = (
        f"Extract: {column_name}\n"
        f"Field description: {column_description}\n\n"
        f"Paper row context:\n{row_block}"
        f"{verify_block}"
        f"{long_text_note}"
        f"{field_contract}"
        f"{style_block}\n\n"
        f"{context_block}\n\n"
        f"{whole_document_block}\n\n"
        "Instructions:\n"
        "1. Return proposed_value=null and state='unclear' if the paper does not clearly support a value.\n"
        "2. Use state='found' for directly stated values, 'inferred' for derived/reasoned values.\n"
        "3. Include one or more evidence quotes when they are genuinely needed to support the value.\n"
        "4. Rationale must be ≤3 concise markdown bullets (- bullet text).\n"
        "5. Never fabricate quotes; only use text that appears in the passages above.\n"
        "6. Only set numeric_value_form when the field is numeric; otherwise return null.\n"
        "7. Return ONLY valid JSON matching the schema."
    )

    return [
        {"role": "system", "content": _EXTRACTION_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_figure_extraction_prompt(
    column_name: str,
    column_description: str,
    caption_text: Optional[str],
    nearby_text: Optional[str],
    field_type: Optional[SchemaFieldType] = None,
    allowed_values: Optional[list[str]] = None,
) -> list[dict]:
    """Build the vision-model figure extraction prompt (T063)."""
    caption_block = f"Figure caption: {caption_text}" if caption_text else "No caption available."
    nearby_block = f"Nearby text: {nearby_text[:400]}" if nearby_text else ""

    user_content = (
        f"Field to extract: {column_name}\n"
        f"Field description: {column_description}\n\n"
        f"{_build_field_contract(field_type, allowed_values)}\n\n"
        f"{caption_block}\n"
        f"{nearby_block}\n\n"
        "Analyze the figure image. "
        "Does this figure provide evidence for the field above? "
        "If yes, extract the value. If not, return state='unclear'. "
        "Return ONLY valid JSON matching the schema."
    )

    return [
        {"role": "system", "content": _FIGURE_SYSTEM},
        {"role": "user", "content": user_content},
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

    approx_regions, approx_conf, _ = find_approximate_highlight_regions(
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
) -> tuple[ProposalState, SupportLabel]:
    """Map raw model state to ProposalState + SupportLabel.

    T058a: prefer unclear over guesses with weak support.
    """
    if not proposed_value or not proposed_value.strip():
        return ProposalState.unclear, SupportLabel.blocked

    has_any_quote = bool(quotes)

    if raw_state == "found":
        if any(q.get("source_type") == "direct_quote" for q in quotes):
            return ProposalState.found, SupportLabel.direct_evidence
        if any(q.get("source_type") != "direct_quote" for q in quotes):
            return ProposalState.found, SupportLabel.inferred_from_evidence
        else:
            return ProposalState.inferred, SupportLabel.inferred_from_evidence

    elif raw_state == "inferred":
        if has_any_quote:
            return ProposalState.inferred, SupportLabel.inferred_from_evidence
        else:
            return ProposalState.inferred, SupportLabel.weak_evidence

    else:  # unclear or unknown
        return ProposalState.unclear, SupportLabel.blocked


def determine_support_label(
    state: ProposalState,
    evidence_records: list[EvidenceRecord],
    proposed_value: Optional[str] = None,
    field_type: Optional[SchemaFieldType] = None,
) -> SupportLabel:
    if state == ProposalState.error:
        return SupportLabel.error
    if state in (ProposalState.blocked, ProposalState.skipped, ProposalState.unclear):
        return SupportLabel.blocked
    if any(
        ev.source_type == EvidenceSourceType.direct_quote
        and _quote_directly_supports_value(ev.quote_text, proposed_value, field_type)
        for ev in evidence_records
    ):
        return SupportLabel.direct_evidence
    if evidence_records:
        return SupportLabel.inferred_from_evidence
    return SupportLabel.weak_evidence


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
            "content": (
                "You are a scientific evidence extractor. "
                "Find the single best verbatim quote from the passages that most directly "
                "supports the value for the given field. "
                "Return ONLY a JSON object with: "
                '{"quote": "verbatim text", "page": page_number_or_null}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Field: {column_name} — {column_description}\n\n"
                f"Passages:\n{context_passages}\n\n"
                "Return the single best verbatim quote."
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
        quote_text = result.get("quote", "").strip()
        page_num = result.get("page")
        if not quote_text:
            return None

        source_type, exact_regions, approx_regions, confidence = anchor_evidence(
            quote_text, page_num, doc_dict
        )

        ev_id = generate_evidence_id(proposal_id)
        return EvidenceRecord(
            evidence_id=ev_id,
            run_id=run_id,
            proposal_id=proposal_id,
            pdf_id=pdf_id,
            source_type=source_type,
            quote_text=quote_text,
            page_number=page_num,
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


def select_relevant_figures(
    figures: list[dict],
    column_name: str,
    column_description: str,
    max_figures: int = 5,
) -> list[dict]:
    """Select relevant figures by caption relevance heuristic (T062).

    Not every figure is processed — targeted rather than unrestricted.
    """
    scored = []
    for fig in figures:
        caption = fig.get("caption_text", "") or ""
        score = _caption_relevance_score(caption, column_name, column_description)
        scored.append((score, fig))
    # Include any figure with nonzero score, plus top figures by score
    scored.sort(key=lambda x: -x[0])
    selected = [f for s, f in scored if s > 0.1]
    if not selected:
        # Fall back to top figures by position
        selected = [f for _, f in scored[:2]]
    return selected[:max_figures]


def _load_figure_image_b64(figure: dict, run_dir: pathlib.Path) -> Optional[str]:
    """Load a figure crop as base64 PNG, if the crop file exists."""
    crop_path = figure.get("crop_path")
    if not crop_path:
        return None
    full_path = run_dir / crop_path if not pathlib.Path(crop_path).is_absolute() else pathlib.Path(crop_path)
    if full_path.exists():
        try:
            with open(full_path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        except Exception:
            return None
    return None


def _normalize_value_for_compare(value: Optional[str]) -> str:
    if not value:
        return ""
    lowered = unicodedata.normalize("NFKD", value.lower())
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _values_match(left: Optional[str], right: Optional[str]) -> bool:
    left_norm = _normalize_value_for_compare(left)
    right_norm = _normalize_value_for_compare(right)
    return bool(left_norm and right_norm and left_norm == right_norm)


async def run_figure_review(
    proposal_id: str,
    run_id: str,
    pdf_id: str,
    column_name: str,
    column_description: str,
    doc_dict: dict,
    run_dir: pathlib.Path,
    provider: ProviderAdapter,
    vision_model_id: str,
    current_proposed_value: Optional[str] = None,
    field_type: Optional[SchemaFieldType] = None,
    allowed_values: Optional[list[str]] = None,
    max_figures: int = 5,
) -> list[FigureReviewHit]:
    """Proactive figure review (T062): run vision model over relevant figures.

    Targeted: only relevant figures by caption heuristic.
    Returns figure hits that can either support a text proposal or rescue an empty one.
    """
    figures = doc_dict.get("figures", [])
    if not figures:
        return []

    relevant = select_relevant_figures(figures, column_name, column_description, max_figures)
    figure_hits: list[FigureReviewHit] = []

    for figure in relevant:
        fig_id = figure.get("figure_id", "unknown")
        caption = figure.get("caption_text", "")
        nearby_text = _find_nearby_text(fig_id, doc_dict)

        # Load figure crop image
        image_b64 = _load_figure_image_b64(figure, run_dir)
        if image_b64 is None:
            continue

        # Build vision prompt (T063)
        messages = build_figure_extraction_prompt(
            column_name,
            column_description,
            caption,
            nearby_text,
            field_type=field_type,
            allowed_values=allowed_values,
        )

        try:
            result = await provider.vision_complete_structured(
                messages=messages,
                response_schema=VISION_EXTRACTION_SCHEMA,
                model_id=vision_model_id,
                image_b64=image_b64,
            )
            fig_state = result.get("state", "unclear")
            fig_value = result.get("proposed_value")
            fig_rationale = result.get("rationale")
            fig_description = result.get("figure_description", "")

            if fig_state == "unclear" or not fig_value:
                continue  # This figure doesn't support the field

            if current_proposed_value and not _values_match(fig_value, current_proposed_value):
                continue

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
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            figure_hits.append(
                FigureReviewHit(
                    proposed_value=str(fig_value).strip(),
                    rationale=fig_rationale,
                    evidence=ev,
                )
            )
        except Exception:
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
    line_count = len(read_jsonl(jsonl_path))
    index[proposal.proposal_id] = {
        "proposal_id": proposal.proposal_id,
        "row_id": proposal.row_id,
        "column_name": proposal.column_name,
        "pdf_id": proposal.pdf_id,
        "state": proposal.state.value,
        "support": proposal.support.value,
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
    path = _safe_run_subpath(run_dir, "evidence", f"{evidence.evidence_id}.json")
    write_json(path, evidence.model_dump())
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
    whole_document_mode: bool = False,
    whole_document_max_chars: int = 12000,
    provider_mode_str: str = "unknown",
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

    long_text = is_long_text_field(column_name, column_description)

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
    )

    # T057a: long text fields get more tokens
    max_tokens = 4096 if long_text else 2048

    try:
        raw_result = await provider.chat_complete_structured(
            messages=messages,
            response_schema=TEXT_EXTRACTION_SCHEMA,
            model_id=text_model_id,
            max_tokens=max_tokens,
        )
    except Exception as e:
        # Hard provider error — record error proposal
        proposal = ProposalRecord(
            proposal_id=proposal_id,
            run_id=run_id,
            pdf_id=pdf_id,
            row_id=row_id,
            column_name=column_name,
            cell_id=cell_id,
            state=ProposalState.error,
            support=SupportLabel.error,
            proposed_value=None,
            rationale=f"Provider error: {e}",
            evidence_ids=[],
            warning_flags=["provider_error"],
            provider_mode=provider_mode_str,
            is_verify_mode=is_verify_mode,
            existing_value=existing_value,
            created_at=now,
        )
        persist_proposal(run_dir, proposal)
        return proposal

    recall_rescue_used = False
    whole_document_used = False

    raw_state = raw_result.get("state", "unclear")
    if raw_state == "unclear" and recall_rescue_enabled:
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
                rescue_reason="first_pass_unclear",
            )
        whole_document_text = None
        if whole_document_mode:
            whole_document_text = build_whole_document_context(doc_dict, whole_document_max_chars)
            whole_document_used = whole_document_text is not None
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
        )
        try:
            raw_result = await provider.chat_complete_structured(
                messages=rescue_messages,
                response_schema=TEXT_EXTRACTION_SCHEMA,
                model_id=text_model_id,
                max_tokens=max_tokens,
            )
        except Exception as e:
            proposal = ProposalRecord(
                proposal_id=proposal_id,
                run_id=run_id,
                pdf_id=pdf_id,
                row_id=row_id,
                column_name=column_name,
                cell_id=cell_id,
                state=ProposalState.error,
                support=SupportLabel.error,
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
                created_at=now,
            )
            persist_proposal(run_dir, proposal)
            return proposal

    # Parse and adjudicate result (T058)
    raw_state = raw_result.get("state", "unclear")
    proposed_value = raw_result.get("proposed_value")
    rationale = raw_result.get("rationale")
    calculation = raw_result.get("calculation")
    numeric_value_form = _normalize_numeric_value_form(
        raw_result.get("numeric_value_form"),
        field_type,
    )
    quotes: list[dict] = raw_result.get("quotes") or []

    # T053a: ensure rationale is compact bullets
    rationale = _normalize_rationale(rationale)

    state, _ = adjudicate_state(raw_state, proposed_value, quotes, is_verify_mode)

    # Build evidence records from quotes (T059)
    evidence_records: list[EvidenceRecord] = []

    for q in quotes:
        quote_text = q.get("text", "").strip()
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
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        else:
            # Attempt anchoring (T059)
            anchored_type, exact_regions, approx_regions, confidence = anchor_evidence(
                quote_text, page_num, doc_dict
            )
            ev_id = generate_evidence_id(proposal_id)
            ev = EvidenceRecord(
                evidence_id=ev_id,
                run_id=run_id,
                proposal_id=proposal_id,
                pdf_id=pdf_id,
                source_type=anchored_type,
                quote_text=quote_text,
                page_number=page_num,
                exact_highlight_regions=exact_regions or None,
                approximate_highlight_regions=approx_regions or None,
                anchor_confidence=confidence,
                evidence_rank=99,
                is_primary=False,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        evidence_records.append(ev)

    # Evidence recovery pass (T060): if no usable evidence, try once
    has_usable_evidence = any(
        ev.source_type not in (EvidenceSourceType.quote_plus_page,)
        or ev.quote_text
        for ev in evidence_records
    )
    needs_more = not has_usable_evidence and state != ProposalState.unclear

    if needs_more and proposed_value:
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
        )
        if recovery_ev:
            evidence_records.append(recovery_ev)
            needs_more = False

    # Proactive figure review (T062): when vision model configured
    figure_hits: list[FigureReviewHit] = []
    if vision_model_id and doc_dict.get("figures"):
        try:
            figure_hits = await run_figure_review(
                proposal_id=proposal_id,
                run_id=run_id,
                pdf_id=pdf_id,
                column_name=column_name,
                column_description=column_description,
                doc_dict=doc_dict,
                run_dir=run_dir,
                provider=provider,
                vision_model_id=vision_model_id,
                current_proposed_value=proposed_value,
                field_type=field_type,
                allowed_values=allowed_values,
            )
        except Exception:
            pass  # Figure review failure does not abort the proposal

    figure_evidence = [hit.evidence for hit in figure_hits]

    all_evidence = evidence_records + figure_evidence

    # Rank evidence (T065)
    ranked_evidence = rank_evidence(all_evidence)

    # Allow figure evidence to rescue an empty text proposal (T062)
    if figure_hits and not proposed_value:
        best_figure_hit = figure_hits[0]
        proposed_value = best_figure_hit.proposed_value
        if not rationale:
            rationale = _normalize_rationale(best_figure_hit.rationale)
        state = ProposalState.inferred
        needs_more = False

    support = determine_support_label(
        state,
        ranked_evidence,
        proposed_value=proposed_value,
        field_type=field_type,
    )

    # Persist evidence records
    for ev in ranked_evidence:
        persist_evidence(run_dir, ev)

    # Build final proposal
    primary_ev_id = ranked_evidence[0].evidence_id if ranked_evidence else None
    supporting_ids = [ev.evidence_id for ev in ranked_evidence[1:]]
    all_ev_ids = [ev.evidence_id for ev in ranked_evidence]

    warning_flags = []
    if needs_more:
        warning_flags.append("needs_more_evidence")
    if recall_rescue_used:
        warning_flags.append("recall_rescue_used")
    if whole_document_used:
        warning_flags.append("whole_document_used")
    if any(ev.is_figure_derived for ev in ranked_evidence):
        warning_flags.append("figure_derived")
    if any(ev.source_type == EvidenceSourceType.quote_plus_page for ev in ranked_evidence):
        warning_flags.append("fallback_evidence_used")
    if any(ev.source_type == EvidenceSourceType.approximate_highlight for ev in ranked_evidence):
        warning_flags.append("approximate_highlight")

    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        cell_id=cell_id,
        state=state,
        support=support,
        proposed_value=proposed_value,
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
        created_at=now,
    )

    persist_proposal(run_dir, proposal)
    return proposal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_rationale(rationale: Optional[str]) -> Optional[str]:
    """Ensure rationale is compact markdown bullets (T053a)."""
    if not rationale:
        return None
    stripped = rationale.strip()
    # If it's already bullet-formatted, return as-is
    if stripped.startswith("- ") or stripped.startswith("* "):
        return stripped
    # Convert single sentence to a bullet
    sentences = [s.strip() for s in stripped.split(".") if s.strip()]
    if len(sentences) <= 3:
        return "\n".join(f"- {s}." for s in sentences[:3])
    # Truncate to 3 bullets
    return "\n".join(f"- {s}." for s in sentences[:3]) + "\n- ..."


def _safe_run_subpath(run_dir: pathlib.Path, *parts: str) -> pathlib.Path:
    if not parts:
        raise ValueError("Artifact subpath parts are required.")
    base = run_dir.resolve()
    path = base.joinpath(*parts).resolve()
    if path == base or base not in path.parents:
        raise ValueError("Artifact path must stay within the run directory.")
    return path


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
        state=ProposalState.blocked,
        support=SupportLabel.blocked,
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
        state=ProposalState.skipped,
        support=SupportLabel.blocked,
        proposed_value=None,
        rationale=skip_reason,
        evidence_ids=[],
        warning_flags=["skipped"],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_proposal(run_dir, proposal)
    return proposal
