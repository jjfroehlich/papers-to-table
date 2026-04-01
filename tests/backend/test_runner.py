"""Tests for the staged asyncio runner."""
from __future__ import annotations

import asyncio
import pathlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import respx
import httpx
import pandas as pd

from backend.app.artifacts import (
    get_config_snapshot_path,
    get_input_summary_path,
    get_run_json_path,
    get_reviewer_summary_path,
    get_run_summary_path,
    init_run_bundle,
    read_json,
    write_json,
)
from backend.app.extraction import ProposalRecord, persist_proposal
from backend.app.config import RunConfig
from backend.app.runner import get_initial_run_data, run_pipeline
from backend.app.ids import generate_proposal_id
from backend.app.matching import MatchResult
from backend.app.schemas import MatchOutcome, ProposalState, RunStatus, SupportLabel

FIXTURE_TABLE = "tests/fixtures/tables/literature_fixture.xlsx"
FIXTURE_SCHEMA = "tests/fixtures/tables/literature_fixture_schema.csv"
FIXTURE_PDF_DIR = "tests/fixtures/papers"


def make_config(tmp_path: pathlib.Path, **kwargs) -> RunConfig:
    data = {
        "table_path": FIXTURE_TABLE,
        "schema_path": FIXTURE_SCHEMA,
        "pdf_dir": FIXTURE_PDF_DIR,
        "output_dir": str(tmp_path / "runs"),
        "verify_mode": False,
        "provider": {
            "token": "lm_studio",
            "base_url": "http://localhost:1234",
            "text_model": {
                "model_id": "qwen/qwen3-30b-a3b-2507",
            },
        },
        **kwargs,
    }
    return RunConfig.model_validate(data)


class TestGetInitialRunData:
    def test_has_required_fields(self, tmp_path):
        config = make_config(tmp_path)
        data = get_initial_run_data("run_test_123", config, "config.json")
        assert data["run_id"] == "run_test_123"
        assert data["status"] == RunStatus.created.value
        assert data["config_path"] == "config.json"
        assert data["verify_mode"] is False
        assert data["provider_token"] == "lm_studio"

    def test_timestamps(self, tmp_path):
        config = make_config(tmp_path)
        data = get_initial_run_data("run_test_123", config, None)
        assert data["started_at"] is None
        assert data["completed_at"] is None
        assert data["created_at"] is not None


class TestRunPipeline:
    @pytest.mark.asyncio
    @respx.mock
    async def test_completes_with_valid_inputs(self, tmp_path):
        """Happy-path: pipeline completes when LM Studio is reachable."""
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_test_happy"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["status"] in (
            RunStatus.completed.value,
            RunStatus.completed_with_warnings.value,
        )
        assert run_data["completed_at"] is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_writes_config_snapshot(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_snap"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        snap_path = get_config_snapshot_path(output_dir, run_id)
        assert snap_path.exists()
        snap = read_json(snap_path)
        assert snap["provider"]["token"] == "lm_studio"

    @pytest.mark.asyncio
    @respx.mock
    async def test_writes_input_summary(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_inputs"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        input_path = get_input_summary_path(output_dir, run_id)
        assert input_path.exists()
        summary = read_json(input_path)
        assert summary["table_rows"] is not None
        assert summary["table_rows"] > 0
        assert summary["pdf_count"] is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fails_with_unreachable_provider(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            side_effect=httpx.ConnectError("refused")
        )
        config = make_config(tmp_path)
        run_id = "run_fail"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["status"] == RunStatus.failed.value
        assert run_data["error_message"] is not None
        assert run_data["current_stage"] is None

    @pytest.mark.asyncio
    async def test_input_summary_written_before_readiness_check(self, tmp_path):
        """Input summary should exist even when readiness fails."""
        config = make_config(tmp_path, pdf_dir="/nonexistent/dir")
        run_id = "run_early_summary"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["status"] == RunStatus.failed.value
        assert run_data["current_stage"] is None

        # Input summary should still exist
        input_path = get_input_summary_path(output_dir, run_id)
        assert input_path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_records_total_rows_and_eligible_cells(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_counts"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["total_rows"] > 0
        assert run_data["eligible_cells"] >= 0

    @pytest.mark.asyncio
    async def test_provider_init_failure_does_not_generate_skipped_proposals(self, tmp_path, monkeypatch):
        config = make_config(tmp_path)
        run_id = "run_no_skipped"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        monkeypatch.setattr("backend.app.runner.check_readiness", _ready_ok)
        monkeypatch.setattr("backend.app.runner.initialize_provider", _raise_provider_error)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        proposals_dir = pathlib.Path(output_dir) / run_id / "proposals"

        assert run_data["status"] == RunStatus.failed.value
        assert run_data["error_message"] == "provider offline"
        assert list(proposals_dir.glob("*.json")) == []

    @pytest.mark.asyncio
    async def test_only_usable_matched_rows_create_proposal_artifacts(self, tmp_path, monkeypatch):
        config = make_config(tmp_path)
        run_id = "run_matched_only"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        df = pd.DataFrame([
            {
                "Title": "Matched Paper",
                "Authors": "Smith, J.",
                "Publication Year": "2024",
                "assay": "",
            },
            {
                "Title": "Unmatched Paper",
                "Authors": "Doe, A.",
                "Publication Year": "2023",
                "assay": "",
            },
        ])
        schema = [{"column_name": "assay", "description": "Assay description"}]
        eligible = [
            {"row_index": 0, "column_name": "assay", "current_value": "", "eligibility": "eligible"},
            {"row_index": 1, "column_name": "assay", "current_value": "", "eligibility": "eligible"},
        ]
        match_results = [
            MatchResult(
                pdf_id="paper_1",
                pdf_path="paper_1.pdf",
                outcome=MatchOutcome.matched,
                matched_row_index=0,
                matched_row_title="Matched Paper",
                score=0.9,
                runner_up_score=0.2,
                runner_up_row_index=1,
                reasoning="clear match",
                blocked=False,
                matched_at=datetime.now(timezone.utc).isoformat(),
            ),
            MatchResult(
                pdf_id="paper_2",
                pdf_path="paper_2.pdf",
                outcome=MatchOutcome.unmatched,
                matched_row_index=None,
                matched_row_title=None,
                score=0.0,
                runner_up_score=0.0,
                runner_up_row_index=None,
                reasoning="unmatched",
                blocked=True,
                blocked_reason="unmatched",
                matched_at=datetime.now(timezone.utc).isoformat(),
            ),
        ]

        monkeypatch.setattr("backend.app.runner.check_readiness", _ready_ok)
        monkeypatch.setattr("backend.app.runner.load_table", lambda path: df)
        monkeypatch.setattr("backend.app.runner.validate_metadata_columns", lambda df: [])
        monkeypatch.setattr("backend.app.runner.load_schema", lambda schema_path, table_path: schema)
        monkeypatch.setattr("backend.app.runner.validate_schema_columns", lambda schema: [])
        monkeypatch.setattr("backend.app.runner.get_eligible_cells", lambda df, schema, verify_mode: eligible)
        monkeypatch.setattr("backend.app.runner.parse_pdf", _fake_parse_pdf)
        monkeypatch.setattr("backend.app.runner.run_matching", lambda **kwargs: match_results)
        monkeypatch.setattr("backend.app.runner.persist_match_artifacts", lambda *args, **kwargs: None)
        monkeypatch.setattr("backend.app.runner.initialize_provider", _fake_initialize_provider)
        monkeypatch.setattr("backend.app.runner.run_style_profiles_stage", _fake_style_profiles)
        monkeypatch.setattr("backend.app.runner.run_retrieval_for_cell", lambda **kwargs: None)
        monkeypatch.setattr("backend.app.runner.extract_cell", _fake_extract_cell)

        await run_pipeline(run_id, config, "config.json", output_dir)

        proposals_dir = pathlib.Path(output_dir) / run_id / "proposals"
        proposal_files = list(proposals_dir.glob("*.json"))
        run_data = read_json(get_run_json_path(output_dir, run_id))

        assert run_data["proposals_generated"] == 1
        assert len(proposal_files) == 1


async def _ready_ok(*args, **kwargs):
    return SimpleNamespace(ok=True, errors=[])


async def _raise_provider_error(*args, **kwargs):
    from backend.app.provider import ProviderError

    raise ProviderError("provider offline")


async def _fake_initialize_provider(*args, **kwargs):
    return object(), SimpleNamespace(mode="text", capabilities=None, model_dump=lambda: {"mode": "text"})


async def _fake_style_profiles(**kwargs):
    return {}


def _fake_parse_pdf(**kwargs):
    pdf_id = kwargs["pdf_id"]
    doc = SimpleNamespace(model_dump=lambda: {"pdf_id": pdf_id, "blocks": []})
    return doc, {}, []


async def _fake_extract_cell(**kwargs):
    proposal_id = generate_proposal_id(kwargs["run_id"], kwargs["cell_id"])
    proposal = ProposalRecord(
        proposal_id=proposal_id,
        run_id=kwargs["run_id"],
        pdf_id=kwargs["pdf_id"],
        row_id=kwargs["row_id"],
        column_name=kwargs["column_name"],
        cell_id=kwargs["cell_id"],
        state=ProposalState.unclear,
        support=SupportLabel.weak_evidence,
        proposed_value="candidate",
        rationale="- extracted",
        evidence_ids=[],
        warning_flags=[],
        needs_more_evidence=False,
        is_verify_mode=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_proposal(kwargs["run_dir"], proposal)
    return proposal
