"""
Batch 4 tests — T080

Tests covering:
- T072: Review decision recording
- T073: Audit history preservation
- T074: Bulk-accept (visible-subset semantics, only undecided)
- T068: Warning/status flag semantics
- T071: Review-asset serving (PDF, page images, figures)
- T075: Progress counters
- T076/T077: Run-summary and reviewer-summary recomputation
- T078: Summary recomputation endpoint
- T079: Export candidate selection (accepted-only)
- Partial-review behavior
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.artifacts import RunArtifacts
from backend.app.ids import make_cell_id, make_proposal_id, make_review_decision_id
from backend.app.main import app
from backend.app.review import (
    bulk_accept,
    get_export_candidates,
    get_progress,
    list_proposals,
    record_review_decision,
    get_proposal_decision_history,
)
from backend.app.schemas import (
    EvidenceRecord,
    EvidenceSourceType,
    ProposalRecord,
    ProposalState,
    ReviewDecision,
    ReviewDecisionRecord,
    SupportLabel,
    WarningStatusCategory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_artifacts(tmp_path: Path) -> RunArtifacts:
    return RunArtifacts.create(tmp_path / "out", "run_test")


def _write_proposal(
    artifacts: RunArtifacts,
    run_id: str = "run_test",
    pdf_id: str = "pdf_a",
    row_id: str = "row_1",
    column_name: str = "Method",
    proposed_value: str = "Transformer",
    proposal_state: ProposalState = ProposalState.FOUND,
    support_label: SupportLabel = SupportLabel.DIRECT_EVIDENCE,
    source_mode: str = "text",
    status_flags: list[WarningStatusCategory] | None = None,
) -> ProposalRecord:
    cell_id = make_cell_id(row_id, column_name)
    proposal_id = make_proposal_id(run_id, pdf_id, cell_id)
    record = ProposalRecord(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        cell_id=cell_id,
        source_mode=source_mode,
        proposal_state=proposal_state,
        support_label=support_label,
        proposed_value=proposed_value,
        status_flags=status_flags or [],
    )
    artifacts.append_jsonl("proposals/proposals.jsonl", record.model_dump(mode="json"))
    return record


def _write_evidence(
    artifacts: RunArtifacts,
    proposal_id: str,
    run_id: str = "run_test",
    pdf_id: str = "pdf_a",
    source_type: EvidenceSourceType = EvidenceSourceType.TEXT_QUOTE,
    page: int = 1,
    quote_text: str = "We use a Transformer architecture.",
    highlight: dict | None = None,
    crop_path: str | None = None,
) -> EvidenceRecord:
    from backend.app.ids import make_evidence_id
    evidence_id = make_evidence_id(run_id, proposal_id, 0)
    record = EvidenceRecord(
        evidence_id=evidence_id,
        proposal_id=proposal_id,
        pdf_id=pdf_id,
        source_type=source_type,
        page=page,
        quote_text=quote_text,
        highlight=highlight,
        crop_path=crop_path,
    )
    artifacts.append_jsonl("evidence/evidence.jsonl", record.model_dump(mode="json"))
    return record


def _wait_for_run(client: TestClient, run_id: str, max_polls: int = 120) -> None:
    """Poll until the run reaches a terminal state."""
    for _ in range(max_polls):
        time.sleep(0.5)
        s = client.get(f"/api/runs/{run_id}/summary").json()
        if s["status"] in {"completed", "completed_with_warnings", "failed"}:
            break


def _config_path(tmp_path: Path) -> Path:
    output_dir = tmp_path / "out"
    payload = {
        "paths": {
            "table_path": str(REPO_ROOT / "tests" / "fixtures" / "tables" / "literature_placeholder_fixture.csv"),
            "schema_path": str(REPO_ROOT / "tests" / "fixtures" / "schema" / "schema_fixture.csv"),
            "pdf_dir": str(REPO_ROOT / "tests" / "fixtures" / "papers"),
            "output_dir": str(output_dir),
        },
        "parser": {},
        "ocr_fallback": {},
        "matching": {},
        "style_profiles": {},
        "retrieval": {},
        "provider": {"provider_name": "lm_studio", "model_name": "test-model", "locality": "local"},
        "figure_fallback": {},
        "review": {},
        "export": {},
        "verify_mode": True,
        "placeholders_treated_as_empty": ["", " "],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(payload), encoding="utf-8")
    return config_file


# ---------------------------------------------------------------------------
# T072 + T073: Review decision recording and audit history
# ---------------------------------------------------------------------------


def test_record_decision_creates_record(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    proposal = _write_proposal(artifacts)
    rec = record_review_decision(
        artifacts=artifacts,
        run_id="run_test",
        proposal_id=proposal.proposal_id,
        cell_id=proposal.cell_id,
        decision=ReviewDecision.ACCEPT,
    )
    assert rec.decision == ReviewDecision.ACCEPT
    assert rec.proposal_id == proposal.proposal_id
    assert rec.run_id == "run_test"


def test_record_decision_preserves_history(tmp_path: Path) -> None:
    """T073: Multiple decisions for the same proposal are all preserved in the JSONL."""
    artifacts = _make_artifacts(tmp_path)
    proposal = _write_proposal(artifacts)

    record_review_decision(artifacts, "run_test", proposal.proposal_id, proposal.cell_id, ReviewDecision.ACCEPT)
    record_review_decision(artifacts, "run_test", proposal.proposal_id, proposal.cell_id, ReviewDecision.REJECT)

    history = get_proposal_decision_history(artifacts, proposal.proposal_id)
    assert len(history) == 2
    decisions_in_order = [row["decision"] for row in history]
    assert "accept" in decisions_in_order
    assert "reject" in decisions_in_order


def test_latest_decision_wins_for_progress(tmp_path: Path) -> None:
    """T073: The most recent decision determines progress counts, not all history."""
    artifacts = _make_artifacts(tmp_path)
    proposal = _write_proposal(artifacts)

    record_review_decision(artifacts, "run_test", proposal.proposal_id, proposal.cell_id, ReviewDecision.ACCEPT)
    record_review_decision(artifacts, "run_test", proposal.proposal_id, proposal.cell_id, ReviewDecision.REJECT)

    progress = get_progress(artifacts)
    assert progress.rejected == 1
    assert progress.accepted_as_is == 0


def test_accept_with_edit_stores_edited_value(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    proposal = _write_proposal(artifacts)
    rec = record_review_decision(
        artifacts,
        "run_test",
        proposal.proposal_id,
        proposal.cell_id,
        ReviewDecision.ACCEPT_WITH_EDIT,
        edited_value="CNN",
    )
    assert rec.edited_value == "CNN"


# ---------------------------------------------------------------------------
# T068: Warning/status flag semantics
# ---------------------------------------------------------------------------


def test_weak_evidence_flag_computed(tmp_path: Path) -> None:
    """Proposals with WEAK_EVIDENCE support_label get the WEAK_EVIDENCE status flag."""
    from backend.app.extraction import _compute_proposal_status_flags
    cell_id = make_cell_id("row_1", "Method")
    proposal_id = make_proposal_id("run_test", "pdf_a", cell_id)
    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id="run_test",
        pdf_id="pdf_a",
        row_id="row_1",
        column_name="Method",
        cell_id=cell_id,
        proposal_state=ProposalState.FOUND,
        support_label=SupportLabel.WEAK_EVIDENCE,
        proposed_value="CNN",
    )
    flags = _compute_proposal_status_flags(proposal, [])
    assert WarningStatusCategory.WEAK_EVIDENCE in flags


def test_figure_derived_flag_computed(tmp_path: Path) -> None:
    """Proposals with FIGURE_BASED_EVIDENCE support label get the FIGURE_DERIVED flag."""
    from backend.app.extraction import _compute_proposal_status_flags
    cell_id = make_cell_id("row_1", "Method")
    proposal_id = make_proposal_id("run_test", "pdf_a", cell_id)
    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id="run_test",
        pdf_id="pdf_a",
        row_id="row_1",
        column_name="Method",
        cell_id=cell_id,
        proposal_state=ProposalState.FOUND,
        support_label=SupportLabel.FIGURE_BASED_EVIDENCE,
        proposed_value="96%",
        source_mode="figure",
    )
    flags = _compute_proposal_status_flags(proposal, [])
    assert WarningStatusCategory.FIGURE_DERIVED in flags


def test_quote_page_fallback_flag_computed(tmp_path: Path) -> None:
    """Evidence with text quote but no highlight gets QUOTE_PAGE_FALLBACK flag."""
    from backend.app.extraction import _compute_proposal_status_flags
    from backend.app.schemas import EvidenceHighlight
    cell_id = make_cell_id("row_1", "Method")
    proposal_id = make_proposal_id("run_test", "pdf_a", cell_id)
    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id="run_test",
        pdf_id="pdf_a",
        row_id="row_1",
        column_name="Method",
        cell_id=cell_id,
        proposal_state=ProposalState.FOUND,
        support_label=SupportLabel.INFERRED_FROM_EVIDENCE,
        proposed_value="Transformer",
    )
    from backend.app.ids import make_evidence_id
    evidence = EvidenceRecord(
        evidence_id=make_evidence_id("run_test", proposal_id, 0),
        proposal_id=proposal_id,
        pdf_id="pdf_a",
        source_type=EvidenceSourceType.TEXT_QUOTE,
        page=2,
        quote_text="We use transformers",
        highlight=None,
    )
    flags = _compute_proposal_status_flags(proposal, [evidence])
    assert WarningStatusCategory.QUOTE_PAGE_FALLBACK in flags


def test_no_spurious_flags_with_highlight(tmp_path: Path) -> None:
    """Proposals with highlight evidence do not get QUOTE_PAGE_FALLBACK."""
    from backend.app.extraction import _compute_proposal_status_flags
    from backend.app.schemas import EvidenceHighlight
    cell_id = make_cell_id("row_1", "Method")
    proposal_id = make_proposal_id("run_test", "pdf_a", cell_id)
    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id="run_test",
        pdf_id="pdf_a",
        row_id="row_1",
        column_name="Method",
        cell_id=cell_id,
        proposal_state=ProposalState.FOUND,
        support_label=SupportLabel.DIRECT_EVIDENCE,
        proposed_value="Transformer",
    )
    from backend.app.ids import make_evidence_id
    evidence = EvidenceRecord(
        evidence_id=make_evidence_id("run_test", proposal_id, 0),
        proposal_id=proposal_id,
        pdf_id="pdf_a",
        source_type=EvidenceSourceType.TEXT_HIGHLIGHT,
        page=2,
        quote_text="transformers",
        highlight=EvidenceHighlight(x0=0.0, y0=0.0, x1=100.0, y1=20.0),
    )
    flags = _compute_proposal_status_flags(proposal, [evidence])
    assert WarningStatusCategory.QUOTE_PAGE_FALLBACK not in flags
    assert WarningStatusCategory.WEAK_EVIDENCE not in flags


# ---------------------------------------------------------------------------
# T069: Proposal list filtering
# ---------------------------------------------------------------------------


def test_list_proposals_no_filter(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    _write_proposal(artifacts, row_id="row_1", column_name="Method")
    _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")
    items = list_proposals(artifacts)
    assert len(items) == 2


def test_list_proposals_filter_by_column(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    _write_proposal(artifacts, row_id="row_1", column_name="Method")
    _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")
    items = list_proposals(artifacts, column_name="Method")
    assert len(items) == 1
    assert items[0].column_name == "Method"


def test_list_proposals_filter_by_decision_status(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts, row_id="row_1", column_name="Method")
    p2 = _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.ACCEPT)

    undecided = list_proposals(artifacts, decision_status=ReviewDecision.UNDECIDED)
    accepted = list_proposals(artifacts, decision_status=ReviewDecision.ACCEPT)
    assert len(undecided) == 1
    assert undecided[0].proposal_id == p2.proposal_id
    assert len(accepted) == 1
    assert accepted[0].proposal_id == p1.proposal_id


def test_list_proposals_filter_by_figure_evidence(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    _write_proposal(
        artifacts,
        row_id="row_1",
        column_name="Method",
        status_flags=[WarningStatusCategory.FIGURE_DERIVED],
    )
    _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")

    fig_only = list_proposals(artifacts, has_figure_evidence=True)
    non_fig = list_proposals(artifacts, has_figure_evidence=False)
    assert len(fig_only) == 1
    assert len(non_fig) == 1


# ---------------------------------------------------------------------------
# T074: Bulk-accept (visible-subset, undecided only)
# ---------------------------------------------------------------------------


def test_bulk_accept_all_undecided(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts, row_id="row_1", column_name="Method")
    p2 = _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")

    decisions = bulk_accept(artifacts, "run_test")
    assert len(decisions) == 2
    progress = get_progress(artifacts)
    assert progress.accepted_as_is == 2
    assert progress.pending == 0


def test_bulk_accept_only_undecided(tmp_path: Path) -> None:
    """Bulk-accept must not change already-decided proposals."""
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts, row_id="row_1", column_name="Method")
    p2 = _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.REJECT)

    decisions = bulk_accept(artifacts, "run_test")
    # Only p2 (undecided) should be bulk-accepted
    assert len(decisions) == 1
    assert decisions[0].proposal_id == p2.proposal_id

    progress = get_progress(artifacts)
    assert progress.rejected == 1
    assert progress.accepted_as_is == 1


def test_bulk_accept_with_column_filter(tmp_path: Path) -> None:
    """Bulk-accept with column filter only affects the visible subset."""
    artifacts = _make_artifacts(tmp_path)
    _write_proposal(artifacts, row_id="row_1", column_name="Method")
    _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")

    decisions = bulk_accept(artifacts, "run_test", column_name="Method")
    assert len(decisions) == 1
    assert decisions[0].cell_id == make_cell_id("row_1", "Method")

    progress = get_progress(artifacts)
    assert progress.accepted_as_is == 1
    assert progress.pending == 1


# ---------------------------------------------------------------------------
# T075: Progress counters
# ---------------------------------------------------------------------------


def test_progress_with_no_decisions(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    _write_proposal(artifacts)
    _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")
    progress = get_progress(artifacts)
    assert progress.total == 2
    assert progress.pending == 2
    assert progress.accepted_as_is == 0
    assert progress.rejected == 0


def test_progress_partial_review(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts, row_id="row_1", column_name="Method")
    p2 = _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.ACCEPT)
    record_review_decision(artifacts, "run_test", p2.proposal_id, p2.cell_id, ReviewDecision.REJECT)

    progress = get_progress(artifacts)
    assert progress.total == 2
    assert progress.accepted_as_is == 1
    assert progress.rejected == 1
    assert progress.pending == 0


# ---------------------------------------------------------------------------
# T076 + T077 + T078: Summary recomputation
# ---------------------------------------------------------------------------


def test_recompute_summaries_counts(tmp_path: Path) -> None:
    """T076/T077/T078: Summaries are derivable and reflect actual decision state."""
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts, row_id="row_1", column_name="Method")
    p2 = _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.ACCEPT)

    run_summary, reviewer_summary = artifacts.recompute_summaries("run_test")

    assert run_summary["counts"]["proposals_generated"] == 2
    assert run_summary["counts"]["accepted_as_is"] == 1
    assert run_summary["counts"]["pending"] == 1
    assert reviewer_summary["counts"]["proposals_generated"] == 2
    assert reviewer_summary["counts"]["accepted_as_is"] == 1


def test_recompute_summaries_loads_from_artifacts(tmp_path: Path) -> None:
    """T078: After writing proposals + decisions, recompute is idempotent from artifacts."""
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts)
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.REJECT)

    # First recompute
    run_summary1, _ = artifacts.recompute_summaries("run_test")
    # Second recompute (idempotent)
    run_summary2, _ = artifacts.recompute_summaries("run_test")

    assert run_summary1["counts"]["rejected"] == run_summary2["counts"]["rejected"] == 1


def test_recompute_summaries_run_status_flags(tmp_path: Path) -> None:
    """T068+T076: Run-level NO_REVIEWED_VERIFIED_CELLS flag appears when nothing accepted."""
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts)
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.REJECT)

    run_summary, _ = artifacts.recompute_summaries("run_test")
    assert "no_reviewed_verified_cells" in run_summary["run_status_flags"]


def test_recompute_summaries_no_flag_when_accepted(tmp_path: Path) -> None:
    """T068+T076: NO_REVIEWED_VERIFIED_CELLS is absent when at least one proposal accepted."""
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts)
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.ACCEPT)

    run_summary, _ = artifacts.recompute_summaries("run_test")
    assert "no_reviewed_verified_cells" not in run_summary["run_status_flags"]


# ---------------------------------------------------------------------------
# T079: Export candidates (accepted-only by construction)
# ---------------------------------------------------------------------------


def test_export_candidates_excludes_unreviewed(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts, row_id="row_1", column_name="Method", proposed_value="Transformer")
    _write_proposal(artifacts, pdf_id="pdf_b", row_id="row_2", column_name="Dataset")

    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.ACCEPT)

    candidates = get_export_candidates(artifacts)
    assert len(candidates) == 1
    assert candidates[0].proposal_id == p1.proposal_id
    assert candidates[0].accepted_value == "Transformer"


def test_export_candidates_excludes_rejected(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts)
    record_review_decision(artifacts, "run_test", p1.proposal_id, p1.cell_id, ReviewDecision.REJECT)
    candidates = get_export_candidates(artifacts)
    assert len(candidates) == 0


def test_export_candidates_accept_with_edit_uses_edited_value(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    p1 = _write_proposal(artifacts, proposed_value="CNN")
    record_review_decision(
        artifacts, "run_test", p1.proposal_id, p1.cell_id,
        ReviewDecision.ACCEPT_WITH_EDIT, edited_value="ResNet-50"
    )
    candidates = get_export_candidates(artifacts)
    assert len(candidates) == 1
    assert candidates[0].accepted_value == "ResNet-50"


def test_export_candidates_empty_when_nothing_accepted(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    _write_proposal(artifacts)  # undecided
    candidates = get_export_candidates(artifacts)
    assert len(candidates) == 0


# ---------------------------------------------------------------------------
# T071: Review-asset serving endpoints
# ---------------------------------------------------------------------------


def test_serve_pdf_not_found_returns_404(tmp_path: Path) -> None:
    client = TestClient(app)
    config_path = _config_path(tmp_path)

    create_resp = client.post("/api/runs", json={"config_path": str(config_path)})
    assert create_resp.status_code == 200
    run_id = create_resp.json()["run_id"]
    _wait_for_run(client, run_id)

    response = client.get(f"/api/runs/{run_id}/assets/pdf/nonexistent_pdf_id")
    assert response.status_code == 404


def test_serve_page_image_not_found_returns_404(tmp_path: Path) -> None:
    client = TestClient(app)
    config_path = _config_path(tmp_path)

    create_resp = client.post("/api/runs", json={"config_path": str(config_path)})
    run_id = create_resp.json()["run_id"]
    _wait_for_run(client, run_id)

    response = client.get(f"/api/runs/{run_id}/assets/pages/nonexistent_pdf/1")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Batch 4 API integration tests (endpoints on a live run)
# ---------------------------------------------------------------------------


def test_api_proposals_and_progress(tmp_path: Path) -> None:
    """Integration: proposal-list, detail, decision, progress, and summary endpoints work."""
    client = TestClient(app)
    config_path = _config_path(tmp_path)

    create_resp = client.post("/api/runs", json={"config_path": str(config_path)})
    assert create_resp.status_code == 200
    run_id = create_resp.json()["run_id"]
    _wait_for_run(client, run_id)

    # Proposal list
    proposals_resp = client.get(f"/api/runs/{run_id}/proposals")
    assert proposals_resp.status_code == 200
    proposals = proposals_resp.json()
    assert isinstance(proposals, list)

    # Progress endpoint
    progress_resp = client.get(f"/api/runs/{run_id}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert "total" in progress
    assert "pending" in progress

    # Run summary full
    run_summary_resp = client.get(f"/api/runs/{run_id}/summaries/run")
    assert run_summary_resp.status_code == 200
    run_summary = run_summary_resp.json()
    assert "counts" in run_summary

    # Reviewer summary
    reviewer_resp = client.get(f"/api/runs/{run_id}/summaries/reviewer")
    assert reviewer_resp.status_code == 200

    # Recompute summaries
    recompute_resp = client.post(f"/api/runs/{run_id}/summaries/recompute")
    assert recompute_resp.status_code == 200
    recomputed = recompute_resp.json()
    assert "run_summary" in recomputed
    assert "reviewer_summary" in recomputed

    # Export candidates (should be empty since no decisions made)
    candidates_resp = client.get(f"/api/runs/{run_id}/export-candidates")
    assert candidates_resp.status_code == 200
    assert candidates_resp.json() == []

    # If there are proposals, test detail, decision, and bulk-accept
    if proposals:
        pid = proposals[0]["proposal_id"]

        detail_resp = client.get(f"/api/runs/{run_id}/proposals/{pid}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["proposal_id"] == pid
        assert "evidence" in detail
        assert "latest_decision" in detail
        assert detail["latest_decision"] == "undecided"

        # Record a decision
        decision_resp = client.post(
            f"/api/runs/{run_id}/proposals/{pid}/decision",
            json={"decision": "accept"},
        )
        assert decision_resp.status_code == 200
        assert decision_resp.json()["decision"] == "accept"

        # Progress should reflect the decision
        progress2 = client.get(f"/api/runs/{run_id}/progress").json()
        assert progress2["accepted_as_is"] >= 1

        # Export candidates should now include the accepted proposal
        candidates2 = client.get(f"/api/runs/{run_id}/export-candidates").json()
        assert any(c["proposal_id"] == pid for c in candidates2)

        # Evidence endpoint
        evidence_resp = client.get(f"/api/runs/{run_id}/proposals/{pid}/evidence")
        assert evidence_resp.status_code == 200


def test_bulk_accept_endpoint(tmp_path: Path) -> None:
    """Integration: bulk-accept endpoint works on a completed run."""
    client = TestClient(app)
    config_path = _config_path(tmp_path)

    create_resp = client.post("/api/runs", json={"config_path": str(config_path)})
    run_id = create_resp.json()["run_id"]
    _wait_for_run(client, run_id)
    bulk_resp = client.post(f"/api/runs/{run_id}/proposals/bulk-accept", json={})
    assert bulk_resp.status_code == 200
    bulk_decisions = bulk_resp.json()
    assert isinstance(bulk_decisions, list)

    progress = client.get(f"/api/runs/{run_id}/progress").json()
    # pending should be 0 after bulk accepting everything
    assert progress["pending"] == 0


def test_proposal_not_found_returns_404(tmp_path: Path) -> None:
    """Detail and decision endpoints return 404 for unknown proposal."""
    client = TestClient(app)
    config_path = _config_path(tmp_path)

    create_resp = client.post("/api/runs", json={"config_path": str(config_path)})
    run_id = create_resp.json()["run_id"]
    _wait_for_run(client, run_id)

    resp = client.get(f"/api/runs/{run_id}/proposals/proposal_doesnotexist")
    assert resp.status_code == 404

    resp2 = client.post(
        f"/api/runs/{run_id}/proposals/proposal_doesnotexist/decision",
        json={"decision": "accept"},
    )
    assert resp2.status_code == 404
