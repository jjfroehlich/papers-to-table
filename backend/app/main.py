from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .artifacts import ArtifactStore
from .config import load_config
from .models import (
    AppConfig,
    BulkAcceptRequest,
    CreateRunRequest,
    MatchListResponse,
    MatchOutcome,
    MatchRecord,
    ProposalListResponse,
    ProposalRecord,
    ReviewDecisionRequest,
    ReviewerSummary,
    RunInspectionResponse,
    InputSummary,
    RunRecord,
    RunSummary,
)
from .review import apply_review_decision
from .runner import Runner, sort_proposals
from .summaries import build_reviewer_summary, build_run_summary
from .exporter import export_reviewed_changes


def create_app(output_root: str | Path = "artifacts") -> FastAPI:
    app = FastAPI(title="Paper Table Agent")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    runner = Runner(Path(output_root))

    def store_for(run_id: str) -> ArtifactStore:
        root = Path(output_root) / run_id
        if not root.exists():
            raise HTTPException(status_code=404, detail="Run not found")
        return ArtifactStore(root)

    def read_run(store: ArtifactStore) -> RunRecord:
        return store.read_model(store.path("run.json"), RunRecord)

    def read_config(store: ArtifactStore) -> AppConfig:
        return store.read_model(store.path("config.snapshot.json"), AppConfig)

    def read_matches(store: ArtifactStore) -> list[MatchRecord]:
        return store.read_models_jsonl(store.path("matching", "matches.jsonl"), MatchRecord)

    def read_proposals(store: ArtifactStore) -> list[ProposalRecord]:
        return store.read_models_jsonl(store.path("proposals", "proposals.jsonl"), ProposalRecord)

    def read_rows(store: ArtifactStore) -> list[dict]:
        return store.read_json(store.path("inputs", "rows.json"))

    def persist_summaries(store: ArtifactStore, run: RunRecord, proposals: list[ProposalRecord]) -> tuple[RunSummary, ReviewerSummary]:
        matches = read_matches(store)
        config = read_config(store)
        changed = sum(1 for proposal in proposals if proposal.review_decision.value.startswith("accept"))
        workbook_name, audit_name, changed, warnings = export_reviewed_changes(config.paths.table_path, read_rows(store), proposals, store.path("exports"), config.export.highlight_hex)
        diagnostics = store.read_json(store.path("logs", "diagnostics.json")) if store.path("logs", "diagnostics.json").exists() else {}
        diagnostics["exports"] = {"workbook": workbook_name, "audit_log": audit_name}
        diagnostics["warnings"] = warnings
        store.write_json(store.path("logs", "diagnostics.json"), diagnostics)
        run_summary = build_run_summary(run, matches, proposals, changed)
        reviewer_summary = build_reviewer_summary(run, matches, proposals, changed)
        store.write_model(store.path("summaries", "run_summary.json"), run_summary)
        store.write_model(store.path("summaries", "reviewer_summary.json"), reviewer_summary)
        return run_summary, reviewer_summary

    @app.post("/api/runs", response_model=RunRecord)
    def create_run(request: CreateRunRequest) -> RunRecord:
        config = load_config(request.config_path, request.config.model_dump(mode="json") if request.config else None)
        return runner.execute(config)

    @app.get("/api/runs", response_model=list[RunRecord])
    def list_runs() -> list[RunRecord]:
        runs: list[RunRecord] = []
        for run_dir in sorted(Path(output_root).glob("run-*")):
            store = ArtifactStore(run_dir)
            runs.append(read_run(store))
        return runs

    @app.get("/api/runs/{run_id}", response_model=RunInspectionResponse)
    def get_run(run_id: str) -> RunInspectionResponse:
        store = store_for(run_id)
        return RunInspectionResponse(
            run=read_run(store),
            summary=store.read_model(store.path("summaries", "run_summary.json"), RunSummary),
            reviewer_summary=store.read_model(store.path("summaries", "reviewer_summary.json"), ReviewerSummary),
            input_summary=store.read_model(store.path("inputs", "input_summary.json"), InputSummary),
        )

    @app.get("/api/runs/{run_id}/summary", response_model=RunSummary)
    def get_run_summary(run_id: str) -> RunSummary:
        store = store_for(run_id)
        return store.read_model(store.path("summaries", "run_summary.json"), RunSummary)

    @app.get("/api/runs/{run_id}/reviewer-summary", response_model=ReviewerSummary)
    def get_reviewer_summary(run_id: str) -> ReviewerSummary:
        store = store_for(run_id)
        return store.read_model(store.path("summaries", "reviewer_summary.json"), ReviewerSummary)

    @app.get("/api/runs/{run_id}/config")
    def get_config_snapshot(run_id: str) -> dict:
        store = store_for(run_id)
        return store.read_json(store.path("config.snapshot.json"))

    @app.get("/api/runs/{run_id}/input-summary")
    def get_input_summary(run_id: str) -> dict:
        store = store_for(run_id)
        return store.read_json(store.path("inputs", "input_summary.json"))

    @app.get("/api/runs/{run_id}/matches", response_model=MatchListResponse)
    def get_matches(run_id: str, outcome: MatchOutcome | None = None) -> MatchListResponse:
        store = store_for(run_id)
        matches = read_matches(store)
        if outcome:
            matches = [match for match in matches if match.outcome == outcome]
        return MatchListResponse(matches=matches)

    @app.get("/api/runs/{run_id}/proposals", response_model=ProposalListResponse)
    def get_proposals(
        run_id: str,
        row_id: str | None = None,
        column_name: str | None = None,
        pdf_id: str | None = None,
        evidence_status: str | None = None,
        figure_only: bool = False,
        match_status: MatchOutcome | None = None,
        review_status: str | None = None,
    ) -> ProposalListResponse:
        store = store_for(run_id)
        proposals = read_proposals(store)
        matches = {match.pdf_id: match for match in read_matches(store)}
        if row_id:
            proposals = [proposal for proposal in proposals if proposal.row_id == row_id]
        if column_name:
            proposals = [proposal for proposal in proposals if proposal.column_name == column_name]
        if pdf_id:
            proposals = [proposal for proposal in proposals if proposal.pdf_id == pdf_id]
        if evidence_status == "needs_more_evidence":
            proposals = [proposal for proposal in proposals if proposal.needs_more_evidence]
        if figure_only:
            proposals = [proposal for proposal in proposals if proposal.source_mode == "vision"]
        if match_status:
            proposals = [proposal for proposal in proposals if matches.get(proposal.pdf_id) and matches[proposal.pdf_id].outcome == match_status]
        if review_status:
            proposals = [proposal for proposal in proposals if proposal.review_decision.value == review_status]
        proposals = sort_proposals(proposals)
        return ProposalListResponse(proposals=proposals, total=len(proposals))

    @app.get("/api/runs/{run_id}/proposals/{proposal_id}")
    def get_proposal_detail(run_id: str, proposal_id: str) -> dict:
        store = store_for(run_id)
        proposal = next((proposal for proposal in read_proposals(store) if proposal.proposal_id == proposal_id), None)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        rows = {row["row_id"]: row for row in read_rows(store)}
        evidences = [item for item in store.read_jsonl(store.path("evidence", "evidence.jsonl")) if item.get("proposal_id") == proposal_id]
        return {
            "proposal": proposal.model_dump(mode="json"),
            "row_context": rows.get(proposal.row_id, {}),
            "primary_evidence": evidences[0] if evidences else None,
            "secondary_evidence": evidences[1:],
        }

    @app.post("/api/runs/{run_id}/reviews")
    def post_review(run_id: str, request: ReviewDecisionRequest) -> dict:
        store = store_for(run_id)
        run = read_run(store)
        proposals = read_proposals(store)
        updated_proposals = []
        history_path = store.path("review", "history.jsonl")
        target = None
        for proposal in proposals:
            if proposal.proposal_id == request.proposal_id:
                target = proposal
                updated, decision = apply_review_decision(proposal, request)
                updated_proposals.append(updated)
                store.append_jsonl(history_path, {"proposal_before": proposal.model_dump(mode="json"), "decision": decision.model_dump(mode="json")})
            else:
                updated_proposals.append(proposal)
        if target is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        store.write_models_jsonl(store.path("proposals", "proposals.jsonl"), updated_proposals)
        run_summary, reviewer_summary = persist_summaries(store, run, updated_proposals)
        return {"ok": True, "summary": run_summary.model_dump(mode="json"), "reviewer_summary": reviewer_summary.model_dump(mode="json")}

    @app.post("/api/runs/{run_id}/bulk-accept")
    def bulk_accept(run_id: str, request: BulkAcceptRequest) -> dict:
        store = store_for(run_id)
        run = read_run(store)
        proposals = read_proposals(store)
        updated = []
        for proposal in proposals:
            if proposal.proposal_id in request.proposal_ids and proposal.review_decision.value == "no_decision":
                proposal = proposal.model_copy(update={"review_decision": 'accept', "reviewed_value": proposal.proposed_value})
            updated.append(proposal)
        store.write_models_jsonl(store.path("proposals", "proposals.jsonl"), updated)
        run_summary, reviewer_summary = persist_summaries(store, run, updated)
        return {"ok": True, "summary": run_summary.model_dump(mode="json"), "reviewer_summary": reviewer_summary.model_dump(mode="json")}

    @app.get("/api/runs/{run_id}/assets/pdf/{pdf_id}")
    def get_pdf_asset(run_id: str, pdf_id: str):
        store = store_for(run_id)
        match = next((item for item in read_matches(store) if item.pdf_id == pdf_id), None)
        config = read_config(store)
        if match is None:
            raise HTTPException(status_code=404, detail="PDF not found")
        path = Path(config.paths.pdf_dir) / match.pdf_name
        return FileResponse(path)

    @app.get("/api/runs/{run_id}/assets/page/{pdf_id}/{page_number}")
    def get_page_image(run_id: str, pdf_id: str, page_number: int):
        store = store_for(run_id)
        path = store.path("parsed", pdf_id, f"page-{page_number}.png")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Page image not found")
        return FileResponse(path)

    @app.get("/api/runs/{run_id}/assets/evidence/{evidence_id}")
    def get_evidence_asset(run_id: str, evidence_id: str, download: str | None = Query(default=None)):
        store = store_for(run_id)
        evidence = next((item for item in store.read_jsonl(store.path("evidence", "evidence.jsonl")) if item.get("evidence_id") == evidence_id), None)
        if evidence is None:
            raise HTTPException(status_code=404, detail="Evidence not found")
        if download == 'crop' and evidence.get('crop_path'):
            return FileResponse(store.root / evidence['crop_path'])
        return evidence

    @app.get("/api/runs/{run_id}/downloads/{download_name}")
    def download(run_id: str, download_name: str):
        store = store_for(run_id)
        mapping = {
            "workbook": store.path("exports", "updated_workbook.xlsx"),
            "audit-log": store.path("exports", "audit_log.csv"),
            "run-summary": store.path("summaries", "run_summary.json"),
            "reviewer-summary": store.path("summaries", "reviewer_summary.json"),
            "artifacts": store.root,
        }
        path = mapping.get(download_name)
        if path is None or not path.exists():
            raise HTTPException(status_code=404, detail="Download not found")
        if path.is_dir():
            raise HTTPException(status_code=400, detail="Directory download is not implemented in this MVP build")
        return FileResponse(path)

    return app


app = create_app()
