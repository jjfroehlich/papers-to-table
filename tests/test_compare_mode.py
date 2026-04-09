from __future__ import annotations

import csv
import json
from pathlib import Path

from paper_optimizer.plotting import generate_compare_plots
from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.study import run_compare_mode


def test_compare_mode_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"
    run_compare_mode(base_config, benches, out)

    assert (out / "best_candidate.json").exists()
    assert (out / "compare_summary.json").exists()
    assert (out / "summary.json").exists()
    assert (out / "results" / "results.csv").exists()
    assert (out / "results" / "results.jsonl").exists()
    assert (out / "results" / "candidate_diagnostics.csv").exists()
    assert (out / "candidate_diagnostics.json").exists()
    assert (out / "plots" / "compare_primary_by_candidate.png").exists()
    assert (out / "plots" / "compare_correctness_vs_runtime.png").exists()
    assert (out / "plots" / "compare_primary_by_text_model.png").exists()
    assert (out / "plots" / "compare_primary_by_knob_retrieval_top_k.png").exists()

    best_candidate = json.loads((out / "best_candidate.json").read_text(encoding="utf-8"))
    compare_summary = json.loads((out / "compare_summary.json").read_text(encoding="utf-8"))
    assert best_candidate["candidate_id"]
    assert best_candidate["text_model_id"]
    assert best_candidate["prompt_bundle_id"]
    assert isinstance(best_candidate["optimizer_knobs_flat"], dict)
    assert compare_summary["winner"]["candidate_id"] == best_candidate["candidate_id"]
    assert compare_summary["candidate_count"] == 3


def test_compare_plots_keep_unscored_candidates(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "compare_exp"
    results_dir = experiment_dir / "results"
    results_dir.mkdir(parents=True)
    results_csv = results_dir / "results.csv"

    fieldnames = [
        "candidate_id",
        "candidate_status",
        "text_model_id",
        "prompt_bundle_id",
        "primary.correctness",
        "runtime_seconds",
        "guardrail.evidence_quality",
        "guardrail.null_count",
        "guardrail.failure_count",
    ]
    rows = [
        {
            "candidate_id": "cand_0001",
            "candidate_status": "completed",
            "text_model_id": "qwen/qwen3.5-9b",
            "prompt_bundle_id": "default",
            "primary.correctness": "",
            "runtime_seconds": "4905.39",
            "guardrail.evidence_quality": "",
            "guardrail.null_count": "9",
            "guardrail.failure_count": "9",
        },
        {
            "candidate_id": "cand_0002",
            "candidate_status": "completed",
            "text_model_id": "google/gemma-4-26b-a4b",
            "prompt_bundle_id": "default",
            "primary.correctness": "0.8333333333333334",
            "runtime_seconds": "843.5469",
            "guardrail.evidence_quality": "0.0",
            "guardrail.null_count": "9",
            "guardrail.failure_count": "9",
        },
    ]

    with results_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    generate_compare_plots(experiment_dir, "correctness")

    candidate_rows = list(
        csv.DictReader((experiment_dir / "plots" / "compare_primary_by_candidate.csv").open("r", encoding="utf-8", newline=""))
    )
    assert [row["candidate_id"] for row in candidate_rows] == ["cand_0001", "cand_0002"]
    assert candidate_rows[0]["candidate_label"] == "qwen/qwen3.5-9b"
    assert candidate_rows[0]["primary_score_display"] == "NA"
    assert candidate_rows[0]["score_available"] == "False"
    assert candidate_rows[1]["candidate_label"] == "google/gemma-4-26b-a4b"

    model_rows = list(
        csv.DictReader((experiment_dir / "plots" / "compare_primary_by_text_model.csv").open("r", encoding="utf-8", newline=""))
    )
    assert [row["text_model_id"] for row in model_rows] == ["google/gemma-4-26b-a4b", "qwen/qwen3.5-9b"]
    assert model_rows[1]["best_primary_score"] == ""
