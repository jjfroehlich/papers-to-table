from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.contracts import Candidate, CandidateResult
from paper_optimizer.plotting import generate_suite_plots
from paper_optimizer.settings import ConfigError, load_config
from paper_optimizer.study import run_compare_mode

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import papers_to_table  # noqa: E402


def _write_config(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "optimizer.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _add_suite(config: dict[str, Any], *, count: int = 2) -> dict[str, Any]:
    config = json.loads(json.dumps(config))
    config["compare_candidates"] = [config["compare_candidates"][0]]
    config["benchmark_suites"] = {
        "dev_suite": {
            "benchmark_ids": ["bench_dev", "bench_holdout"],
            "aggregation": {
                "method": "weighted_mean",
                "primary_metric": "correctness",
                "weights": {"bench_dev": 1.0, "bench_holdout": 3.0},
            },
        }
    }
    config["replicates"] = {"count": count, "continue_on_failure": True}
    return config


def _fake_result(
    config: dict[str, Any],
    candidate: Candidate,
    *,
    benchmark_id: str,
    score: float | None,
    status: str = "scored",
    runtime_seconds: float = 10.0,
) -> CandidateResult:
    scored = status in {"scored", "scored_degraded"} and score is not None
    return CandidateResult(
        schema_version=str(config["schema_version"]),
        experiment_id=str(config["experiment_id"]),
        study_type="compare",
        benchmark_id=benchmark_id,
        candidate_id=candidate.candidate_id,
        parent_candidate_id=candidate.parent_candidate_id,
        round_index=candidate.round_index,
        candidate_hash=f"hash-{candidate.candidate_id}",
        candidate_manifest_path="candidate.json",
        candidate_bundle_dir="candidate",
        prompt_bundle_id=candidate.prompt_bundle_id,
        text_model_id=candidate.text_model_id,
        vision_model_id=candidate.vision_model_id,
        optimizer_knobs_flat=dict(candidate.optimizer_knobs),
        primary_metrics={"correctness": score} if score is not None else {},
        guardrail_metrics={"evidence_quality": 1.0},
        diagnostic_metrics={"contract_warning_count": 0.0},
        scored=scored,
        score_status=status,
        unscored_reason=None if scored else status,
        runtime_seconds=runtime_seconds,
        runtime_metadata={"total_duration_seconds": runtime_seconds},
        candidate_status="completed" if status != "failed" else "failed",
        prompt_only_degraded_mode_used=status == "scored_degraded",
        extraction_contract_valid=status != "failed",
        main_app_run_ref={"run_path": f"runs/{candidate.candidate_id}/{benchmark_id}/main"},
        eval_output_ref={"summary_path": f"runs/{candidate.candidate_id}/{benchmark_id}/eval/run_summary.json"},
        metadata={"eval_summary": {"metrics": {}}},
    )


def test_suite_config_validates_and_preserves_order(tmp_path: Path, base_config: dict) -> None:
    cfg = load_config(_write_config(tmp_path, _add_suite(base_config)))

    assert cfg["benchmark_suites"]["dev_suite"]["benchmark_ids"] == ["bench_dev", "bench_holdout"]
    assert cfg["replicates"]["count"] == 2


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda cfg: cfg["benchmark_suites"]["dev_suite"]["benchmark_ids"].append("missing_bench"), "unknown benchmark id"),
        (lambda cfg: cfg["benchmark_suites"]["dev_suite"]["aggregation"]["weights"].update({"bench_smoke": 1.0}), "unknown suite benchmark id"),
        (lambda cfg: cfg["replicates"].update({"count": 0}), "replicates.count"),
    ],
)
def test_invalid_suite_and_replicate_config_fails_clearly(
    tmp_path: Path,
    base_config: dict,
    mutate: Any,
    message: str,
) -> None:
    payload = _add_suite(base_config)
    mutate(payload)

    with pytest.raises(ConfigError, match=message):
        load_config(_write_config(tmp_path, payload))


def test_suite_replicate_orchestration_and_artifacts(
    tmp_path: Path,
    base_config: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _add_suite(base_config, count=2)
    benchmarks = load_benchmarks(config)
    calls: list[tuple[str, str]] = []
    scores = {
        "bench_dev": [0.7, 0.9],
        "bench_holdout": [0.4, 0.8],
    }

    monkeypatch.setattr(
        "paper_optimizer.study._probe_candidate_structured_output_mode",
        lambda *args, **kwargs: {"probe_status": "error"},
    )

    def fake_evaluate(config_arg: dict[str, Any], *, candidate: Candidate, benchmark_id: str, **kwargs: Any) -> CandidateResult:
        calls.append((candidate.candidate_id, benchmark_id))
        score = scores[benchmark_id].pop(0)
        return _fake_result(config_arg, candidate, benchmark_id=benchmark_id, score=score, runtime_seconds=10.0 + len(calls))

    monkeypatch.setattr("paper_optimizer.study.evaluate_candidate_once", fake_evaluate)

    out_dir = tmp_path / "experiment"
    run_compare_mode(config, benchmarks, out_dir, suite_id="dev_suite")

    assert calls == [
        ("cand_0001", "bench_dev"),
        ("cand_0001", "bench_dev"),
        ("cand_0001", "bench_holdout"),
        ("cand_0001", "bench_holdout"),
    ]
    replicate_rows = [
        json.loads(line)
        for line in (out_dir / "results" / "replicate_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(replicate_rows) == 4
    assert {row["replicate_index"] for row in replicate_rows} == {1, 2}
    assert all(row["suite_id"] == "dev_suite" for row in replicate_rows)

    benchmark_summary = json.loads((out_dir / "results" / "benchmark_summary.json").read_text(encoding="utf-8"))["rows"]
    dev_row = next(row for row in benchmark_summary if row["benchmark_id"] == "bench_dev")
    assert dev_row["primary_metric_mean"] == pytest.approx(0.8)
    assert dev_row["primary_metric_sd"] == pytest.approx(0.1414213562)
    assert dev_row["primary_metric_sem"] == pytest.approx(0.1)
    assert dev_row["n_total"] == 2
    assert dev_row["n_scored"] == 2

    suite_summary = json.loads((out_dir / "results" / "suite_summary.json").read_text(encoding="utf-8"))["rows"][0]
    assert suite_summary["suite_primary_metric_weighted_mean"] == pytest.approx(0.65)
    assert suite_summary["benchmark_coverage"] == 1.0


def test_one_benchmark_suite_with_one_replicate_uses_canonical_outputs(
    tmp_path: Path,
    base_config: dict,
) -> None:
    config = json.loads(json.dumps(base_config))
    config["compare_candidates"] = [config["compare_candidates"][0]]
    config["compare"]["suite_id"] = "dev_suite"
    config["replicates"]["count"] = 1
    benches = load_benchmarks(config)

    out_dir = tmp_path / "experiment"
    run_compare_mode(config, benches, out_dir)

    replicate_rows = [
        json.loads(line)
        for line in (out_dir / "results" / "replicate_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    benchmark_rows = json.loads((out_dir / "results" / "benchmark_summary.json").read_text(encoding="utf-8"))["rows"]
    suite_rows = json.loads((out_dir / "results" / "suite_summary.json").read_text(encoding="utf-8"))["rows"]

    assert len(replicate_rows) == 1
    assert replicate_rows[0]["suite_id"] == "dev_suite"
    assert replicate_rows[0]["replicate_index"] == 1
    assert benchmark_rows[0]["suite_id"] == "dev_suite"
    assert benchmark_rows[0]["n_total"] == 1
    assert suite_rows[0]["suite_id"] == "dev_suite"
    assert "Suite Ranking" in (out_dir / "report.html").read_text(encoding="utf-8")


def test_failed_and_single_replicates_remain_visible(
    tmp_path: Path,
    base_config: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _add_suite(base_config, count=1)
    benchmarks = load_benchmarks(config)
    monkeypatch.setattr(
        "paper_optimizer.study._probe_candidate_structured_output_mode",
        lambda *args, **kwargs: {"probe_status": "error"},
    )

    def fake_evaluate(config_arg: dict[str, Any], *, candidate: Candidate, benchmark_id: str, **kwargs: Any) -> CandidateResult:
        if benchmark_id == "bench_dev":
            return _fake_result(config_arg, candidate, benchmark_id=benchmark_id, score=None, status="failed")
        return _fake_result(config_arg, candidate, benchmark_id=benchmark_id, score=0.5, status="scored_degraded")

    monkeypatch.setattr("paper_optimizer.study.evaluate_candidate_once", fake_evaluate)

    out_dir = tmp_path / "experiment"
    run_compare_mode(config, benchmarks, out_dir, suite_id="dev_suite")

    benchmark_rows = json.loads((out_dir / "results" / "benchmark_summary.json").read_text(encoding="utf-8"))["rows"]
    failed_row = next(row for row in benchmark_rows if row["benchmark_id"] == "bench_dev")
    degraded_row = next(row for row in benchmark_rows if row["benchmark_id"] == "bench_holdout")
    assert failed_row["n_failed"] == 1
    assert failed_row["primary_metric_sd"] is None
    assert "single_replicate_no_variance_estimate" in failed_row["trust_caveats"]
    assert degraded_row["n_degraded"] == 1

    report_html = (out_dir / "report.html").read_text(encoding="utf-8")
    assert "Suite Ranking" in report_html
    assert "Benchmark And Replicate Stability" in report_html
    assert "Failed replicates" in report_html
    assert "degraded replicates" in report_html
    assert "Caveats" in report_html
    assert "Nested Artifacts" in report_html
    assert "n = 1" in report_html


def test_suite_plots_include_replicate_variability_artifacts(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "suite_exp"
    results_dir = experiment_dir / "results"
    results_dir.mkdir(parents=True)

    suite_fieldnames = [
        "candidate_id",
        "suite_id",
        "suite_primary_metric_weighted_mean",
        "benchmark_coverage",
        "failed_replicate_count",
        "degraded_replicate_count",
        "trust_caveats",
    ]
    with (results_dir / "suite_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = json  # placeholder to keep context stable

    with (results_dir / "suite_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=suite_fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "cand_0001",
                "suite_id": "dev_suite",
                "suite_primary_metric_weighted_mean": "0.82",
                "benchmark_coverage": "1.0",
                "failed_replicate_count": "0",
                "degraded_replicate_count": "0",
                "trust_caveats": "[]",
            }
        )

    benchmark_fieldnames = [
        "candidate_id",
        "suite_id",
        "benchmark_id",
        "primary_metric_mean",
        "primary_metric_sem",
        "n_total",
        "n_scored",
    ]
    with (results_dir / "benchmark_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=benchmark_fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "cand_0001",
                "suite_id": "dev_suite",
                "benchmark_id": "bench_dev",
                "primary_metric_mean": "0.81",
                "primary_metric_sem": "0.05",
                "n_total": "3",
                "n_scored": "3",
            }
        )
        writer.writerow(
            {
                "candidate_id": "cand_0001",
                "suite_id": "dev_suite",
                "benchmark_id": "bench_other",
                "primary_metric_mean": "0.78",
                "primary_metric_sem": "0.02",
                "n_total": "3",
                "n_scored": "3",
            }
        )

    with (results_dir / "replicate_results.csv").open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_id",
                "suite_id",
                "benchmark_id",
                "replicate_index",
                "score_status",
                "candidate_status",
                "primary.correctness",
                "runtime_seconds",
                "prompt_only_degraded_mode_used",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "cand_0001",
                "suite_id": "dev_suite",
                "benchmark_id": "bench_dev",
                "replicate_index": "1",
                "score_status": "scored",
                "candidate_status": "completed",
                "primary.correctness": "0.8",
                "runtime_seconds": "10.0",
                "prompt_only_degraded_mode_used": "false",
            }
        )

    generate_suite_plots(experiment_dir, "correctness")

    assert (experiment_dir / "plots" / "suite_benchmark_breakdown.png").exists()
    plot_rows = list(
        __import__("csv").DictReader(
            (experiment_dir / "plots" / "suite_benchmark_breakdown.csv").open("r", encoding="utf-8", newline="")
        )
    )
    assert plot_rows[0]["primary_metric_sem"] == "0.05"
    assert plot_rows[1]["primary_metric_sem"] == "0.02"


def test_wrapper_compare_command_resolves_suite_and_replicates(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> int:
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        return 0

    monkeypatch.setattr(papers_to_table, "_run", fake_run)
    args = type(
        "Args",
        (),
        {
            "config": None,
            "out": None,
            "suite": "dev_suite",
            "replicates": 3,
        },
    )()

    assert papers_to_table.cmd_optimizer_compare(args) == 0

    cmd = captured["cmd"]
    assert cmd[:4] == [sys.executable, "-m", "paper_optimizer.cli", "optimize"]
    assert ["--suite", "dev_suite"] == cmd[cmd.index("--suite") : cmd.index("--suite") + 2]
    assert ["--replicates", "3"] == cmd[cmd.index("--replicates") : cmd.index("--replicates") + 2]
