from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .artifacts import (
    get_config_snapshot_path,
    get_input_summary_path,
    get_run_json_path,
    get_run_summary_path,
    list_run_ids,
    read_json,
)
from .config import apply_overrides, load_config
from .ids import generate_run_id
from .runner import launch_run
from .schemas import RunStatus

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
