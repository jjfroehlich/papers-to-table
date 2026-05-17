from __future__ import annotations

from pathlib import Path

import json

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.overnight import generate_overnight_report
from paper_optimizer.study import run_compare_mode, summarize


def test_summarize_rebuilds_compare_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)

    exp = tmp_path / "compare_exp"
    run_compare_mode(base_config, benches, exp)

    assert (exp / "results" / "results.csv").exists()

    summarize(base_config, exp)
    assert (exp / "plots" / "compare_primary_scores.png").exists()
    report_html = (exp / "report.html").read_text(encoding="utf-8")
    assert "Main Conclusion" in report_html


def test_generate_overnight_report_writes_aggregate_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)

    run_root = tmp_path / "runs" / "session_compare"
    experiment_dir = run_root / "experiment"
    run_compare_mode(base_config, benches, experiment_dir)

    overnight_dir = tmp_path / "overnight"
    overnight_dir.mkdir(parents=True)
    manifest_path = overnight_dir / "overnight_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "session_id": "session_001",
                "label": "nightly",
                "stages": [
                    {
                        "stage_name": "model_compare",
                        "run_name": "session_compare",
                        "run_root": str(run_root.resolve()),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report_path = generate_overnight_report(manifest_path)

    assert report_path == overnight_dir / "overview.html"
    assert (overnight_dir / "all_candidates.csv").exists()
    assert (overnight_dir / "all_candidates.json").exists()
    report_html = report_path.read_text(encoding="utf-8")
    assert "../runs/session_compare/experiment/report.html" in report_html
    assert "Stage Evolution" in report_html
    assert "Stage Decision Table" in report_html
    assert "Pipeline Evidence" in report_html
    assert "Stage-To-Stage Score Trajectory" in report_html
    assert "What This Shows" in report_html
    assert "How To Read It" in report_html
    assert "None" not in report_html
    payload = json.loads((overnight_dir / "all_candidates.json").read_text(encoding="utf-8"))
    assert payload
    assert payload[0]["stage_name"] == "model_compare"
    assert (overnight_dir / "pipeline_plots" / "pipeline_stage_trajectory.png").exists()


def test_generate_overnight_report_surfaces_manifest_failure_status(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)

    run_root = tmp_path / "runs" / "session_compare"
    experiment_dir = run_root / "experiment"
    run_compare_mode(base_config, benches, experiment_dir)

    overnight_dir = tmp_path / "overnight"
    overnight_dir.mkdir(parents=True)
    manifest_path = overnight_dir / "overnight_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "session_id": "session_001",
                "label": "nightly",
                "status": "failed",
                "completed_at": "2026-04-15T01:02:03Z",
                "stages": [
                    {
                        "stage_name": "model_compare",
                        "run_name": "session_compare",
                        "run_root": str(run_root.resolve()),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report_path = generate_overnight_report(manifest_path)

    report_html = report_path.read_text(encoding="utf-8")
    assert "Session Status" in report_html
    assert "failed" in report_html
    assert "2026-04-15T01:02:03Z" in report_html
