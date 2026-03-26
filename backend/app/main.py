from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .models import CreateRunRequest, ReviewDecisionType
from .services.review_service import ReviewService
from .services.run_service import RunService

ARTIFACT_ROOT = Path("artifacts")
ARTIFACT_ROOT.mkdir(exist_ok=True)

app = FastAPI(title="Paper Table Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
run_service = RunService(base_dir=ARTIFACT_ROOT)
review_service = ReviewService(run_service.store)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/runs")
def create_run(payload: CreateRunRequest) -> dict:
    return run_service.create_run(payload.config_path).model_dump()


@app.get("/api/runs")
def list_runs() -> list[dict]:
    return run_service.list_runs()


@app.get("/api/runs/{run_id}")
def get_run_summary(run_id: str) -> dict:
    try:
        return run_service.get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/config")
def get_run_config(run_id: str) -> dict:
    try:
        return run_service.get_config_snapshot(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Config snapshot not found") from exc


@app.get("/api/runs/{run_id}/inputs")
def get_run_inputs(run_id: str) -> dict:
    try:
        return run_service.get_input_summary(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Input summary not found") from exc


@app.get("/api/runs/{run_id}/matching/issues")
def get_run_matching_issues(run_id: str) -> dict:
    try:
        return run_service.get_matching_issues(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Matching summary not found") from exc


@app.get("/api/runs/{run_id}/summaries/run")
def get_run_summary_file(run_id: str) -> dict:
    try:
        return run_service.get_run_summary(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run summary not found") from exc


@app.get("/api/runs/{run_id}/summaries/reviewer")
def get_reviewer_summary_file(run_id: str) -> dict:
    try:
        return run_service.get_reviewer_summary(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Reviewer summary not found") from exc


@app.get("/api/runs/{run_id}/downloads")
def list_downloads(run_id: str) -> dict:
    run_dir = ARTIFACT_ROOT / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    workbook = run_dir / "exports" / "updated.xlsx"
    audit = run_dir / "exports" / "audit_log.jsonl"
    run_summary = run_dir / "summaries" / "run_summary.json"
    reviewer_summary = run_dir / "summaries" / "reviewer_summary.json"
    return {
        "run_id": run_id,
        "downloads": {
            "updated_workbook": {"ready": workbook.exists(), "path": str(workbook)},
            "audit_log": {"ready": audit.exists(), "path": str(audit)},
            "run_summary": {"ready": run_summary.exists(), "url": f"/api/runs/{run_id}/downloads/run-summary"},
            "reviewer_summary": {"ready": reviewer_summary.exists(), "url": f"/api/runs/{run_id}/downloads/reviewer-summary"},
            "artifacts_zip": {"ready": True, "url": f"/api/runs/{run_id}/downloads/artifacts"},
        },
    }


@app.post("/api/runs/{run_id}/export")
def export_run_outputs(run_id: str) -> dict:
    try:
        return run_service.export_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run/config not found") from exc


@app.get("/api/runs/{run_id}/downloads/run-summary")
def download_run_summary(run_id: str) -> FileResponse:
    target = ARTIFACT_ROOT / run_id / "summaries" / "run_summary.json"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Run summary not available")
    return FileResponse(target, filename=f"{run_id}-run-summary.json")


@app.get("/api/runs/{run_id}/downloads/reviewer-summary")
def download_reviewer_summary(run_id: str) -> FileResponse:
    target = ARTIFACT_ROOT / run_id / "summaries" / "reviewer_summary.json"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Reviewer summary not available")
    return FileResponse(target, filename=f"{run_id}-reviewer-summary.json")


@app.get("/api/runs/{run_id}/downloads/workbook")
def download_workbook(run_id: str) -> FileResponse:
    target = ARTIFACT_ROOT / run_id / "exports" / "updated.xlsx"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Updated workbook not available yet")
    return FileResponse(target, filename=f"{run_id}-updated.xlsx")


@app.get("/api/runs/{run_id}/downloads/audit-log")
def download_audit(run_id: str) -> FileResponse:
    target = ARTIFACT_ROOT / run_id / "exports" / "audit_log.jsonl"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Audit log not available yet")
    return FileResponse(target, filename=f"{run_id}-audit-log.jsonl")


@app.get("/api/runs/{run_id}/downloads/artifacts")
def download_artifacts_zip(run_id: str) -> FileResponse:
    run_dir = ARTIFACT_ROOT / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    zip_base = run_dir / "exports" / f"{run_id}-artifacts"
    archive_path = shutil.make_archive(str(zip_base), "zip", root_dir=run_dir)
    return FileResponse(archive_path, filename=f"{run_id}-artifacts.zip")


@app.get("/api/runs/{run_id}/proposals")
def list_proposals(
    run_id: str,
    row_id: str | None = None,
    column_name: str | None = None,
    pdf_id: str | None = None,
    evidence_status: str | None = None,
    figure_derived: bool | None = None,
    match_status: str | None = None,
    review_decision: str | None = None,
) -> dict:
    run_dir = ARTIFACT_ROOT / run_id
    try:
        review_service.refresh_review_index(run_dir)
        return review_service.list_proposals(
            run_dir,
            {
                "row_id": row_id,
                "column_name": column_name,
                "pdf_id": pdf_id,
                "evidence_status": evidence_status,
                "figure_derived": figure_derived,
                "match_status": match_status,
                "review_decision": review_decision,
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run or proposal artifacts not found") from exc


@app.get("/api/runs/{run_id}/proposals/{proposal_id}")
def get_proposal_detail(run_id: str, proposal_id: str) -> dict:
    run_dir = ARTIFACT_ROOT / run_id
    try:
        review_service.refresh_review_index(run_dir)
        return review_service.proposal_detail(run_dir, proposal_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Proposal not found") from exc


@app.post("/api/runs/{run_id}/review/decisions")
def record_review_decision(
    run_id: str,
    payload: dict,
) -> dict:
    run_dir = ARTIFACT_ROOT / run_id
    try:
        decision = ReviewDecisionType(payload.get("decision", ReviewDecisionType.UNDECIDED.value))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid review decision type") from exc
    try:
        return review_service.record_decision(
            run_dir,
            proposal_id=payload["proposal_id"],
            decision=decision,
            edited_value=payload.get("edited_value"),
            reviewer_note=payload.get("reviewer_note"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing field: {exc}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Proposal not found") from exc


@app.post("/api/runs/{run_id}/review/decisions/bulk-accept-visible")
def bulk_accept_visible(
    run_id: str,
    payload: dict,
) -> dict:
    run_dir = ARTIFACT_ROOT / run_id
    try:
        return review_service.bulk_accept_visible(
            run_dir,
            {
                "row_id": payload.get("row_id"),
                "column_name": payload.get("column_name"),
                "pdf_id": payload.get("pdf_id"),
                "evidence_status": payload.get("evidence_status"),
                "figure_derived": payload.get("figure_derived"),
                "match_status": payload.get("match_status"),
                "review_decision": payload.get("review_decision"),
            },
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run or proposal artifacts not found") from exc


@app.get("/api/runs/{run_id}/review/assets/pdf/{pdf_id}")
def get_pdf_asset(run_id: str, pdf_id: str) -> FileResponse:
    run_dir = ARTIFACT_ROOT / run_id
    parsed_doc = run_service.store.find_by_id(run_dir, "parsed/documents.jsonl", "pdf_id", pdf_id)
    if parsed_doc is None:
        raise HTTPException(status_code=404, detail="PDF metadata not found")
    source_pdf = Path(parsed_doc["source_pdf_path"])
    if not source_pdf.exists():
        raise HTTPException(status_code=404, detail="PDF file missing")
    return FileResponse(source_pdf)


@app.get("/api/runs/{run_id}/review/assets/page/{pdf_id}/{page_number}")
def get_page_asset(run_id: str, pdf_id: str, page_number: int) -> FileResponse:
    page_path = ARTIFACT_ROOT / run_id / "parsed" / "pages" / pdf_id / f"page_{page_number:04d}.png"
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(page_path)


@app.get("/api/runs/{run_id}/review/assets/figure")
def get_figure_asset(run_id: str, path: str = Query(...)) -> FileResponse:
    run_dir = (ARTIFACT_ROOT / run_id).resolve()
    candidate = Path(path).resolve()
    if run_dir not in candidate.parents and candidate != run_dir:
        raise HTTPException(status_code=400, detail="Figure path must be inside this run's artifacts")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="Figure asset not found")
    return FileResponse(candidate)


@app.get("/api/runs/{run_id}/review/evidence/{evidence_id}")
def get_evidence_metadata(run_id: str, evidence_id: str) -> dict:
    run_dir = ARTIFACT_ROOT / run_id
    evidence = run_service.store.find_by_id(run_dir, "evidence/evidence.jsonl", "evidence_id", evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return evidence
