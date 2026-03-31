from __future__ import annotations

import pathlib
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .artifacts import (
    get_config_snapshot_path,
    get_input_summary_path,
    get_matching_dir,
    get_parsed_base_dir,
    get_run_dir,
    get_run_json_path,
    get_run_summary_path,
    list_run_ids,
    read_json,
)
from .config import apply_overrides, load_config
from .ids import generate_run_id
from .matching import load_ambiguous, load_conflicts, load_match_results, load_match_summary, load_unmatched
from .extraction import load_proposals, persist_proposal, persist_evidence
from .review import (
    ProposalFilter,
    bulk_accept_proposals,
    compute_reviewer_summary,
    get_evidence_asset_metadata,
    get_export_candidates,
    get_figure_crop_path,
    get_latest_decision,
    get_page_image_path,
    get_pdf_asset_path,
    get_progress,
    get_proposal_detail,
    list_proposals,
    recompute_summaries,
    record_review_decision,
)
from .export import run_export
from .runner import launch_run
from .schemas import ReviewDecision, ReviewResolutionReason, RunStatus

app = FastAPI(title="Paper Table Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateRunRequest(BaseModel):
    config_path: str
    table_path: Optional[str] = None
    schema_path: Optional[str] = None
    pdf_dir: Optional[str] = None


class CreateRunResponse(BaseModel):
    run_id: str
    status: str


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/runs", response_model=CreateRunResponse)
async def create_run(request: CreateRunRequest):
    """Create and immediately start a run in background."""
    try:
        config = load_config(request.config_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail=f"Config file not found: {request.config_path}",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Config error: {e}")

    overrides = {}
    if request.table_path:
        overrides["table_path"] = request.table_path
    if request.schema_path:
        overrides["schema_path"] = request.schema_path
    if request.pdf_dir:
        overrides["pdf_dir"] = request.pdf_dir
    if overrides:
        try:
            config = apply_overrides(config, overrides)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Override error: {e}")

    run_id = generate_run_id()
    output_dir = config.output_dir

    launch_run(run_id, config, request.config_path, output_dir)

    return CreateRunResponse(run_id=run_id, status=RunStatus.created.value)


@app.get("/api/runs")
async def list_runs(output_dir: str = "./runs"):
    """List all runs."""
    try:
        run_ids = list_run_ids(output_dir)
    except Exception:
        return {"runs": []}

    runs = []
    for rid in run_ids:
        try:
            run_data = read_json(get_run_json_path(output_dir, rid))
            runs.append(run_data)
        except Exception:
            pass
    runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str, output_dir: str = "./runs"):
    """Get run data."""
    path = get_run_json_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return read_json(path)


@app.get("/api/runs/{run_id}/config")
async def get_run_config(run_id: str, output_dir: str = "./runs"):
    """Get config snapshot."""
    path = get_config_snapshot_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Config snapshot not found")
    return read_json(path)


@app.get("/api/runs/{run_id}/inputs")
async def get_run_inputs(run_id: str, output_dir: str = "./runs"):
    """Get input summary."""
    path = get_input_summary_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Input summary not found")
    return read_json(path)


@app.get("/api/runs/{run_id}/summary")
async def get_run_summary(run_id: str, output_dir: str = "./runs"):
    """Get run summary from summaries dir, falling back to run.json."""
    path = get_run_summary_path(output_dir, run_id)
    if not path.exists():
        return await get_run(run_id, output_dir)
    return read_json(path)


# ---------------------------------------------------------------------------
# T039: Matching inspection endpoints
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/matching")
async def get_run_matching(run_id: str, output_dir: str = "./runs"):
    """Get all match results for a run (T039)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    results = load_match_results(run_dir)
    summary = load_match_summary(run_dir)
    return {"run_id": run_id, "summary": summary, "results": results}


@app.get("/api/runs/{run_id}/matching/summary")
async def get_run_matching_summary(run_id: str, output_dir: str = "./runs"):
    """Get match summary counts for a run."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    summary = load_match_summary(run_dir)
    if summary is None:
        raise HTTPException(status_code=404, detail="Matching not yet complete for this run")
    return summary


@app.get("/api/runs/{run_id}/matching/unmatched")
async def get_run_unmatched(run_id: str, output_dir: str = "./runs"):
    """Get unmatched PDFs for a run (T039)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {"run_id": run_id, "unmatched": load_unmatched(run_dir)}


@app.get("/api/runs/{run_id}/matching/ambiguous")
async def get_run_ambiguous(run_id: str, output_dir: str = "./runs"):
    """Get ambiguous-match PDFs for a run (T039)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {"run_id": run_id, "ambiguous": load_ambiguous(run_dir)}


@app.get("/api/runs/{run_id}/matching/conflicts")
async def get_run_conflicts(run_id: str, output_dir: str = "./runs"):
    """Get duplicate-row-conflict PDFs for a run (T039)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {"run_id": run_id, "conflicts": load_conflicts(run_dir)}


@app.get("/api/runs/{run_id}/parsed/{pdf_id}")
async def get_parsed_document(run_id: str, pdf_id: str, output_dir: str = "./runs"):
    """Get the normalized ParsedDocument for a single PDF (T029)."""
    run_dir = get_run_dir(output_dir, run_id)
    parsed_path = run_dir / "parsed" / pdf_id / "parsed_document.json"
    if not parsed_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Parsed document not found for pdf_id={pdf_id} in run {run_id}",
        )
    return read_json(parsed_path)


@app.get("/api/runs/{run_id}/parsed/{pdf_id}/diagnostics")
async def get_parse_diagnostics(run_id: str, pdf_id: str, output_dir: str = "./runs"):
    """Get parser diagnostics for a single PDF (T031)."""
    run_dir = get_run_dir(output_dir, run_id)
    diag_path = run_dir / "parsed" / pdf_id / "diagnostics.json"
    if not diag_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Parser diagnostics not found for pdf_id={pdf_id} in run {run_id}",
        )
    return read_json(diag_path)


# ---------------------------------------------------------------------------
# Batch 4 — Review API request/response models (T069–T079)
# ---------------------------------------------------------------------------

class RecordDecisionRequest(BaseModel):
    decision: str                                   # ReviewDecision value
    resolution_reason: Optional[str] = None         # ReviewResolutionReason value
    edited_value: Optional[str] = None
    reviewer_note: Optional[str] = None


class BulkAcceptRequest(BaseModel):
    proposal_ids: list[str]


# ---------------------------------------------------------------------------
# T069 — Proposal list with filters
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/proposals")
async def get_proposals(
    run_id: str,
    output_dir: str = "./runs",
    row_id: Optional[str] = None,
    column_name: Optional[str] = None,
    pdf_id: Optional[str] = None,
    evidence_status: Optional[str] = None,
    figure_derived: Optional[bool] = None,
    decision: Optional[str] = None,
    match_status: Optional[str] = None,
):
    """List proposals with optional filters (T069).

    Filter parameters:
    - row_id: filter to a specific row
    - column_name: filter to a specific column
    - pdf_id: filter to a specific PDF
    - evidence_status: 'figure_derived' | 'fallback' | 'weak'
    - figure_derived: true/false
    - decision: ReviewDecision value or 'undecided'
    - match_status: MatchOutcome value
    """
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    filt = ProposalFilter(
        row_id=row_id,
        column_name=column_name,
        pdf_id=pdf_id,
        evidence_status=evidence_status,
        figure_derived=figure_derived,
        decision=decision,
        match_status=match_status,
    )
    proposals = list_proposals(run_dir, filt)
    return {"run_id": run_id, "count": len(proposals), "proposals": proposals}


# ---------------------------------------------------------------------------
# T070 — Proposal detail
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/proposals/{proposal_id}")
async def get_proposal(run_id: str, proposal_id: str, output_dir: str = "./runs"):
    """Get full detail for a single proposal (T070)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    detail = get_proposal_detail(run_dir, proposal_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Proposal not found: {proposal_id}")
    return detail


# ---------------------------------------------------------------------------
# T071 — Review-asset serving endpoints
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/assets/pdf/{pdf_id}")
async def serve_pdf(run_id: str, pdf_id: str, output_dir: str = "./runs"):
    """Serve the original PDF file for a given pdf_id (T071)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    pdf_path = get_pdf_asset_path(run_dir, pdf_id)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found for pdf_id={pdf_id}")
    return FileResponse(str(pdf_path), media_type="application/pdf")


@app.get("/api/runs/{run_id}/assets/pages/{pdf_id}/{page}")
async def serve_page_image(run_id: str, pdf_id: str, page: int, output_dir: str = "./runs"):
    """Serve a rendered page image for PDF viewer (T071)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    img_path = get_page_image_path(run_dir, pdf_id, page)
    if img_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Page image not found for pdf_id={pdf_id} page={page}",
        )
    return FileResponse(str(img_path), media_type="image/png")


@app.get("/api/runs/{run_id}/assets/figures/{pdf_id}/{figure_id}")
async def serve_figure_crop(run_id: str, pdf_id: str, figure_id: str, output_dir: str = "./runs"):
    """Serve a figure crop image (T071)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    crop_path = get_figure_crop_path(run_dir, pdf_id, figure_id)
    if crop_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Figure crop not found for pdf_id={pdf_id} figure_id={figure_id}",
        )
    return FileResponse(str(crop_path), media_type="image/png")


@app.get("/api/runs/{run_id}/assets/evidence/{evidence_id}")
async def get_evidence_metadata(run_id: str, evidence_id: str, output_dir: str = "./runs"):
    """Get evidence metadata for a given evidence_id (T071)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    meta = get_evidence_asset_metadata(run_dir, evidence_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Evidence not found: {evidence_id}")
    return meta


# ---------------------------------------------------------------------------
# T072/T073 — Review-decision recording
# ---------------------------------------------------------------------------

@app.post("/api/runs/{run_id}/proposals/{proposal_id}/decision")
async def record_decision(
    run_id: str,
    proposal_id: str,
    request: RecordDecisionRequest,
    output_dir: str = "./runs",
):
    """Record a review decision for a proposal (T072/T073)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    # Validate decision value
    try:
        decision = ReviewDecision(request.decision)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid decision value: {request.decision!r}. "
            f"Must be one of: {[d.value for d in ReviewDecision]}",
        )

    # Validate resolution_reason if provided
    resolution_reason = None
    if request.resolution_reason:
        try:
            resolution_reason = ReviewResolutionReason(request.resolution_reason)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid resolution_reason: {request.resolution_reason!r}",
            )

    # Resolve cell_id from proposal
    proposals = load_proposals(run_dir)
    proposal = next((p for p in proposals if p.proposal_id == proposal_id), None)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal not found: {proposal_id}")

    rec = record_review_decision(
        run_dir=run_dir,
        proposal_id=proposal_id,
        cell_id=proposal.cell_id,
        run_id=run_id,
        decision=decision,
        resolution_reason=resolution_reason,
        edited_value=request.edited_value,
        reviewer_note=request.reviewer_note,
    )
    return rec.model_dump()


# ---------------------------------------------------------------------------
# T074 — Bulk-accept visible subset
# ---------------------------------------------------------------------------

@app.post("/api/runs/{run_id}/proposals/bulk-accept")
async def bulk_accept(run_id: str, request: BulkAcceptRequest, output_dir: str = "./runs"):
    """Bulk-accept a filtered subset of undecided proposals (T074).

    Only undecided proposals in the supplied list are accepted.
    Already-decided proposals are skipped.
    """
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    recorded = bulk_accept_proposals(run_dir, run_id, request.proposal_ids)
    return {
        "run_id": run_id,
        "accepted_count": len(recorded),
        "decisions": [r.model_dump() for r in recorded],
    }


# ---------------------------------------------------------------------------
# T075 — Progress counters
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/progress")
async def get_run_progress(run_id: str, output_dir: str = "./runs"):
    """Get review progress counters (T075/T075a)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {"run_id": run_id, **get_progress(run_dir)}


# ---------------------------------------------------------------------------
# T077 — Reviewer summary
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/reviewer-summary")
async def get_reviewer_summary_endpoint(run_id: str, output_dir: str = "./runs"):
    """Get the reviewer outcome summary (T077)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    summary = compute_reviewer_summary(run_dir, run_id)
    return summary.model_dump()


# ---------------------------------------------------------------------------
# T078 — Summary recomputation
# ---------------------------------------------------------------------------

@app.post("/api/runs/{run_id}/summaries/recompute")
async def recompute_run_summaries(run_id: str, output_dir: str = "./runs"):
    """Recompute and persist both run and reviewer summaries from artifacts (T078)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    try:
        result = recompute_summaries(run_dir, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return result


# ---------------------------------------------------------------------------
# T079 — Export candidate selection
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/export-candidates")
async def get_run_export_candidates(run_id: str, output_dir: str = "./runs"):
    """Return accepted proposals that are eligible for export (T079).

    Only explicitly accepted (as-is or with edit) proposals are returned.
    Unreviewed, confirmed-no-data, and rejected proposals are excluded by
    construction.
    """
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    candidates = get_export_candidates(run_dir)
    return {
        "run_id": run_id,
        "count": len(candidates),
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# T100 — Download endpoints
# ---------------------------------------------------------------------------

@app.get("/api/runs/{run_id}/downloads/workbook")
async def download_workbook(run_id: str, output_dir: str = "./runs"):
    """Download updated workbook if export exists (T100)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    exports_dir = run_dir / "exports"
    if not exports_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="No exports found. Complete review and trigger export first.",
        )
    xlsx_files = sorted(exports_dir.glob("*.xlsx"))
    if not xlsx_files:
        raise HTTPException(
            status_code=404,
            detail="No workbook export found. Trigger export after completing review.",
        )
    latest = xlsx_files[-1]
    return FileResponse(
        str(latest),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=latest.name,
    )


@app.get("/api/runs/{run_id}/downloads/audit-log")
async def download_audit_log(run_id: str, output_dir: str = "./runs"):
    """Download audit log if export exists (T100)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    exports_dir = run_dir / "exports"
    if not exports_dir.exists():
        raise HTTPException(status_code=404, detail="No exports found.")
    audit_files = sorted(exports_dir.glob("audit_log*.json")) + sorted(exports_dir.glob("audit_log*.csv"))
    if not audit_files:
        raise HTTPException(status_code=404, detail="No audit log found.")
    latest = audit_files[-1]
    suffix = latest.suffix.lower()
    media_type = "application/json" if suffix == ".json" else "text/csv"
    return FileResponse(str(latest), media_type=media_type, filename=latest.name)


@app.get("/api/runs/{run_id}/downloads/run-summary")
async def download_run_summary_file(run_id: str, output_dir: str = "./runs"):
    """Download run_summary.json (T100)."""
    path = get_run_summary_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="run_summary.json not found.")
    return FileResponse(str(path), media_type="application/json", filename="run_summary.json")


@app.get("/api/runs/{run_id}/downloads/reviewer-summary")
async def download_reviewer_summary_file(run_id: str, output_dir: str = "./runs"):
    """Download reviewer_summary.json (T100)."""
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    summaries_dir = run_dir / "summaries"
    reviewer_path = summaries_dir / "reviewer_summary.json"
    if not reviewer_path.exists():
        raise HTTPException(status_code=404, detail="reviewer_summary.json not found.")
    return FileResponse(str(reviewer_path), media_type="application/json", filename="reviewer_summary.json")


# ---------------------------------------------------------------------------
# T096-T099 — Trigger export pipeline
# ---------------------------------------------------------------------------

@app.post("/api/runs/{run_id}/export")
async def trigger_export(run_id: str, output_dir: str = "./runs"):
    """Trigger the export pipeline for a completed run (T096-T099).

    Generates:
    - Updated XLSX workbook with accepted-only changes and changed-cell highlighting
    - Audit log JSON
    - Diagnostics JSON

    Only available for runs in completed or completed_with_warnings status.
    Returns a summary of generated artifacts and any unsupported-feature warnings.
    """
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    try:
        result = run_export(run_dir, output_dir, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")
    return result

