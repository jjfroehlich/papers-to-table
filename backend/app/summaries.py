from __future__ import annotations

from .models import (
    MatchOutcome,
    MatchRecord,
    ProposalRecord,
    ProviderLocality,
    ReviewDecisionType,
    ReviewerColumnSummary,
    ReviewerSummary,
    RunRecord,
    RunSummary,
)


def build_run_summary(run: RunRecord, matches: list[MatchRecord], proposals: list[ProposalRecord], changed_cells_exported: int) -> RunSummary:
    accepted = sum(1 for proposal in proposals if proposal.review_decision == ReviewDecisionType.ACCEPT)
    accepted_edit = sum(1 for proposal in proposals if proposal.review_decision == ReviewDecisionType.ACCEPT_EDIT)
    rejected = sum(1 for proposal in proposals if proposal.review_decision == ReviewDecisionType.REJECT)
    reviewed = accepted + accepted_edit + rejected
    return RunSummary(
        run_id=run.run_id,
        status=run.status,
        pdfs_processed=len(matches),
        matched_pdfs=sum(1 for match in matches if match.outcome == MatchOutcome.MATCHED),
        unmatched_pdfs=sum(1 for match in matches if match.outcome == MatchOutcome.UNMATCHED),
        ambiguous_pdfs=sum(1 for match in matches if match.outcome == MatchOutcome.AMBIGUOUS),
        duplicate_conflict_pdfs=sum(1 for match in matches if match.outcome == MatchOutcome.DUPLICATE_ROW_CONFLICT),
        proposals_generated=len(proposals),
        reviewed_proposals=reviewed,
        accepted_as_is=accepted,
        accepted_with_edit=accepted_edit,
        rejected=rejected,
        pending=len(proposals) - reviewed,
        changed_cells_exported=changed_cells_exported,
        verify_mode=run.verify_mode,
        provider_name=run.provider_name,
        provider_model=run.provider_model,
        provider_locality=run.provider_locality,
        warnings=[warning.value for warning in run.warnings],
    )


def build_reviewer_summary(run: RunRecord, matches: list[MatchRecord], proposals: list[ProposalRecord], changed_cells_exported: int) -> ReviewerSummary:
    accepted = [proposal for proposal in proposals if proposal.review_decision == ReviewDecisionType.ACCEPT]
    accepted_edit = [proposal for proposal in proposals if proposal.review_decision == ReviewDecisionType.ACCEPT_EDIT]
    rejected = [proposal for proposal in proposals if proposal.review_decision == ReviewDecisionType.REJECT]
    reviewed = accepted + accepted_edit + rejected
    verify_targets = [proposal for proposal in proposals if proposal.is_verify_target]
    reviewed_verify_targets = [proposal for proposal in reviewed if proposal.is_verify_target]
    with_evidence = [proposal for proposal in proposals if proposal.evidence_ids]
    anchorable = [proposal for proposal in proposals if proposal.primary_evidence_id and "Weak" not in proposal.support_label.value]
    per_column: list[ReviewerColumnSummary] = []
    for column_name in sorted({proposal.column_name for proposal in proposals}):
        column_verify = [proposal for proposal in verify_targets if proposal.column_name == column_name]
        column_reviewed = [proposal for proposal in reviewed_verify_targets if proposal.column_name == column_name]
        column_items = [proposal for proposal in proposals if proposal.column_name == column_name]
        evidence_cov = len([proposal for proposal in column_items if proposal.evidence_ids]) / len(column_items) if column_items else 0.0
        anchor_cov = len([proposal for proposal in column_items if proposal.primary_evidence_id and "Weak" not in proposal.support_label.value]) / len(column_items) if column_items else 0.0
        per_column.append(
            ReviewerColumnSummary(
                column_name=column_name,
                reviewed_verified_cell_count=len(column_reviewed),
                accepted_as_is=sum(1 for proposal in column_reviewed if proposal.review_decision == ReviewDecisionType.ACCEPT),
                accepted_with_edit=sum(1 for proposal in column_reviewed if proposal.review_decision == ReviewDecisionType.ACCEPT_EDIT),
                rejected=sum(1 for proposal in column_reviewed if proposal.review_decision == ReviewDecisionType.REJECT),
                evidence_coverage=round(evidence_cov, 4),
                anchorable_evidence_rate=round(anchor_cov, 4),
            )
        )
    warnings: list[str] = []
    if run.verify_mode and not reviewed_verify_targets:
        warnings.append("No reviewed verified cells were available for reviewer-outcome interpretation.")
    return ReviewerSummary(
        run_id=run.run_id,
        proposals_generated=len(proposals),
        reviewed_proposals=len(reviewed),
        accepted_as_is=len(accepted),
        accepted_with_edit=len(accepted_edit),
        rejected=len(rejected),
        pending=len(proposals) - len(reviewed),
        changed_cells_exported=changed_cells_exported,
        matched_pdfs=sum(1 for match in matches if match.outcome == MatchOutcome.MATCHED),
        unmatched_pdfs=sum(1 for match in matches if match.outcome == MatchOutcome.UNMATCHED),
        ambiguous_pdfs=sum(1 for match in matches if match.outcome == MatchOutcome.AMBIGUOUS),
        verify_mode=run.verify_mode,
        provider_name=run.provider_name,
        provider_model=run.provider_model,
        provider_locality=run.provider_locality,
        reviewed_verified_cell_count=len(reviewed_verify_targets),
        proposal_coverage=round(len(reviewed) / len(proposals), 4) if proposals else 0.0,
        evidence_coverage=round(len(with_evidence) / len(proposals), 4) if proposals else 0.0,
        anchorable_evidence_rate=round(len(anchorable) / len(proposals), 4) if proposals else 0.0,
        per_column=per_column,
        warnings=warnings,
    )
