"""
Batch 3 — Extraction orchestrator, request builder, proposal/evidence serialization.

Implements:
- T053: Extraction request builder
- T054: Text-model structured JSON schema
- T055: Vision-model structured JSON schema
- T056: Proposal/evidence serialization via shared artifact I/O
- T057: Per-target-cell extraction orchestrator
- T058: Proposal state handling (found/inferred/unclear/blocked/error/skipped)
- T059: Text evidence anchoring (quote + page + highlight)
- T060: Evidence recovery pass
- T061: Weak proposals with quote+page
- T062: Figure fallback trigger
- T063: Figure fallback input package
- T064: Figure-derived evidence records
- T065: Support-label mapping
- T066: Verify mode extraction
"""
from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from .ids import make_evidence_id, make_proposal_id
from .provider import ProviderAdapter, ProviderError, StructuredOutputError
from .schemas import (
    EvidenceHighlight,
    EvidenceRecord,
    EvidenceSourceType,
    ProposalRecord,
    ProposalState,
    SupportLabel,
)

if TYPE_CHECKING:
    from .artifacts import RunArtifacts
    from .parsing import ParsedDocument
    from .retrieval import RetrievalChunk, RetrievalResult
    from .style_profiles import StyleProfile

logger = logging.getLogger(__name__)

# Minimum prefix length used when matching evidence quotes against document text
QUOTE_MATCH_PREFIX_LENGTH = 40


# ---------------------------------------------------------------------------
# T054 — Text-model structured JSON schema
# ---------------------------------------------------------------------------

TEXT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["proposal_state", "proposed_value", "rationale"],
    "properties": {
        "proposal_state": {
            "type": "string",
            "enum": ["found", "inferred", "unclear", "skipped"],
            "description": "Whether the value was directly found, inferred, unclear, or should be skipped.",
        },
        "proposed_value": {
            "type": "string",
            "description": "The extracted or inferred value, or empty string if unclear/skipped.",
        },
        "rationale": {
            "type": "string",
            "description": "Brief explanation of where/how the value was found or inferred.",
        },
        "calculation": {
            "type": "string",
            "description": "Calculation steps when the value is derived numerically. Empty otherwise.",
        },
        "needs_more_evidence": {
            "type": "boolean",
            "description": "True if the evidence is weak or incomplete.",
        },
        "evidence_quote": {
            "type": "string",
            "description": "Exact verbatim quote from the paper supporting this value.",
        },
        "evidence_page": {
            "type": "integer",
            "description": "Page number (1-based) of the evidence quote.",
        },
    },
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# T055 — Vision-model structured JSON schema (same shape + figure fields)
# ---------------------------------------------------------------------------

VISION_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["proposal_state", "proposed_value", "rationale"],
    "properties": {
        **TEXT_EXTRACTION_SCHEMA["properties"],
        "figure_ref": {
            "type": "string",
            "description": "Figure identifier or label from the document (e.g. 'Figure 2').",
        },
        "caption_text": {
            "type": "string",
            "description": "Caption text associated with the figure/table.",
        },
    },
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# T053 — Extraction request builder
# ---------------------------------------------------------------------------


class ExtractionRequest(BaseModel):
    """Per-cell extraction request assembled for the LLM."""

    run_id: str
    pdf_id: str
    row_id: str
    column_name: str
    column_description: str
    current_value: str | None = None  # T066: Verify mode
    style_profile: dict[str, Any] = Field(default_factory=dict)
    retrieved_passages: list[str] = Field(default_factory=list)
    retrieved_display_passages: list[str] = Field(default_factory=list)  # source-preserving
    table_context: list[str] = Field(default_factory=list)
    row_context: dict[str, Any] = Field(default_factory=dict)
    verify_mode: bool = False
    source_mode: str = "text"  # "text" | "vision"


def build_extraction_system_prompt(verify_mode: bool = False) -> str:
    base = (
        "You are a scientific literature extraction assistant. "
        "Your task is to extract or infer a specific value from a scientific paper. "
        "Always ground your answer in the provided evidence passages. "
        "Never fabricate information not present in the passages. "
        "Set proposal_state to 'found' when you find a direct answer, "
        "'inferred' when you derive it by calculation or strong implication, "
        "'unclear' when the evidence is ambiguous or insufficient, "
        "and 'skipped' when the column is clearly not applicable to this paper."
    )
    if verify_mode:
        base += (
            " The cell already has a value — verify whether the existing value is supported "
            "by the paper evidence and note any discrepancy in your rationale."
        )
    return base


def build_extraction_user_prompt(request: ExtractionRequest) -> str:
    parts: list[str] = []

    # Row context (metadata)
    if request.row_context:
        ctx_lines = [f"  {k}: {v}" for k, v in request.row_context.items() if v]
        if ctx_lines:
            parts.append("Row context (other columns from the same spreadsheet row):\n" + "\n".join(ctx_lines))

    # Target column
    parts.append(f"Target column: {request.column_name!r}")
    parts.append(f"Column description: {request.column_description}")

    # Verify mode: show existing value
    if request.verify_mode and request.current_value:
        parts.append(f"Existing cell value (verify): {request.current_value!r}")

    # Style guidance (T043: format only, no semantic exemplars)
    sp = request.style_profile
    if sp:
        style_cues: list[str] = []
        if sp.get("field_type_guess"):
            style_cues.append(f"type={sp['field_type_guess']}")
        if sp.get("expected_length"):
            style_cues.append(f"length={sp['expected_length']}")
        if sp.get("unit_style"):
            style_cues.append(f"units={sp['unit_style']}")
        if sp.get("value_shape"):
            style_cues.append(f"shape={sp['value_shape']}")
        if sp.get("format_notes"):
            style_cues.append(f"notes: {sp['format_notes']}")
        if style_cues:
            parts.append("Style guidance (format only): " + "; ".join(style_cues))

    # Retrieved evidence passages
    if request.retrieved_passages:
        parts.append("Evidence passages from the paper:")
        for i, passage in enumerate(request.retrieved_passages, 1):
            parts.append(f"  [{i}] {passage}")

    # Table context
    if request.table_context:
        parts.append("Relevant table regions from the paper:")
        for i, tbl in enumerate(request.table_context, 1):
            parts.append(f"  [Table {i}] {tbl}")

    parts.append(
        "\nRespond with a JSON object following the schema provided in the system prompt."
    )
    return "\n\n".join(parts)


def build_extraction_request(
    run_id: str,
    pdf_id: str,
    row_id: str,
    row_data: dict[str, Any],
    column_name: str,
    column_description: str,
    style_profile: "StyleProfile | None",
    retrieval_result: "RetrievalResult | None",
    all_chunks: list["RetrievalChunk"],
    verify_mode: bool = False,
) -> ExtractionRequest:
    """T053: Assemble a per-cell ExtractionRequest from all available context."""
    from .retrieval import TABLE

    current_value = str(row_data.get(column_name, "")).strip() or None

    # Row context: metadata columns only (Title, Authors, Year)
    row_context = {
        k: str(v)
        for k, v in row_data.items()
        if k in ("Title", "Authors", "Publication Year")
        and str(v).strip()
    }

    # Retrieved evidence passages from retrieval result
    retrieved_passages: list[str] = []
    retrieved_display: list[str] = []
    table_context: list[str] = []
    all_chunks_map = {c.chunk_id: c for c in all_chunks}

    if retrieval_result:
        for chunk in retrieval_result.selected_chunks:
            if chunk.chunk_type == TABLE:
                table_context.append(chunk.display_text)
            else:
                retrieved_passages.append(chunk.retrieval_text)
                retrieved_display.append(chunk.display_text)
        # Add neighbor chunks as additional context
        for cid in retrieval_result.neighbor_chunk_ids:
            neighbor = all_chunks_map.get(cid)
            if neighbor and neighbor.chunk_type != TABLE:
                if neighbor.retrieval_text not in retrieved_passages:
                    retrieved_passages.append(neighbor.retrieval_text)
                    retrieved_display.append(neighbor.display_text)

    # Determine if vision model should be used
    source_mode = "text"  # T054/T055: default to text; vision override applied in orchestrator

    return ExtractionRequest(
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        column_description=column_description,
        current_value=current_value if verify_mode else None,
        style_profile=style_profile.model_dump(mode="json") if style_profile else {},
        retrieved_passages=retrieved_passages[:8],  # cap at 8 for prompt length
        retrieved_display_passages=retrieved_display[:8],
        table_context=table_context[:4],
        row_context=row_context,
        verify_mode=verify_mode,
        source_mode=source_mode,
    )


# ---------------------------------------------------------------------------
# T059 — Text evidence anchoring
# ---------------------------------------------------------------------------


def _find_quote_in_text(quote: str, full_text: str, page_texts: dict[int, str]) -> tuple[int | None, str | None]:
    """
    T059: Try to locate the quote in page texts.

    Returns (page_no, matched_quote) or (None, None) if not found.
    """
    if not quote or not quote.strip():
        return None, None

    normalized_quote = re.sub(r"\s+", " ", quote.strip().lower())

    # Search per page
    for page_no, page_text in sorted(page_texts.items()):
        normalized_page = re.sub(r"\s+", " ", page_text.lower())
        if normalized_quote[:QUOTE_MATCH_PREFIX_LENGTH] in normalized_page:
            return page_no, quote
    # Try full-document fallback
    normalized_full = re.sub(r"\s+", " ", full_text.lower())
    if normalized_quote[:QUOTE_MATCH_PREFIX_LENGTH] in normalized_full:
        # Try to determine page number from context
        return None, quote

    return None, None


def validate_and_anchor_evidence(
    proposed_value: str,
    evidence_quote: str,
    evidence_page: int | None,
    doc: "ParsedDocument",
) -> tuple[str | None, int | None, float]:
    """
    T059: Validate quote against parsed document and return (quote, page, confidence).

    Confidence:
    - 1.0: exact match on correct page
    - 0.7: found in doc but page unclear
    - 0.3: quote present in model response but not found in document
    - 0.0: no quote
    """
    if not evidence_quote:
        return None, evidence_page, 0.0

    # Build per-page text map
    page_texts: dict[int, str] = {}
    for block in doc.blocks:
        if block.page_no not in page_texts:
            page_texts[block.page_no] = ""
        page_texts[block.page_no] += " " + block.text

    found_page, matched_quote = _find_quote_in_text(evidence_quote, doc.full_text, page_texts)

    if matched_quote is None:
        # Quote not found in document — keep it but mark low confidence
        return evidence_quote, evidence_page, 0.3

    if evidence_page and found_page and evidence_page == found_page:
        return matched_quote, evidence_page, 1.0

    # Found in doc but page mismatch or unknown
    resolved_page = found_page or evidence_page
    confidence = 0.7 if found_page else 0.5
    return matched_quote, resolved_page, confidence


# ---------------------------------------------------------------------------
# T060 — Evidence recovery pass
# ---------------------------------------------------------------------------


def attempt_evidence_recovery(
    column_name: str,
    proposed_value: str,
    doc: "ParsedDocument",
    all_chunks: list["RetrievalChunk"],
) -> tuple[str | None, int | None]:
    """
    T060: Simple evidence recovery when the primary evidence is weak/missing.

    Searches for the proposed value as a literal pattern in the document.
    Returns (quote, page_no) or (None, None).
    """
    if not proposed_value.strip():
        return None, None

    search_term = re.sub(r"\s+", " ", proposed_value.strip().lower())
    if len(search_term) < 2:
        return None, None

    # Try to find any block containing the value
    for block in doc.reading_order_blocks:
        if search_term in block.normalized_text:
            # Extract a short quote around the found text
            idx = block.text.lower().find(search_term[:20])
            if idx >= 0:
                start = max(0, idx - 20)
                end = min(len(block.text), idx + len(search_term) + 40)
                quote = block.text[start:end].strip()
                return quote, block.page_no

    return None, None


# ---------------------------------------------------------------------------
# T062 — Figure fallback trigger
# ---------------------------------------------------------------------------

_VISUAL_ELEMENT_FIELD_KEYWORDS = frozenset([
    "figure", "fig", "chart", "plot", "image", "diagram", "graph",
    "table", "tbl", "illustration", "panel",
])


def should_trigger_figure_fallback(
    column_name: str,
    column_description: str,
    proposal_state: ProposalState,
    retrieval_result: "RetrievalResult | None",
) -> bool:
    """
    T062: Determine whether to trigger figure/vision fallback.

    Triggers only when:
    1. The field is likely figure/table-derived (keyword hint)
    2. AND text/table retrieval failed or remained insufficient
    """
    if proposal_state not in (ProposalState.UNCLEAR, ProposalState.ERROR):
        return False

    combined = f"{column_name} {column_description}".lower()
    field_suggests_figure = any(kw in combined for kw in _VISUAL_ELEMENT_FIELD_KEYWORDS)
    if not field_suggests_figure:
        return False

    # Check if retrieval was weak
    if retrieval_result is None:
        return True
    diag = retrieval_result.diagnostics
    top_scores = getattr(retrieval_result, "scores", [])
    max_score = max(top_scores) if top_scores else 0.0
    if max_score < 0.5 or diag.get("selected_count", 0) == 0:
        return True

    return False


# ---------------------------------------------------------------------------
# T063 — Figure fallback input package
# ---------------------------------------------------------------------------


class FigureInputPackage(BaseModel):
    """T063: Input package for figure-based extraction."""

    figure_id: str
    pdf_id: str
    page_no: int
    crop_path: str | None = None
    crop_b64: str | None = None
    caption_text: str | None = None
    nearby_text: str | None = None
    full_page_path: str | None = None


def build_figure_fallback_packages(
    doc: "ParsedDocument",
    artifacts_root: Path,
) -> list[FigureInputPackage]:
    """
    T063: Build figure input packages from the document.

    Returns one package per figure that has a crop artifact.
    """
    packages: list[FigureInputPackage] = []
    for fig in doc.figures:
        crop_path_rel = f"parsed/{doc.pdf_id}/figures/{fig.figure_id}_crop.png"
        crop_path_abs = artifacts_root / crop_path_rel
        full_page_rel = f"parsed/{doc.pdf_id}/pages/page_{fig.page_no:04d}.png"

        crop_b64 = None
        if crop_path_abs.exists():
            with crop_path_abs.open("rb") as fh:
                crop_b64 = base64.b64encode(fh.read()).decode("ascii")
        elif not crop_path_abs.exists():
            continue  # Skip if no crop available

        packages.append(
            FigureInputPackage(
                figure_id=fig.figure_id,
                pdf_id=doc.pdf_id,
                page_no=fig.page_no,
                crop_path=str(crop_path_abs),
                crop_b64=crop_b64,
                caption_text=fig.caption_text,
                nearby_text=_get_nearby_text(doc, fig.page_no),
                full_page_path=str(artifacts_root / full_page_rel),
            )
        )
    return packages


def _get_nearby_text(doc: "ParsedDocument", page_no: int) -> str:
    """Extract a short excerpt of text from the same page."""
    page_blocks = [b for b in doc.blocks if b.page_no == page_no and b.block_type not in ("figure", "caption")]
    texts = [b.text for b in sorted(page_blocks, key=lambda b: b.reading_order)[:4]]
    return " ".join(texts)[:400]


# ---------------------------------------------------------------------------
# T056 — Proposal/evidence serialization
# ---------------------------------------------------------------------------


def _make_evidence_record(
    run_id: str,
    proposal_id: str,
    pdf_id: str,
    source_type: EvidenceSourceType,
    page: int | None,
    quote_text: str | None,
    anchor_confidence: float,
    highlight: EvidenceHighlight | None = None,
    figure_ref: str | None = None,
    caption_text: str | None = None,
    crop_path: str | None = None,
    full_page_path: str | None = None,
    ordinal: int = 0,
) -> EvidenceRecord:
    evidence_id = make_evidence_id(run_id, proposal_id, ordinal)
    return EvidenceRecord(
        evidence_id=evidence_id,
        proposal_id=proposal_id,
        pdf_id=pdf_id,
        source_type=source_type,
        page=page,
        quote_text=quote_text,
        highlight=highlight,
        figure_ref=figure_ref,
        caption_text=caption_text,
        crop_path=crop_path,
        full_page_path=full_page_path,
        anchor_confidence=anchor_confidence,
    )


def persist_proposal_and_evidence(
    artifacts: "RunArtifacts",
    proposal: ProposalRecord,
    evidence_list: list[EvidenceRecord],
) -> None:
    """T056: Persist proposal and evidence records to stable bundle locations."""
    artifacts.append_jsonl("proposals/proposals.jsonl", proposal.model_dump(mode="json"))
    for ev in evidence_list:
        artifacts.append_jsonl("evidence/evidence.jsonl", ev.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# T065 — Support-label mapping
# ---------------------------------------------------------------------------


def map_support_label(
    proposal_state: ProposalState,
    anchor_confidence: float,
    source_mode: str,
    is_figure_derived: bool = False,
) -> SupportLabel:
    """
    T065: Map internal state + evidence quality to a reviewer-facing SupportLabel.
    """
    if is_figure_derived:
        return SupportLabel.FIGURE_BASED_EVIDENCE
    if proposal_state == ProposalState.FOUND:
        if anchor_confidence >= 0.7:
            return SupportLabel.DIRECT_EVIDENCE
        return SupportLabel.WEAK_EVIDENCE
    if proposal_state == ProposalState.INFERRED:
        return SupportLabel.INFERRED_FROM_EVIDENCE
    return SupportLabel.WEAK_EVIDENCE


# ---------------------------------------------------------------------------
# T057 — Per-target-cell extraction orchestrator
# ---------------------------------------------------------------------------


def extract_cell(
    request: ExtractionRequest,
    provider: ProviderAdapter,
    doc: "ParsedDocument",
    run_id: str,
    all_chunks: list["RetrievalChunk"],
) -> tuple[ProposalRecord, list[EvidenceRecord]]:
    """
    T057: Execute extraction for one target cell.

    Returns (ProposalRecord, [EvidenceRecord]).
    All proposal states from T058 are handled here.
    """
    from .ids import make_cell_id

    cell_id = make_cell_id(request.row_id, request.column_name)
    proposal_id = make_proposal_id(run_id, request.pdf_id, cell_id)

    # --- Execute LLM extraction ---
    raw_result: dict[str, Any] = {}
    proposal_state = ProposalState.ERROR
    proposed_value: str | None = None
    rationale: str | None = None
    calculation: str | None = None
    needs_more_evidence = False
    evidence_quote: str | None = None
    evidence_page: int | None = None
    is_figure_derived = False

    try:
        schema = TEXT_EXTRACTION_SCHEMA if request.source_mode == "text" else VISION_EXTRACTION_SCHEMA
        system_prompt = build_extraction_system_prompt(verify_mode=request.verify_mode)
        user_prompt = build_extraction_user_prompt(request)

        raw_result = provider.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=schema,
            max_tokens=512,
            temperature=0.0,
        )

        # Parse response (T058)
        state_str = str(raw_result.get("proposal_state", "unclear")).lower()
        proposal_state = _parse_proposal_state(state_str)
        proposed_value = str(raw_result.get("proposed_value", "")).strip() or None
        rationale = str(raw_result.get("rationale", "")).strip() or None
        calculation = str(raw_result.get("calculation", "")).strip() or None
        needs_more_evidence = bool(raw_result.get("needs_more_evidence", False))
        evidence_quote = str(raw_result.get("evidence_quote", "")).strip() or None
        evidence_page_raw = raw_result.get("evidence_page")
        evidence_page = int(evidence_page_raw) if evidence_page_raw is not None else None
        is_figure_derived = bool(raw_result.get("figure_ref"))

    except StructuredOutputError as exc:
        logger.warning("Structured output error for cell %s/%s: %s", request.column_name, request.pdf_id, exc)
        proposal_state = ProposalState.ERROR
        rationale = f"Extraction failed: structured output parsing error — {exc}"
    except ProviderError as exc:
        logger.warning("Provider error for cell %s/%s: %s", request.column_name, request.pdf_id, exc)
        proposal_state = ProposalState.ERROR
        rationale = f"Extraction failed: provider error — {exc}"
    except Exception as exc:
        logger.error("Unexpected extraction error for cell %s/%s: %s", request.column_name, request.pdf_id, exc)
        proposal_state = ProposalState.ERROR
        rationale = f"Extraction failed: unexpected error — {exc}"

    # --- T059: Evidence anchoring ---
    anchor_confidence = 0.0
    primary_evidence: EvidenceRecord | None = None
    evidence_list: list[EvidenceRecord] = []

    if evidence_quote and proposal_state not in (ProposalState.ERROR, ProposalState.BLOCKED, ProposalState.SKIPPED):
        validated_quote, validated_page, anchor_confidence = validate_and_anchor_evidence(
            proposed_value=proposed_value or "",
            evidence_quote=evidence_quote,
            evidence_page=evidence_page,
            doc=doc,
        )

        if anchor_confidence >= 0.3:
            # T061: Keep quote+page proposals even when highlight anchoring fails
            source_type = (
                EvidenceSourceType.TEXT_HIGHLIGHT if anchor_confidence >= 0.7
                else EvidenceSourceType.TEXT_QUOTE
            )
            primary_evidence = _make_evidence_record(
                run_id=run_id,
                proposal_id=proposal_id,
                pdf_id=request.pdf_id,
                source_type=source_type,
                page=validated_page,
                quote_text=validated_quote,
                anchor_confidence=anchor_confidence,
                ordinal=0,
            )
            evidence_list.append(primary_evidence)
        else:
            # T060: Evidence recovery pass
            rec_quote, rec_page = attempt_evidence_recovery(
                column_name=request.column_name,
                proposed_value=proposed_value or "",
                doc=doc,
                all_chunks=all_chunks,
            )
            if rec_quote:
                anchor_confidence = 0.3
                primary_evidence = _make_evidence_record(
                    run_id=run_id,
                    proposal_id=proposal_id,
                    pdf_id=request.pdf_id,
                    source_type=EvidenceSourceType.TEXT_QUOTE,
                    page=rec_page,
                    quote_text=rec_quote,
                    anchor_confidence=anchor_confidence,
                    ordinal=0,
                )
                evidence_list.append(primary_evidence)
                needs_more_evidence = True
            else:
                needs_more_evidence = True

    # Handle figure-derived evidence (T064)
    if is_figure_derived:
        fig_ref = str(raw_result.get("figure_ref", ""))
        caption = str(raw_result.get("caption_text", "")).strip() or None
        fig_evidence = _make_evidence_record(
            run_id=run_id,
            proposal_id=proposal_id,
            pdf_id=request.pdf_id,
            source_type=EvidenceSourceType.FIGURE_CROP,
            page=evidence_page,
            quote_text=None,
            anchor_confidence=0.6,
            figure_ref=fig_ref,
            caption_text=caption,
            ordinal=len(evidence_list),
        )
        evidence_list.append(fig_evidence)
        if primary_evidence is None:
            primary_evidence = fig_evidence

    # T065: Map support label
    support_label = map_support_label(
        proposal_state=proposal_state,
        anchor_confidence=anchor_confidence,
        source_mode=request.source_mode,
        is_figure_derived=is_figure_derived,
    )

    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=request.pdf_id,
        row_id=request.row_id,
        column_name=request.column_name,
        cell_id=cell_id,
        source_mode=request.source_mode,
        proposal_state=proposal_state,
        support_label=support_label,
        proposed_value=proposed_value,
        rationale=rationale,
        calculation=calculation,
        needs_more_evidence=needs_more_evidence,
        primary_evidence_id=primary_evidence.evidence_id if primary_evidence else None,
        evidence_ids=[e.evidence_id for e in evidence_list],
    )

    return proposal, evidence_list


def _parse_proposal_state(state_str: str) -> ProposalState:
    """T058: Map raw string to ProposalState, defaulting to ERROR."""
    mapping = {
        "found": ProposalState.FOUND,
        "inferred": ProposalState.INFERRED,
        "unclear": ProposalState.UNCLEAR,
        "blocked": ProposalState.BLOCKED,
        "error": ProposalState.ERROR,
        "skipped": ProposalState.SKIPPED,
    }
    return mapping.get(state_str, ProposalState.ERROR)


# ---------------------------------------------------------------------------
# T057+T062+T063+T064 — Figure fallback execution
# ---------------------------------------------------------------------------


def extract_cell_with_figure_fallback(
    request: ExtractionRequest,
    provider: ProviderAdapter,
    doc: "ParsedDocument",
    run_id: str,
    all_chunks: list["RetrievalChunk"],
    retrieval_result: "RetrievalResult | None",
    artifacts_root: Path,
    column_description: str,
) -> tuple[ProposalRecord, list[EvidenceRecord]]:
    """
    T062: Attempt text extraction; trigger figure fallback when needed.

    Figure fallback is triggered only when:
    - Field is likely figure-derived (keyword check)
    - AND text extraction returned unclear/error
    """
    proposal, evidence_list = extract_cell(
        request=request,
        provider=provider,
        doc=doc,
        run_id=run_id,
        all_chunks=all_chunks,
    )

    # T062: Check figure fallback trigger
    if not should_trigger_figure_fallback(
        column_name=request.column_name,
        column_description=column_description,
        proposal_state=proposal.proposal_state,
        retrieval_result=retrieval_result,
    ):
        return proposal, evidence_list

    # T063: Build figure input packages
    figure_packages = build_figure_fallback_packages(doc, artifacts_root)
    if not figure_packages:
        return proposal, evidence_list

    # T063: Try first relevant figure
    for fig_pkg in figure_packages[:3]:  # cap at 3 figures per cell
        if not fig_pkg.crop_b64:
            continue
        try:
            from .ids import make_cell_id

            cell_id = make_cell_id(request.row_id, request.column_name)
            proposal_id = make_proposal_id(run_id, request.pdf_id, cell_id)

            schema_hint = VISION_EXTRACTION_SCHEMA
            vision_user_prompt = (
                f"{build_extraction_user_prompt(request)}\n\n"
                f"The attached image shows a figure/chart from the paper. "
                f"Caption: {fig_pkg.caption_text or 'not available'}\n"
                f"Nearby text: {fig_pkg.nearby_text or ''}"
            )
            raw_result = provider.complete_vision_json(
                system_prompt=build_extraction_system_prompt(verify_mode=request.verify_mode),
                user_prompt=vision_user_prompt,
                image_b64=fig_pkg.crop_b64,
                json_schema=schema_hint,
                max_tokens=512,
                temperature=0.0,
            )
            state_str = str(raw_result.get("proposal_state", "unclear")).lower()
            fig_state = _parse_proposal_state(state_str)
            if fig_state in (ProposalState.FOUND, ProposalState.INFERRED):
                # Build a figure-derived proposal
                proposed_value = str(raw_result.get("proposed_value", "")).strip() or None
                rationale = str(raw_result.get("rationale", "")).strip() or None
                calculation = str(raw_result.get("calculation", "")).strip() or None

                fig_evidence = _make_evidence_record(
                    run_id=run_id,
                    proposal_id=proposal_id,
                    pdf_id=request.pdf_id,
                    source_type=EvidenceSourceType.FIGURE_CROP,
                    page=fig_pkg.page_no,
                    quote_text=None,
                    anchor_confidence=0.6,
                    figure_ref=fig_pkg.figure_id,
                    caption_text=fig_pkg.caption_text,
                    crop_path=fig_pkg.crop_path,
                    full_page_path=fig_pkg.full_page_path,
                    ordinal=len(evidence_list),
                )
                evidence_list.append(fig_evidence)

                proposal = ProposalRecord(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    pdf_id=request.pdf_id,
                    row_id=request.row_id,
                    column_name=request.column_name,
                    cell_id=cell_id,
                    source_mode="vision",
                    proposal_state=fig_state,
                    support_label=SupportLabel.FIGURE_BASED_EVIDENCE,
                    proposed_value=proposed_value,
                    rationale=rationale,
                    calculation=calculation,
                    needs_more_evidence=False,
                    primary_evidence_id=fig_evidence.evidence_id,
                    evidence_ids=[e.evidence_id for e in evidence_list],
                )
                logger.info(
                    "Figure fallback succeeded for %s/%s: state=%s",
                    request.column_name, request.pdf_id, fig_state,
                )
                return proposal, evidence_list
        except NotImplementedError:
            logger.debug("Vision not supported by this provider; skipping figure fallback")
            break
        except (ProviderError, Exception) as exc:
            logger.warning("Figure fallback failed for figure %s: %s", fig_pkg.figure_id, exc)

    return proposal, evidence_list


# ---------------------------------------------------------------------------
# T057 — Full run extraction orchestrator
# ---------------------------------------------------------------------------


def run_extraction_for_run(
    run_id: str,
    artifacts: "RunArtifacts",
    config: Any,
    matched_pdfs: dict[str, str],  # pdf_id -> row_id
    parsed_docs: dict[str, "ParsedDocument"],
    schema_rows: list[dict[str, Any]],
    table_rows: list[dict[str, Any]],
    provider: ProviderAdapter | None,
    style_profiles: dict[str, "StyleProfile"],
    all_chunks_by_pdf: dict[str, list["RetrievalChunk"]],
    retrieval_results: dict[str, dict[str, "RetrievalResult"]],  # pdf_id -> {col -> result}
) -> dict[str, Any]:
    """
    T057: Per-target-cell extraction orchestrator.

    For each matched PDF × eligible cell:
    - Assembles the extraction request
    - Calls the provider (if available)
    - Persists proposal + evidence

    Returns a summary dict with counts.
    """
    if provider is None:
        logger.warning("No provider configured — extraction skipped; all cells will be 'skipped'")

    # Build row lookup by row_id
    row_by_id: dict[str, dict[str, Any]] = {}
    for row in table_rows:
        row_id = str(row.get("Title") or "")
        if row_id:
            row_by_id[row_id] = row

    verify_mode = getattr(config, "verify_mode", True)
    placeholders = set(getattr(config, "placeholders_treated_as_empty", ["", " "]))

    proposals_generated = 0
    skipped_no_provider = 0

    for pdf_id, row_id in matched_pdfs.items():
        doc = parsed_docs.get(pdf_id)
        if doc is None:
            logger.warning("No parsed doc for pdf_id=%s; skipping", pdf_id)
            continue

        row_data = row_by_id.get(row_id, {})
        chunks = all_chunks_by_pdf.get(pdf_id, [])

        for schema_row in schema_rows:
            column_name = str(schema_row.get("column_name", ""))
            column_description = str(schema_row.get("description", ""))
            if not column_name:
                continue

            # Check eligibility (T020 / T021)
            current_val = str(row_data.get(column_name, "")).strip()
            is_empty = current_val in placeholders or not current_val
            if not is_empty and not verify_mode:
                # Cell is filled and we're not in verify mode — skip
                from .ids import make_cell_id

                cell_id = make_cell_id(row_id, column_name)
                proposal_id = make_proposal_id(run_id, pdf_id, cell_id)
                skipped_proposal = ProposalRecord(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    pdf_id=pdf_id,
                    row_id=row_id,
                    column_name=column_name,
                    cell_id=cell_id,
                    source_mode="text",
                    proposal_state=ProposalState.SKIPPED,
                    support_label=SupportLabel.WEAK_EVIDENCE,
                    rationale="Cell already filled and verify mode is off.",
                )
                persist_proposal_and_evidence(artifacts, skipped_proposal, [])
                continue

            retrieval_result = (retrieval_results.get(pdf_id) or {}).get(column_name)
            style_profile = style_profiles.get(column_name)

            if provider is None:
                # No provider: emit skipped proposals
                from .ids import make_cell_id

                cell_id = make_cell_id(row_id, column_name)
                proposal_id = make_proposal_id(run_id, pdf_id, cell_id)
                skipped_proposal = ProposalRecord(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    pdf_id=pdf_id,
                    row_id=row_id,
                    column_name=column_name,
                    cell_id=cell_id,
                    source_mode="text",
                    proposal_state=ProposalState.SKIPPED,
                    support_label=SupportLabel.WEAK_EVIDENCE,
                    rationale="No LLM provider configured; extraction skipped.",
                )
                persist_proposal_and_evidence(artifacts, skipped_proposal, [])
                skipped_no_provider += 1
                continue

            request = build_extraction_request(
                run_id=run_id,
                pdf_id=pdf_id,
                row_id=row_id,
                row_data=row_data,
                column_name=column_name,
                column_description=column_description,
                style_profile=style_profile,
                retrieval_result=retrieval_result,
                all_chunks=chunks,
                verify_mode=verify_mode,
            )

            try:
                proposal, evidence_list = extract_cell_with_figure_fallback(
                    request=request,
                    provider=provider,
                    doc=doc,
                    run_id=run_id,
                    all_chunks=chunks,
                    retrieval_result=retrieval_result,
                    artifacts_root=artifacts.root,
                    column_description=column_description,
                )
            except Exception as exc:
                logger.error("Extraction failed for %s/%s/%s: %s", pdf_id, row_id, column_name, exc)
                from .ids import make_cell_id

                cell_id = make_cell_id(row_id, column_name)
                proposal_id = make_proposal_id(run_id, pdf_id, cell_id)
                proposal = ProposalRecord(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    pdf_id=pdf_id,
                    row_id=row_id,
                    column_name=column_name,
                    cell_id=cell_id,
                    source_mode="text",
                    proposal_state=ProposalState.ERROR,
                    support_label=SupportLabel.WEAK_EVIDENCE,
                    rationale=f"Unhandled extraction error: {exc}",
                )
                evidence_list = []

            persist_proposal_and_evidence(artifacts, proposal, evidence_list)
            proposals_generated += 1

    return {
        "proposals_generated": proposals_generated,
        "skipped_no_provider": skipped_no_provider,
    }
