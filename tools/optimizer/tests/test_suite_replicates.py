from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.contracts import Candidate, CandidateResult
from paper_optimizer.plotting import generate_suite_plots
from paper_optimizer.results import ResultsWriter
from paper_optimizer.settings import ConfigError, load_config
from paper_optimizer.study import (
    _evaluate_external_result_with_suite_and_replicates,
    _external_candidate_id,
    _external_replicates,
    _suite_plan,
    run_compare_mode,
)
from paper_optimizer.utils import EXTERNAL_CANDIDATE_ID_MAX_LENGTH, SAFE_IDENTIFIER_RE


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


def test_suite_plots_include_replicate_variability_artifacts(tmp_path: Path, monkeypatch) -> None:
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
                "candidate_id": "ext_gold",
                "suite_id": "dev_suite",
                "benchmark_id": "bench_dev",
                "primary_metric_mean": "1.0",
                "primary_metric_sem": "0.0",
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

    import paper_optimizer.plotting as plotting_module

    original_save_plot = plotting_module._save_plot
    captured_ylim: tuple[float, float] | None = None
    captured_mean_labels: list[tuple[str, tuple[float, float]]] = []

    def capture_score_distribution_ylim(path: Path) -> None:
        nonlocal captured_ylim, captured_mean_labels
        if path.name == "suite_replicate_score_distribution.png":
            axes = plotting_module.plt.gca()
            captured_ylim = axes.get_ylim()
            captured_mean_labels = [
                (label.get_text(), label.get_position())
                for label in axes.texts
                if label.get_gid() == "boxplot-mean-label"
            ]
        original_save_plot(path)

    monkeypatch.setattr(plotting_module, "_save_plot", capture_score_distribution_ylim)
    generate_suite_plots(experiment_dir, "correctness")

    assert (experiment_dir / "plots" / "suite_benchmark_breakdown.png").exists()
    plot_rows = list(
        __import__("csv").DictReader(
            (experiment_dir / "plots" / "suite_benchmark_breakdown.csv").open("r", encoding="utf-8", newline="")
        )
    )
    assert plot_rows[0]["primary_metric_sem"] == "0.05"
    assert plot_rows[1]["primary_metric_sem"] == "0.0"
    assert plot_rows[2]["primary_metric_sem"] == "0.02"
    breakdown_rows = list(
        __import__("csv").DictReader(
            (experiment_dir / "plots" / "suite_benchmark_breakdown_by_benchmark.csv").open("r", encoding="utf-8", newline="")
        )
    )
    assert breakdown_rows[0]["benchmark_id"] == "bench_dev"
    assert breakdown_rows[0]["best_primary_score"] == "0.81"
    assert breakdown_rows[0]["external_control_count"] == "1"
    assert captured_ylim is not None
    assert captured_ylim[0] == 0.0
    assert captured_ylim[1] > 0.8
    assert captured_mean_labels == [("0.80", (1, pytest.approx(0.82, abs=0.01)))]
    assert captured_ylim[1] > captured_mean_labels[0][1][1]


def test_external_replicates_load_adjacent_runtime_file(tmp_path: Path) -> None:
    result_root = tmp_path / "external_tool"
    rep1 = result_root / "rep1"
    rep2 = result_root / "rep2"
    rep1.mkdir(parents=True)
    rep2.mkdir(parents=True)
    (rep1 / "bench_filled.csv").write_text("row_id,value\nrow-1,yes\n", encoding="utf-8")
    (rep2 / "bench_filled.csv").write_text("row_id,value\nrow-1,no\n", encoding="utf-8")
    (result_root / "runtimes.json").write_text(
        json.dumps(
            {
                "runtime_scope": "suite_replicate",
                "unit": "seconds",
                "replicates": [
                    {"replicate_index": 1, "runtime_seconds": 1179},
                    {"replicate_index": 2, "runtime_seconds": 912},
                ],
            }
        ),
        encoding="utf-8",
    )

    replicates = _external_replicates(
        {
            "label": "external_tool",
            "replicates": [
                {"replicate_index": 1, "path": str(rep1 / "bench_filled.csv")},
                {"replicate_index": 2, "path": str(rep2 / "bench_filled.csv")},
            ],
        }
    )

    assert replicates[0]["runtime_seconds"] == 1179.0
    assert replicates[1]["runtime_seconds"] == 912.0
    assert replicates[0]["runtime_scope"] == "suite_replicate"


def test_external_candidate_id_fallback_is_path_safe_and_stable() -> None:
    long_label = "codex_gpt_pro_5_5_extra_high_jjfroehlich_papers_to_table_agent_kit"

    candidate_id = _external_candidate_id({"label": long_label})

    assert candidate_id == _external_candidate_id({"label": long_label})
    assert candidate_id.startswith("external_")
    assert len(candidate_id) <= EXTERNAL_CANDIDATE_ID_MAX_LENGTH
    assert SAFE_IDENTIFIER_RE.fullmatch(candidate_id)
    assert candidate_id != f"external_{long_label}"


def test_external_suite_replicate_runtime_is_counted_once_per_replicate(
    tmp_path: Path,
    base_config: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _add_suite(base_config, count=2)
    plan = _suite_plan(config, "dev_suite")
    result_root = tmp_path / "external_tool"
    for replicate_index in [1, 2]:
        rep_dir = result_root / f"rep{replicate_index}"
        rep_dir.mkdir(parents=True)
        (rep_dir / "bench_filled.csv").write_text("row_id,value\nrow-1,yes\n", encoding="utf-8")
    (result_root / "runtimes.json").write_text(
        json.dumps(
            {
                "runtime_scope": "suite_replicate",
                "replicates": [
                    {"replicate_index": 1, "runtime_seconds": 1179},
                    {"replicate_index": 2, "runtime_seconds": 912},
                ],
            }
        ),
        encoding="utf-8",
    )
    external_results_by_benchmark = {
        benchmark_id: {
            "label": "external_tool",
            "system": "external_tool",
            "replicates": [
                {"replicate_index": 1, "path": str(result_root / "rep1" / "bench_filled.csv")},
                {"replicate_index": 2, "path": str(result_root / "rep2" / "bench_filled.csv")},
            ],
        }
        for benchmark_id in plan.benchmark_ids
    }

    def _fake_external_once(*args: Any, **kwargs: Any) -> CandidateResult:
        external_result = kwargs["external_result"]
        candidate = Candidate(
            candidate_id=external_result["candidate_id"],
            prompt_bundle_id="external_result",
            text_model_id="external_tool",
            vision_model_id=None,
            optimizer_knobs={},
        )
        return _fake_result(
            config,
            candidate,
            benchmark_id=kwargs["benchmark_id"],
            score=0.8,
            runtime_seconds=float(external_result["runtime_seconds"]),
        )

    monkeypatch.setattr("paper_optimizer.study.evaluate_external_result_once", _fake_external_once)

    result = _evaluate_external_result_with_suite_and_replicates(
        config,
        ResultsWriter(tmp_path / "experiment"),
        experiment_dir=tmp_path / "experiment",
        plan=plan,
        external_results_by_benchmark=external_results_by_benchmark,
        study_type="compare",
    )

    assert result.runtime_seconds == 2091.0
