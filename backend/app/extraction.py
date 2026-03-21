from __future__ import annotations

from .ids import make_evidence_id, make_proposal_id
from .models import (
    EvidenceRecord,
    EvidenceSourceType,
    HighlightBox,
    MatchOutcome,
    MatchRecord,
    ProposalRecord,
    ProposalState,
    ReviewDecisionType,
    SchemaColumn,
    StyleProfile,
    SupportLabel,
    WarningCategory,
    BlockType,
)
from .prompts import build_text_request, build_vision_request
from .provider import ProviderError, get_provider
from .retrieval import select_chunks


def map_support_label(state: ProposalState, support: str, figure_based: bool = False, weak_text: bool = False) -> SupportLabel:
    if state == ProposalState.BLOCKED:
        return SupportLabel.BLOCKED
    if state == ProposalState.UNCLEAR:
        return SupportLabel.UNCLEAR
    if state == ProposalState.ERROR:
        return SupportLabel.ERROR
    if figure_based:
        return SupportLabel.FIGURE
    if weak_text or support == "weak":
        return SupportLabel.WEAK_TEXT
    if support == "inferred" or state == ProposalState.INFERRED:
        return SupportLabel.INFERRED
    return SupportLabel.DIRECT


class ExtractionOrchestrator:
    def __init__(self, config):
        self.config = config
        self.provider = get_provider(config.provider)

    def extract_for_match(self, run_id: str, match: MatchRecord, row: dict, parsed_doc, eligibility_by_column: dict[str, object], schema: list[SchemaColumn], style_profiles: dict[str, StyleProfile], retrieval_chunks: list) -> tuple[list[ProposalRecord], list[EvidenceRecord]]:
        proposals: list[ProposalRecord] = []
        evidence_records: list[EvidenceRecord] = []
        for order, column in enumerate(schema, start=1):
            cell = eligibility_by_column.get(column.column_name)
            if not cell:
                continue
            proposal_id = make_proposal_id(run_id, match.pdf_id, cell.cell_id)
            if match.outcome != MatchOutcome.MATCHED:
                proposal = ProposalRecord(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    pdf_id=match.pdf_id,
                    row_id=row["row_id"],
                    row_index=row["row_index"],
                    column_name=column.column_name,
                    column_order=order,
                    cell_id=cell.cell_id,
                    proposal_state=ProposalState.BLOCKED,
                    support_label=SupportLabel.BLOCKED,
                    current_value=cell.current_value,
                    is_verify_target=cell.verify_target,
                    pdf_name=match.pdf_name,
                    warning_flags=[WarningCategory.AMBIGUOUS_MATCH] if match.outcome == MatchOutcome.AMBIGUOUS else [WarningCategory.DUPLICATE_ROW_CONFLICT] if match.outcome == MatchOutcome.DUPLICATE_ROW_CONFLICT else [],
                )
                proposals.append(proposal)
                continue
            if not cell.eligible:
                proposals.append(
                    ProposalRecord(
                        proposal_id=proposal_id,
                        run_id=run_id,
                        pdf_id=match.pdf_id,
                        row_id=row["row_id"],
                        row_index=row["row_index"],
                        column_name=column.column_name,
                        column_order=order,
                        cell_id=cell.cell_id,
                        proposal_state=ProposalState.SKIPPED,
                        support_label=SupportLabel.BLOCKED,
                        current_value=cell.current_value,
                        is_verify_target=cell.verify_target,
                        pdf_name=match.pdf_name,
                    )
                )
                continue
            selected_chunks = select_chunks(retrieval_chunks, column, row, self.config.retrieval)
            retrieval_context = [chunk.model_dump(mode="json") for chunk in selected_chunks]
            style_profile = style_profiles[column.column_name]
            request_payload = build_text_request(row, column, style_profile, retrieval_context, cell.current_value, self.config.review.verify_mode)
            use_vision = self._should_use_figure_fallback(column, selected_chunks, parsed_doc)
            if use_vision:
                request_payload = build_vision_request(request_payload, self._build_figure_package(parsed_doc))
            try:
                response = self.provider.invoke(request_payload)
                state = ProposalState(response.payload.get("proposal_state", "unclear"))
            except (ProviderError, ValueError):
                response = None
                state = ProposalState.ERROR
            warning_flags = []
            figure_based = False
            evidence_id = None
            if response and state not in {ProposalState.BLOCKED, ProposalState.SKIPPED, ProposalState.ERROR} and response.payload.get("proposed_value"):
                primary_chunk = selected_chunks[0] if selected_chunks else None
                quote_text = response.payload.get("evidence_quote", "")
                page = int(response.payload.get("page", primary_chunk.page if primary_chunk else 1))
                highlight = [HighlightBox(x=40, y=80, width=500, height=95)] if primary_chunk and primary_chunk.block_type != BlockType.CAPTION else []
                source_type = EvidenceSourceType.TEXT
                caption_text = ""
                crop_path = None
                full_page_path = None
                anchor_confidence = 0.9 if highlight else 0.4
                if use_vision and parsed_doc.figures:
                    figure_based = True
                    source_type = EvidenceSourceType.FIGURE
                    figure = parsed_doc.figures[0]
                    caption_text = figure.caption
                    crop_path = figure.crop_path
                    full_page_path = figure.full_page_path
                    highlight = []
                    anchor_confidence = 0.5
                    warning_flags.append(WarningCategory.FIGURE_DERIVED)
                elif not highlight:
                    warning_flags.append(WarningCategory.QUOTE_PAGE_FALLBACK)
                if anchor_confidence < 0.75:
                    warning_flags.append(WarningCategory.WEAK_EVIDENCE)
                evidence_id = make_evidence_id(proposal_id, page, source_type.value)
                evidence_records.append(
                    EvidenceRecord(
                        evidence_id=evidence_id,
                        proposal_id=proposal_id,
                        pdf_id=match.pdf_id,
                        source_type=source_type,
                        page=page,
                        quote_text=quote_text,
                        highlight=highlight,
                        figure_ref=parsed_doc.figures[0].figure_id if figure_based and parsed_doc.figures else None,
                        caption_text=caption_text,
                        crop_path=crop_path,
                        full_page_path=full_page_path or (parsed_doc.pages[page - 1].image_path if parsed_doc.pages else None),
                        anchor_confidence=anchor_confidence,
                    )
                )
            elif response and response.payload.get("evidence_quote"):
                warning_flags.append(WarningCategory.WEAK_EVIDENCE)
            support_label = map_support_label(state, response.payload.get("support", "weak") if response else "weak", figure_based=figure_based, weak_text=WarningCategory.WEAK_EVIDENCE in warning_flags)
            proposal = ProposalRecord(
                proposal_id=proposal_id,
                run_id=run_id,
                pdf_id=match.pdf_id,
                row_id=row["row_id"],
                row_index=row["row_index"],
                column_name=column.column_name,
                column_order=order,
                cell_id=cell.cell_id,
                source_mode="vision" if use_vision else "text",
                proposal_state=state,
                support_label=support_label,
                proposed_value=response.payload.get("proposed_value") if response else None,
                rationale=response.payload.get("rationale", "") if response else "Provider invocation failed.",
                calculation=response.payload.get("calculation", "") if response else "",
                needs_more_evidence=WarningCategory.WEAK_EVIDENCE in warning_flags,
                primary_evidence_id=evidence_id,
                evidence_ids=[evidence_id] if evidence_id else [],
                current_value=cell.current_value,
                is_verify_target=cell.verify_target,
                warning_flags=warning_flags,
                review_decision=ReviewDecisionType.NONE,
                pdf_name=match.pdf_name,
                support_sort_bucket=0 if state == ProposalState.FOUND else 1 if state == ProposalState.INFERRED else 2,
            )
            proposals.append(proposal)
        return proposals, evidence_records

    def _should_use_figure_fallback(self, column: SchemaColumn, selected_chunks: list, parsed_doc) -> bool:
        if not self.config.figure_fallback.enabled or not parsed_doc.figures:
            return False
        insufficient_text = not selected_chunks or max(chunk.score for chunk in selected_chunks) < 0.22
        keyword_hit = any(keyword in column.description.lower() or keyword in column.column_name.lower() for keyword in self.config.figure_fallback.trigger_keywords)
        return column.figure_likely or (insufficient_text and keyword_hit)

    def _build_figure_package(self, parsed_doc) -> dict:
        figure = parsed_doc.figures[0]
        return {
            "crop_path": figure.crop_path,
            "caption": figure.caption,
            "nearby_text": figure.nearby_text,
            "full_page_path": figure.full_page_path,
        }
