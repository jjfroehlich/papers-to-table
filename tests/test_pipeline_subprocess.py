from __future__ import annotations

import json
import sys
from pathlib import Path

from paper_optimizer.bundle import build_candidate_from_dict
from paper_optimizer.launch_eval import launch_eval_app
from paper_optimizer.pipeline import evaluate_candidate_once
from paper_optimizer.benchmarks import load_benchmarks


def test_single_candidate_pipeline(base_config: dict, tmp_path: Path) -> None:
    candidate = build_candidate_from_dict(
        "cand_0001",
        {
            "prompt_bundle_id": "prompt_a",
            "text_model_id": "text-model-a",
            "vision_model_id": None,
            "optimizer_knobs": {"retrieval_top_k": 5},
        },
        parent_candidate_id=None,
        round_index=None,
    )

    result = evaluate_candidate_once(
        base_config,
        experiment_dir=tmp_path / "exp",
        candidate=candidate,
        benchmark_id="bench_dev",
        study_type="compare",
        decision="not_promoted",
        reason="test",
    )

    assert result.candidate_id == "cand_0001"
    assert "correctness" in result.primary_metrics
    assert result.main_app_run_ref.get("run_id") == "run_cand_0001"
    assert result.candidate_status == "completed"
    assert result.eval_output_ref.get("summary_path")
    assert result.eval_output_ref.get("artifact_paths", {}).get("gold_path", "").endswith("inputs\\gold_table.csv")
    assert result.metadata.get("eval_summary", {}).get("gold_source", "").endswith("inputs\\gold_table.csv")


def test_launch_eval_reports_explicit_cli_failure(base_config: dict, tmp_path: Path) -> None:
    fail_script = tmp_path / "eval_fail.py"
    fail_script.write_text(
        "import sys\n"
        "sys.stderr.write(\"Gold wide-format inputs must include a 'row_id' column to support stable joins.\\n\")\n"
        "raise SystemExit(2)\n",
        encoding="utf-8",
    )

    main_run_dir = tmp_path / "run-dir"
    main_run_dir.mkdir(parents=True, exist_ok=True)
    (main_run_dir / "run.json").write_text(json.dumps({"run_id": "run-test"}), encoding="utf-8")

    config = dict(base_config)
    config["eval_app"] = dict(base_config["eval_app"])
    config["eval_app"]["command_prefix"] = [sys.executable, str(fail_script)]

    benchmark = load_benchmarks(config).manifests["bench_dev"]

    try:
        launch_eval_app(
            config,
            benchmark=benchmark,
            benchmark_id="bench_dev",
            main_run_ref_path=tmp_path / "main_run.json",
            main_run_dir=main_run_dir,
            out_dir=tmp_path / "eval-out",
        )
    except ValueError as exc:
        message = str(exc)
        assert "exit code 2" in message
        assert "row_id" in message
    else:
        raise AssertionError("Expected launch_eval_app to raise ValueError for a non-JSON eval CLI failure")
