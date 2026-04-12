from __future__ import annotations

from pathlib import Path

import json

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.overnight import generate_overnight_report
from paper_optimizer.search_space import load_search_space
from paper_optimizer.study import run_optimize_mode, summarize, validate_best
from paper_optimizer.utils import read_json


def test_holdout_validation_and_summarize(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    search_space = load_search_space(base_config)

    exp = tmp_path / "optimize_exp"
    run_optimize_mode(base_config, benches, search_space, exp)

    holdout = tmp_path / "holdout_exp"
    validate_best(base_config, benches, exp, holdout)
    assert (holdout / "results" / "results.csv").exists()
    assert read_json(exp / "summary.json")["holdout_validation"]["ran"] is True

    summarize(base_config, exp)
    assert (exp / "plots" / "optimize_best_by_round.png").exists()
    report_html = (exp / "report.html").read_text(encoding="utf-8")
    assert "Main Conclusion" in report_html


def test_generate_overnight_report_writes_aggregate_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    search_space = load_search_space(base_config)

    run_root = tmp_path / "runs" / "session_compare"
    experiment_dir = run_root / "experiment"
    run_optimize_mode(base_config, benches, search_space, experiment_dir)

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
                        "stage_name": "optimize",
                        "run_name": "session_compare",
                        "run_root": str(run_root.resolve()),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report_path = generate_overnight_report(manifest_path)

    assert report_path == overnight_dir / "report.html"
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
    assert payload[0]["stage_name"] == "optimize"
    assert (overnight_dir / "pipeline_plots" / "pipeline_stage_trajectory.png").exists()
