from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CreateRunRequest(BaseModel):
    config_path: str = "config.json"
    table_path: Optional[str] = None
    schema_path: Optional[str] = None
    pdf_dir: Optional[str] = None
    output_dir: Optional[str] = None
    table_staged_handle: Optional[str] = None
    schema_staged_handle: Optional[str] = None
    pdf_dir_staged_handle: Optional[str] = None


class RunPreflightRequest(CreateRunRequest):
    pass


class CreateRunResponse(BaseModel):
    run_id: str
    status: str
    resolved_inputs: dict[str, Any]


class StagedInputResponse(BaseModel):
    handle: str
    kind: str
    logical_source: str
    runtime_locator: str


class RunsDirectoryRequest(BaseModel):
    path: Optional[str] = None
    browse: bool = False


class RunsDirectoryResponse(BaseModel):
    status: str
    path: Optional[str] = None


class OpenPdfResponse(BaseModel):
    run_id: str
    pdf_id: str
    status: str
    path: str


class RecordDecisionRequest(BaseModel):
    decision: str
    resolution_reason: Optional[str] = None
    edited_value: Optional[str] = None
    reviewer_note: Optional[str] = None


class BulkAcceptRequest(BaseModel):
    proposal_ids: list[str]


class BulkDecisionRequest(BaseModel):
    proposal_ids: list[str]
    decision: str
    replace_existing: bool = False
