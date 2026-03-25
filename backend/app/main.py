from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .models import CreateRunRequest
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
