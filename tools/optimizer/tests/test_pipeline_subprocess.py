from __future__ import annotations

import json
import sys
from pathlib import Path

from paper_optimizer.bundle import build_candidate_from_dict
from paper_optimizer.launch_eval import launch_eval_app, launch_external_eval_app
from paper_optimizer.launch_main import _build_real_main_command
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
    assert Path(result.eval_output_ref.get("artifact_paths", {}).get("gold_path", "")).as_posix().endswith("gold/dev.csv")
    assert Path(result.eval_output_ref.get("artifact_paths", {}).get("run_bundled_gold_path", "")).as_posix().endswith("inputs/gold_table.csv")
    assert Path(result.metadata.get("eval_summary", {}).get("gold_source", "")).as_posix().endswith("gold/dev.csv")


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


def test_launch_eval_passes_benchmark_eval_args(base_config: dict, tmp_path: Path) -> None:
    eval_script = tmp_path / "eval_assert_args.py"
    eval_script.write_text(
        """
import json
import sys
from pathlib import Path

args = sys.argv[1:]
if "--enable-text-exact-match-fast-path" not in args:
    sys.stderr.write("missing exact-match fast-path flag\\n")
    raise SystemExit(2)

run_dir = Path(args[args.index("--run") + 1])
out_dir = Path(args[args.index("--out") + 1])
run_id = json.loads((run_dir / "run.json").read_text(encoding="utf-8")).get("run_id", run_dir.name)
run_output_dir = out_dir / "per-run" / run_id
(out_dir / "compare").mkdir(parents=True, exist_ok=True)
run_output_dir.mkdir(parents=True, exist_ok=True)
summary_path = run_output_dir / "run_summary.json"
summary_path.write_text(
    json.dumps(
        {
            "run_id": run_id,
            "run_dir": str(run_dir.resolve()),
            "gold_source": args[args.index("--gold") + 1],
            "metrics": {"structured_accuracy": 1.0},
            "metadata": {},
            "contract_warnings": [],
            "join_diagnostics": [],
        }
    ),
    encoding="utf-8",
)
(run_output_dir / "scored_cells.jsonl").write_text("", encoding="utf-8")
print(
    json.dumps(
        {
            "schema_version": "paper_eval_cli.v1",
            "command": "evaluate",
            "status": "ok",
            "success": True,
            "output_dir": str(out_dir.resolve()),
            "per_run_dir": str((out_dir / "per-run").resolve()),
            "compare_dir": str((out_dir / "compare").resolve()),
            "run_count": 1,
            "run_ids": [run_id],
            "run_summary_paths": [str(summary_path.resolve())],
            "scored_cells_paths": [str((run_output_dir / "scored_cells.jsonl").resolve())],
            "judge_records_paths": [],
            "comparison_artifacts": {},
        },
        sort_keys=True,
    )
)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    main_run_dir = tmp_path / "run-dir"
    main_run_dir.mkdir(parents=True, exist_ok=True)
    (main_run_dir / "run.json").write_text(json.dumps({"run_id": "run-test"}), encoding="utf-8")

    config = dict(base_config)
    config["eval_app"] = dict(base_config["eval_app"])
    config["eval_app"]["command_prefix"] = [sys.executable, str(eval_script)]
    config["benchmarks"] = dict(base_config["benchmarks"])
    config["benchmarks"]["manifests"] = dict(base_config["benchmarks"]["manifests"])
    config["benchmarks"]["manifests"]["bench_dev"] = dict(base_config["benchmarks"]["manifests"]["bench_dev"])
    config["benchmarks"]["manifests"]["bench_dev"]["eval_args"] = ["--enable-text-exact-match-fast-path"]

    benchmark = load_benchmarks(config).manifests["bench_dev"]

    launch, summary = launch_eval_app(
        config,
        benchmark=benchmark,
        benchmark_id="bench_dev",
        main_run_ref_path=tmp_path / "main_run.json",
        main_run_dir=main_run_dir,
        out_dir=tmp_path / "eval-out",
    )

    assert launch.success
    assert "--enable-text-exact-match-fast-path" in launch.command
    assert summary["metrics"]["structured_accuracy"] == 1.0


def test_launch_external_eval_uses_absolute_paths(base_config: dict, tmp_path: Path, monkeypatch) -> None:
    eval_script = tmp_path / "eval_external_assert_paths.py"
    eval_script.write_text(
        """
import json
import sys
from pathlib import Path

args = sys.argv[1:]
external_path = Path(args[args.index("--external-result") + 1])
gold_path = Path(args[args.index("--gold") + 1])
out_dir = Path(args[args.index("--out") + 1])
schema_path = Path(args[args.index("--schema") + 1])
if not external_path.is_absolute():
    sys.stderr.write("external result path was not absolute\\n")
    raise SystemExit(2)
if not gold_path.is_absolute():
    sys.stderr.write("gold path was not absolute\\n")
    raise SystemExit(2)
if not out_dir.is_absolute():
    sys.stderr.write("out path was not absolute\\n")
    raise SystemExit(2)
if not schema_path.is_absolute():
    sys.stderr.write("schema path was not absolute\\n")
    raise SystemExit(2)
run_id = external_path.name
run_output_dir = out_dir / "per-run" / run_id
(out_dir / "compare").mkdir(parents=True, exist_ok=True)
run_output_dir.mkdir(parents=True, exist_ok=True)
summary_path = run_output_dir / "run_summary.json"
summary_path.write_text(
    json.dumps(
        {
            "run_id": run_id,
            "run_dir": str(external_path.resolve()),
            "gold_source": str(gold_path.resolve()),
            "metrics": {"structured_accuracy": 1.0},
            "metadata": {},
            "contract_warnings": [],
            "join_diagnostics": [],
        }
    ),
    encoding="utf-8",
)
(run_output_dir / "scored_cells.jsonl").write_text("", encoding="utf-8")
print(
    json.dumps(
        {
            "schema_version": "paper_eval_cli.v1",
            "command": "evaluate",
            "status": "ok",
            "success": True,
            "output_dir": str(out_dir.resolve()),
            "per_run_dir": str((out_dir / "per-run").resolve()),
            "compare_dir": str((out_dir / "compare").resolve()),
            "run_count": 1,
            "run_ids": [run_id],
            "run_summary_paths": [str(summary_path.resolve())],
            "scored_cells_paths": [str((run_output_dir / "scored_cells.jsonl").resolve())],
            "judge_records_paths": [],
            "comparison_artifacts": {},
        },
        sort_keys=True,
    )
)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    external_result = tmp_path / "external.csv"
    external_result.write_text("row_id,value\nrow-1,yes\n", encoding="utf-8")
    config = dict(base_config)
    config["eval_app"] = dict(base_config["eval_app"])
    config["eval_app"]["command_prefix"] = [sys.executable, str(eval_script)]
    benchmark = load_benchmarks(config).manifests["bench_dev"]

    monkeypatch.chdir(tmp_path)
    launch, summary = launch_external_eval_app(
        config,
        benchmark=benchmark,
        benchmark_id="bench_dev",
        external_result_path=external_result,
        out_dir=Path("relative-external-eval-out"),
    )

    assert launch.success
    assert Path(launch.command[launch.command.index("--external-result") + 1]).is_absolute()
    assert Path(launch.command[launch.command.index("--gold") + 1]).is_absolute()
    assert Path(launch.command[launch.command.index("--out") + 1]).is_absolute()
    assert summary["metrics"]["structured_accuracy"] == 1.0


def test_build_real_main_command_rewrites_generic_python_prefix_to_active_interpreter(base_config: dict) -> None:
    config = dict(base_config["main_app"])
    config["command_prefix"] = ["python", "-m", "backend.app.automation"]
    benchmark = load_benchmarks(base_config).manifests["bench_dev"]

    command, _working_dir = _build_real_main_command(config, Path("resolved.json"), benchmark)

    assert command[0] == sys.executable


def test_launch_eval_rewrites_generic_python_prefix_to_active_interpreter(base_config: dict, tmp_path: Path) -> None:
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
    config["eval_app"]["command_prefix"] = ["python", str(fail_script)]

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
    except ValueError:
        pass
    else:
        raise AssertionError("Expected launch_eval_app to raise ValueError for a non-JSON eval CLI failure")
