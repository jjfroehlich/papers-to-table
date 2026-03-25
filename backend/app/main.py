from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .runner import RunStore, RunnerError
from .schemas import ErrorResponse, RunCreateRequest, RunCreateResponse, RunRecord, RunSummary

app = FastAPI(title="Paper Table Agent API", version="0.1.0")
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
