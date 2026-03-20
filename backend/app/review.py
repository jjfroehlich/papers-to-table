from __future__ import annotations

from .ids import make_review_decision_id
from .models import ProposalRecord, ReviewDecisionRecord, ReviewDecisionRequest, ReviewDecisionType


def apply_review_decision(proposal: ProposalRecord, request: ReviewDecisionRequest) -> tuple[ProposalRecord, ReviewDecisionRecord]:
    decision_id = make_review_decision_id(proposal.proposal_id, request.decision.value)
    updated = proposal.model_copy(deep=True)
    updated.review_decision = request.decision
    updated.review_decision_id = decision_id
    updated.reviewed_value = request.edited_value if request.decision == ReviewDecisionType.ACCEPT_EDIT else proposal.proposed_value
    record = ReviewDecisionRecord(
        review_decision_id=decision_id,
        proposal_id=proposal.proposal_id,
        run_id=proposal.run_id,
        cell_id=proposal.cell_id,
        decision=request.decision,
        edited_value=request.edited_value,
        reviewer_note=request.reviewer_note,
    )
    return updated, record
