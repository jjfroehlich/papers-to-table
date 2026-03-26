from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .runner import RunStore, RunnerError
from .schemas import (
    BulkAcceptRequest,
    ErrorResponse,
    ExportCandidate,
    ProposalDetail,
    ProposalListItem,
    ProposalProgress,
    RecordDecisionRequest,
    ReviewDecision,
    ReviewDecisionRecord,
    RunCreateRequest,
    RunCreateResponse,
    RunRecord,
    RunSummary,
)

app = FastAPI(title="Paper Table Agent API", version="0.4.0")
run_store = RunStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/runs", response_model=RunCreateResponse, responses={400: {"model": ErrorResponse}})
def create_run(payload: RunCreateRequest) -> RunCreateResponse:
    try:
        return run_store.create_run(payload.config_path)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/runs", response_model=list[RunRecord])
def list_runs() -> list[RunRecord]:
    return run_store.list_runs()


@app.get("/api/runs/{run_id}/summary", response_model=RunSummary, responses={404: {"model": ErrorResponse}})
def get_run_summary(run_id: str) -> RunSummary:
    try:
        return run_store.get_summary(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/runs/{run_id}/config-snapshot", responses={404: {"model": ErrorResponse}})
def get_config_snapshot(run_id: str) -> dict:
    try:
        return run_store.read_artifact_json(run_id, "config.snapshot.json")
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/runs/{run_id}/input-summary", responses={404: {"model": ErrorResponse}})
def get_input_summary(run_id: str) -> dict:
    try:
        return run_store.read_artifact_json(run_id, "inputs/input_summary.json")
    except Exception as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/runs/{run_id}/matching/summary", responses={404: {"model": ErrorResponse}})
def get_matching_summary(run_id: str) -> dict:
    """Return the matching summary (total, matched, unresolved) for a run."""
    try:
        return run_store.get_matching_summary(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/runs/{run_id}/matching/unresolved", responses={404: {"model": ErrorResponse}})
def get_matching_unresolved(run_id: str) -> list[dict]:
    """Return unmatched, ambiguous, and duplicate-row-conflict records for a run."""
    try:
        return run_store.get_matching_unresolved(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


# ---------------------------------------------------------------------------
# Batch 4 — Proposal list/filter, detail, review decisions, assets, summaries
# ---------------------------------------------------------------------------


@app.get(
    "/api/runs/{run_id}/proposals",
    response_model=list[ProposalListItem],
    responses={404: {"model": ErrorResponse}},
)
def list_proposals(
    run_id: str,
    row_id: str | None = Query(default=None),
    column_name: str | None = Query(default=None),
    pdf_id: str | None = Query(default=None),
    has_figure_evidence: bool | None = Query(default=None),
    has_ambiguous_match: bool | None = Query(default=None),
    decision_status: ReviewDecision | None = Query(default=None),
) -> list[ProposalListItem]:
    """T069: Return proposals with optional filters and latest decision status."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    from .review import list_proposals as _list_proposals
    return _list_proposals(
        artifacts,
        row_id=row_id,
        column_name=column_name,
        pdf_id=pdf_id,
        has_figure_evidence=has_figure_evidence,
        has_ambiguous_match=has_ambiguous_match,
        decision_status=decision_status,
    )


@app.get(
    "/api/runs/{run_id}/proposals/{proposal_id}",
    response_model=ProposalDetail,
    responses={404: {"model": ErrorResponse}},
)
def get_proposal_detail(run_id: str, proposal_id: str) -> ProposalDetail:
    """T070: Return full proposal detail including row context, evidence, and latest decision."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    proposal_row = artifacts.find_proposal(proposal_id)
    if proposal_row is None:
        raise HTTPException(status_code=404, detail=f"Proposal not found: {proposal_id}")

    # Load evidence records for this proposal
    evidence_rows = [
        row for row in artifacts.read_jsonl("evidence/evidence.jsonl")
        if row.get("proposal_id") == proposal_id
    ]

    # Load row context and column definition from input details
    row_context: dict = {}
    column_definition: dict = {}
    current_cell_value: str | None = None
    try:
        input_details = artifacts.read_json("inputs/input_details.json")
        row_id = proposal_row.get("row_id", "")
        col_name = proposal_row.get("column_name", "")
        for row in input_details.get("table_rows", []):
            if row.get("row_id") == row_id:
                row_context = row
                current_cell_value = str(row.get(col_name, "")) or None
                break
        for schema_row in input_details.get("schema_rows", []):
            if schema_row.get("column_name") == col_name:
                column_definition = schema_row
                break
    except (FileNotFoundError, KeyError):
        pass

    # Load latest decision
    from .review import _load_latest_decisions, get_proposal_decision_history
    latest_decisions = _load_latest_decisions(artifacts)
    pid = proposal_row.get("proposal_id", "")
    decision_rec = latest_decisions.get(pid)
    latest_decision = decision_rec.decision if decision_rec else ReviewDecision.UNDECIDED
    decision_record_dict = decision_rec.model_dump(mode="json") if decision_rec else None

    flags_raw = proposal_row.get("status_flags", [])
    from .schemas import WarningStatusCategory
    flags = [WarningStatusCategory(f) for f in flags_raw if f in WarningStatusCategory._value2member_map_]

    return ProposalDetail(
        proposal_id=pid,
        run_id=proposal_row.get("run_id", ""),
        pdf_id=proposal_row.get("pdf_id", ""),
        row_id=proposal_row.get("row_id", ""),
        column_name=proposal_row.get("column_name", ""),
        cell_id=proposal_row.get("cell_id", ""),
        source_mode=proposal_row.get("source_mode", "text"),
        proposal_state=proposal_row.get("proposal_state", "unclear"),
        support_label=proposal_row.get("support_label", "weak_evidence"),
        proposed_value=proposal_row.get("proposed_value"),
        rationale=proposal_row.get("rationale"),
        calculation=proposal_row.get("calculation"),
        needs_more_evidence=proposal_row.get("needs_more_evidence", False),
        status_flags=flags,
        row_context=row_context,
        column_definition=column_definition,
        current_cell_value=current_cell_value,
        evidence=evidence_rows,
        latest_decision=latest_decision,
        latest_decision_record=decision_record_dict,
    )


@app.post(
    "/api/runs/{run_id}/proposals/{proposal_id}/decision",
    response_model=ReviewDecisionRecord,
    responses={404: {"model": ErrorResponse}},
)
def record_decision(
    run_id: str,
    proposal_id: str,
    payload: RecordDecisionRequest,
) -> ReviewDecisionRecord:
    """T072 + T073: Record a review decision, preserving full audit history."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    proposal_row = artifacts.find_proposal(proposal_id)
    if proposal_row is None:
        raise HTTPException(status_code=404, detail=f"Proposal not found: {proposal_id}")

    from .review import record_review_decision
    return record_review_decision(
        artifacts=artifacts,
        run_id=run_id,
        proposal_id=proposal_id,
        cell_id=proposal_row.get("cell_id", ""),
        decision=payload.decision,
        edited_value=payload.edited_value,
    )


@app.post(
    "/api/runs/{run_id}/proposals/bulk-accept",
    response_model=list[ReviewDecisionRecord],
    responses={404: {"model": ErrorResponse}},
)
def bulk_accept(run_id: str, payload: BulkAcceptRequest) -> list[ReviewDecisionRecord]:
    """T074: Bulk-accept all undecided proposals in the currently visible filtered subset."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    from .review import bulk_accept as _bulk_accept
    return _bulk_accept(
        artifacts=artifacts,
        run_id=run_id,
        row_id=payload.row_id,
        column_name=payload.column_name,
        pdf_id=payload.pdf_id,
    )


@app.get(
    "/api/runs/{run_id}/progress",
    response_model=ProposalProgress,
    responses={404: {"model": ErrorResponse}},
)
def get_progress(run_id: str) -> ProposalProgress:
    """T075: Return progress counters and decision-breakdown aggregation."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    from .review import get_progress as _get_progress
    return _get_progress(artifacts)


@app.get("/api/runs/{run_id}/summaries/run", responses={404: {"model": ErrorResponse}})
def get_run_summary_full(run_id: str) -> dict:
    """T076: Return the full run summary including counts and matching stats."""
    try:
        artifacts = run_store.get_artifacts(run_id)
        return artifacts.read_json("summaries/run_summary.json")
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Run summary not yet available")


@app.get("/api/runs/{run_id}/summaries/reviewer", responses={404: {"model": ErrorResponse}})
def get_reviewer_summary(run_id: str) -> dict:
    """T077: Return the reviewer-outcome summary."""
    try:
        artifacts = run_store.get_artifacts(run_id)
        return artifacts.read_json("summaries/reviewer_summary.json")
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Reviewer summary not yet available")


@app.post("/api/runs/{run_id}/summaries/recompute", responses={404: {"model": ErrorResponse}})
def recompute_summaries(run_id: str) -> dict:
    """T078: Recompute run and reviewer summaries from artifact files."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    run_summary, reviewer_summary = artifacts.recompute_summaries(run_id=run_id)
    return {"run_summary": run_summary, "reviewer_summary": reviewer_summary}


@app.get(
    "/api/runs/{run_id}/export-candidates",
    response_model=list[ExportCandidate],
    responses={404: {"model": ErrorResponse}},
)
def get_export_candidates(run_id: str) -> list[ExportCandidate]:
    """T079: Return only explicitly accepted proposals for export."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    from .review import get_export_candidates as _get_export_candidates
    return _get_export_candidates(artifacts)


# ---------------------------------------------------------------------------
# T071 — Review-asset serving endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/api/runs/{run_id}/assets/pdf/{pdf_id}",
    responses={404: {"model": ErrorResponse}},
)
def serve_pdf(run_id: str, pdf_id: str) -> FileResponse:
    """T071: Serve the original PDF for a given pdf_id for the PDF.js viewer."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    # Find the source PDF path from the parsed document artifact
    parsed_doc_path = artifacts.root / "parsed" / pdf_id / "parsed_document.json"
    if parsed_doc_path.exists():
        try:
            with parsed_doc_path.open("r", encoding="utf-8") as fh:
                doc = json.load(fh)
            source_path = doc.get("source_path")
            if source_path and Path(source_path).is_file():
                return FileResponse(
                    path=str(source_path),
                    media_type="application/pdf",
                    filename=f"{pdf_id}.pdf",
                )
        except Exception:
            pass

    # Fallback: look in pdf_dir from config snapshot
    try:
        snapshot = artifacts.read_json("config.snapshot.json")
        pdf_dir = snapshot.get("paths", {}).get("pdf_dir", "")
        if pdf_dir:
            candidate = Path(pdf_dir) / f"{pdf_id}.pdf"
            if candidate.is_file():
                return FileResponse(
                    path=str(candidate),
                    media_type="application/pdf",
                    filename=f"{pdf_id}.pdf",
                )
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"PDF not found for pdf_id: {pdf_id}")


@app.get(
    "/api/runs/{run_id}/assets/pages/{pdf_id}/{page_no}",
    responses={404: {"model": ErrorResponse}},
)
def serve_page_image(run_id: str, pdf_id: str, page_no: int) -> FileResponse:
    """T071: Serve a rendered page image (PNG) for the review evidence viewer."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    page_path = artifacts.root / "parsed" / pdf_id / "pages" / f"page_{page_no:04d}.png"
    if not page_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Page image not found: pdf_id={pdf_id}, page={page_no}",
        )
    return FileResponse(path=str(page_path), media_type="image/png")


@app.get(
    "/api/runs/{run_id}/assets/figures/{evidence_id}",
    responses={404: {"model": ErrorResponse}},
)
def serve_figure_crop(run_id: str, evidence_id: str) -> FileResponse:
    """T071: Serve a figure crop image by evidence_id."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    evidence_row = artifacts.find_evidence(evidence_id)
    if evidence_row is None:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {evidence_id}")

    crop_path = evidence_row.get("crop_path")
    if crop_path and Path(crop_path).is_file():
        return FileResponse(path=str(crop_path), media_type="image/png")

    full_page_path = evidence_row.get("full_page_path")
    if full_page_path and Path(full_page_path).is_file():
        return FileResponse(path=str(full_page_path), media_type="image/png")

    raise HTTPException(status_code=404, detail=f"Figure image not found for evidence_id: {evidence_id}")


@app.get(
    "/api/runs/{run_id}/proposals/{proposal_id}/evidence",
    responses={404: {"model": ErrorResponse}},
)
def get_proposal_evidence(run_id: str, proposal_id: str) -> list[dict]:
    """T071: Return evidence metadata records for a proposal."""
    try:
        artifacts = run_store.get_artifacts(run_id)
    except RunnerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return [
        row for row in artifacts.read_jsonl("evidence/evidence.jsonl")
        if row.get("proposal_id") == proposal_id
    ]

