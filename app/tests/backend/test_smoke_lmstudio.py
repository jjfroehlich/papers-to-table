"""T105: Opt-in live LM Studio smoke test.

This test is skipped by default.  It requires:
  - LM Studio running at the configured base_url with a model loaded
  - The environment variable PAPER_TABLE_SMOKE=1 to opt in

Run with:
    PAPER_TABLE_SMOKE=1 python -m pytest tests/backend/test_smoke_lmstudio.py -v -m smoke

When the environment is correctly configured, at least one non-empty proposal
with reviewer-usable evidence must be generated from the canonical fixtures.
When readiness fails, the test captures and reports the explicit readiness
error rather than treating the run as a normal success.
"""
from __future__ import annotations

import asyncio
import os
import pathlib

import pytest

from backend.app.artifacts import get_run_json_path, read_json
from backend.app.config import RunConfig, check_readiness
from backend.app.extraction import load_evidence, load_proposals
from backend.app.runner import run_pipeline

FIXTURE_TABLE = "../benchmark_datasets/massively_parallel_reporter_assays/table_template.csv"
FIXTURE_SCHEMA = "../benchmark_datasets/massively_parallel_reporter_assays/schema.csv"
FIXTURE_PDF_DIR = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs"

# Register custom marker in pyproject.toml or via conftest if needed
pytestmark = pytest.mark.smoke

_SMOKE_ENABLED = os.environ.get("PAPER_TABLE_SMOKE", "").strip() == "1"
_SKIP_REASON = (
    "Live LM Studio smoke test is opt-in. "
    "Set PAPER_TABLE_SMOKE=1 and have LM Studio running with a model loaded."
)


@pytest.mark.skipif(not _SMOKE_ENABLED, reason=_SKIP_REASON)
@pytest.mark.asyncio
async def test_live_lm_studio_produces_proposals(tmp_path: pathlib.Path):
    """Live smoke: run the pipeline on canonical fixtures with real LM Studio.

    Pass condition: at least one non-empty proposal with reviewer-usable
    evidence is generated.

    Fail-with-readiness-error: if LM Studio is unreachable or unconfigured,
    the test reports the explicit readiness error instead of passing.
    """
    lm_studio_url = os.environ.get("LM_STUDIO_URL", "http://localhost:1234")
    text_model_id = os.environ.get("LM_STUDIO_TEXT_MODEL", "")
    if not text_model_id:
        pytest.skip(
            "LM_STUDIO_TEXT_MODEL env var not set. "
            "Set it to the model ID loaded in LM Studio (e.g., meta-llama-3.1-8b-instruct)."
        )

    config_data = {
        "table_path": FIXTURE_TABLE,
        "schema_path": FIXTURE_SCHEMA,
        "pdf_dir": FIXTURE_PDF_DIR,
        "output_dir": str(tmp_path / "runs"),
        "verify_mode": False,
        "provider": {
            "token": "lm_studio",
            "base_url": lm_studio_url,
            "text_model": {"model_id": text_model_id},
        },
        "parser": {"allow_basic_fallback": True},
    }
    config = RunConfig.model_validate(config_data)

    # Explicit readiness check before running — report errors clearly
    readiness = await check_readiness(config)
    if not readiness.ok:
        pytest.fail(
            f"LM Studio readiness check failed — cannot run smoke test.\n"
            f"Errors: {'; '.join(readiness.errors)}\n"
            f"Make sure LM Studio is running at {lm_studio_url} with a model loaded."
        )

    run_id = "smoke_run_lmstudio"
    output_dir = str(tmp_path / "runs")
    (tmp_path / "runs").mkdir(exist_ok=True)

    await run_pipeline(run_id, config, None, output_dir)

    run_data = read_json(get_run_json_path(output_dir, run_id))
    status = run_data.get("status")

    assert status in ("completed", "completed_with_warnings"), (
        f"Run ended with status '{status}'. "
        f"Error: {run_data.get('error_message', 'none')}. "
        "Check LM Studio is running and has the model loaded."
    )

    run_dir = pathlib.Path(output_dir) / run_id
    proposals = load_proposals(run_dir)
    found_proposals = [p for p in proposals if p.state == "found" and p.proposed_value]

    assert len(found_proposals) >= 1, (
        f"Expected at least one non-empty proposal. Got: {len(found_proposals)} found proposals "
        f"out of {len(proposals)} total. Run status: {status}. "
        "This may indicate the model is not producing valid JSON output."
    )

    # Verify at least one proposal has reviewer-usable evidence
    evidence = load_evidence(run_dir)
    evidence_by_proposal = {}
    for ev in evidence:
        evidence_by_proposal.setdefault(ev.proposal_id, []).append(ev)

    proposals_with_evidence = [
        p for p in found_proposals
        if evidence_by_proposal.get(p.proposal_id)
    ]
    assert len(proposals_with_evidence) >= 1, (
        "At least one found proposal must have attached evidence for reviewer usability. "
        f"Found {len(found_proposals)} proposals but none had evidence."
    )

