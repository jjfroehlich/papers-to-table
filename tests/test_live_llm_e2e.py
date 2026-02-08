from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.build_fixture_pdfs import build_fixture_pdf
from paper_table_agent.text.normalization import normalize_for_matching


def _latest_run_dir(runs_root: Path) -> Path:
    run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    assert run_dirs, f"No runs created in {runs_root}"
    return sorted(run_dirs)[-1]


@pytest.mark.live_llm
@pytest.mark.skipif(os.getenv("PTA_LIVE_LLM") != "1", reason="Live LLM tests require PTA_LIVE_LLM=1")
def test_live_llm_smoke_e2e(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pdf_dir = tmp_path / "pdfs"
    build_fixture_pdf(pdf_dir)

    table_path = tmp_path / "table.csv"
    schema_path = tmp_path / "schema.csv"
    table_path.write_text(
        "\n".join(
            [
                "Title,Authors,Year,Variants,Assay,UMIs,Predictive Feature",
                "Synthetic MPRA Study,Jane Doe; John Smith,2024,,,,",
            ]
        ),
        encoding="utf-8",
    )
    schema_path.write_text(
        "\n".join(
            [
                "column_name,description,group",
                "Variants,Total variants tested,core",
                "Assay,Assay type,core",
                "UMIs,Whether UMIs were used,core",
                "Predictive Feature,Key predictive feature,core",
            ]
        ),
        encoding="utf-8",
    )

    run_config = {
        "table_path": str(table_path),
        "schema_mode": "separate",
        "schema_path": str(schema_path),
        "schema_sheet_name": "schema",
        "pdf_folder": str(pdf_dir),
        "title_col": "Title",
        "authors_col": "Authors",
        "year_col": "Year",
        "verify_mode": False,
        "fast_mode": True,
        "max_success_mode": True,
        "provider": {
            "mode": "openai",
            "base_url": os.getenv("PTA_LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
            "api_key": os.getenv("PTA_LMSTUDIO_API_KEY"),
            "model_header": os.getenv("PTA_LIVE_MODEL", "qwen/qwen3-30b-a3b-2507"),
            "model_match": os.getenv("PTA_LIVE_MODEL", "qwen/qwen3-30b-a3b-2507"),
            "model_extract": os.getenv("PTA_LIVE_MODEL", "qwen/qwen3-30b-a3b-2507"),
            "model_query_helper": os.getenv("PTA_LIVE_MODEL", "qwen/qwen3-30b-a3b-2507"),
            "guided_json_mode": "off",
            "max_prompt_tokens": int(os.getenv("PTA_LIVE_CTX_WINDOW", "0")) or None,
            "timeout_s": float(os.getenv("PTA_LIVE_TIMEOUT_S", "120")),
            "read_timeout_s": float(os.getenv("PTA_LIVE_TIMEOUT_S", "180")),
        },
        "retrieval": {
            "top_k": 8,
            "rerank_k": 8,
            "max_context_chunks": 12,
            "max_context_tokens": 1200,
            "query_variants": 2,
            "use_query_expansion": True,
            "use_hyde": True,
            "rrf_k": 60,
            "use_dense": False,
            "embedding_backend": "tfidf",
            "reranker_backend": "tfidf",
            "use_reranker": False,
        },
        "extraction": {
            "groups": [],
            "examples_per_col": 1,
            "column_batch_size": 1,
            "max_chunks": 12,
            "retry_on_unclear": False,
            "whole_text_enabled": True,
            "whole_text_max_tokens": 1600,
        },
        "max_workers": 1,
    }
    config_path = tmp_path / "run_config.json"
    config_path.write_text(json.dumps(run_config, indent=2), encoding="utf-8")

    runs_root = Path(os.getenv("PAPER_TABLE_AGENT_RUNS_ROOT") or (tmp_path / "runs"))
    env = os.environ.copy()
    env["PAPER_TABLE_AGENT_RUNS_ROOT"] = str(runs_root)
    result = subprocess.run(
        [sys.executable, "-m", "paper_table_agent.cli", "run", "--config", str(config_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr

    run_dir = _latest_run_dir(runs_root)
    db_path = run_dir / "proposals.sqlite"
    parsed_dir = run_dir / "artifacts" / "parsed"
    parsed_files = list(parsed_dir.glob("*_pymupdf.json"))
    assert parsed_files, "Missing parsed text artifacts"
    page_text_payload = json.loads(parsed_files[0].read_text(encoding="utf-8"))
    page_text = page_text_payload.get("page_text") or []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT pdf_id, proposed_value, evidence_json, flags_json, status FROM proposals").fetchall()
        assert rows, "No proposals recorded"

    proposals_with_value = 0
    proposals_with_anchorable = 0
    found_unanchored = 0
    for row in rows:
        proposed_value = row["proposed_value"]
        evidence = json.loads(row["evidence_json"] or "[]")
        flags = json.loads(row["flags_json"] or "{}")
        status = row["status"]
        if flags.get("found_unanchored_downgraded"):
            found_unanchored += 1
        if proposed_value:
            proposals_with_value += 1
            has_evidence = bool(evidence) or int(flags.get("evidence_backfilled_count") or 0) > 0
            assert has_evidence, "Proposal with value missing evidence"
            anchorable = False
            for item in evidence:
                quote = (item.get("quote") or item.get("quote_text") or "").strip()
                assert item.get("pdf_id") != "retry"
                assert item.get("pdf_id") == row["pdf_id"]
                assert (item.get("quote_text") or "").strip()
                page = item.get("page")
                if quote and isinstance(page, int) and 0 < page <= len(page_text):
                    if quote in page_text[page - 1]:
                        anchorable = True
                highlight_status = item.get("highlight_status")
                assert highlight_status in {
                    "highlighted",
                    "failed",
                    "missing_quote_or_page",
                    "not_found",
                }
                if highlight_status == "highlighted":
                    rects = item.get("rects") or []
                    assert rects, "Highlighted evidence missing rects"
                    assert len(rects) < 20, "Highlight rect explosion detected"
                    assert len(quote) >= 3, "Highlight quote too short"
            if anchorable:
                proposals_with_anchorable += 1
        if status == "found" and proposed_value:
            normalized_value = normalize_for_matching(str(proposed_value))
            assert any(
                normalized_value and normalized_value in normalize_for_matching(str(item.get("quote") or ""))
                for item in evidence
            ), "Found proposal missing anchored value in quote"

    assert proposals_with_value >= 2, "Expected at least two proposed values"
    assert proposals_with_anchorable >= 1, "Expected at least one anchorable evidence quote"
    assert found_unanchored == 0, "Found-but-unanchored downgrades detected"

    run_report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))
    summary = run_report.get("summary", {})
    assert "evidence_coverage" in summary
    assert "highlighting" in summary
    assert "extraction_diagnostics" in summary
