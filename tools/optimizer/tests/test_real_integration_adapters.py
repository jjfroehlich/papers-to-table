from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.bundle import build_candidate_from_dict
from paper_optimizer.launch_eval import map_eval_summary_to_metric_groups
from paper_optimizer.launch_main import build_main_app_overlay, build_resolved_main_config
from paper_optimizer.pipeline import evaluate_candidate_once
from paper_optimizer.settings import normalize_config


def test_build_main_app_overlay_maps_candidate_into_main_config(base_config: dict) -> None:
    candidate = build_candidate_from_dict(
        "cand_0007",
        {
            "prompt_bundle_id": "default",
            "text_model_id": "text-model-b",
            "vision_model_id": None,
            "optimizer_knobs": {
                "retrieval_top_k": 6,
                "recall_rescue_enabled": True,
                "whole_document_mode": False,
                "text_temperature": 0.7,
                "text_max_tokens": 16384,
                "text_top_p": 0.8,
                "text_chat_template_kwargs": {"enable_thinking": False},
            },
        },
        parent_candidate_id=None,
        round_index=None,
    )

    overlay = build_main_app_overlay(base_config, candidate=candidate)

    assert overlay["eval_mode"] is True
    assert overlay["verify_mode"] is False
    assert overlay["prompt"]["bundle"] == "default"
    assert overlay["provider"]["text_model"]["model_id"] == "text-model-b"
    assert overlay["provider"]["vision_model"] is None
    assert overlay["retrieval"]["top_k"] == 6
    assert overlay["retrieval"]["recall_rescue_enabled"] is True
    assert overlay["retrieval"]["whole_document_mode"] is False
    assert overlay["provider"]["text_model"]["temperature"] == 0.7
    assert overlay["provider"]["text_model"]["max_tokens"] == 16384
    assert overlay["provider"]["text_model"]["top_p"] == 0.8
    assert overlay["provider"]["text_model"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_build_resolved_main_config_binds_benchmark_inputs(base_config: dict, tmp_path: Path) -> None:
    base_config = normalize_config(base_config)
    benches = load_benchmarks(base_config)
    benchmark_id = base_config["benchmark_suites"]["smoke_suite"]["benchmark_ids"][0]
    benchmark = benches.manifests[benchmark_id]
    candidate = build_candidate_from_dict(
        "cand_0008",
        base_config["compare_candidates"][0],
        parent_candidate_id=None,
        round_index=None,
    )

    _overlay, resolved = build_resolved_main_config(
        base_config,
        candidate=candidate,
        benchmark=benchmark,
        run_output_dir=tmp_path / "main_out",
    )

    assert resolved["table_path"] == benchmark.table_path
    assert resolved["schema_path"] == benchmark.schema_path
    assert resolved["pdf_dir"] == benchmark.pdf_dir
    assert resolved["output_dir"] == str((tmp_path / "main_out").resolve())
    assert resolved["eval_mode"] is True
    assert resolved["verify_mode"] is False


def test_map_eval_summary_groups_flat_metrics(base_config: dict) -> None:
    eval_summary = {
        "metrics": {
            "structured_accuracy": 0.81,
            "anchor_valid_rate": 0.92,
            "missing_proposal_count": 1,
            "join_failure_count": 0,
            "contract_warning_count": 2,
        }
    }

    primary, guardrail, diagnostic = map_eval_summary_to_metric_groups(eval_summary, base_config["eval_app"])

    assert primary == {"correctness": 0.81}
    assert guardrail == {
        "evidence_quality": 0.92,
        "null_count": 1.0,
        "failure_count": 0.0,
    }
    assert diagnostic == {"contract_warning_count": 2.0}


def test_evaluate_candidate_records_failure_when_main_artifacts_missing(base_config: dict, tmp_path: Path) -> None:
    broken_script = tmp_path / "broken_main.py"
    broken_script.write_text(
        "import json, sys\nprint(json.dumps({'schema_version':'main_app_automation.v1','run_id':'run_missing','status':'completed','is_terminal':True,'artifacts':{'run_dir': None, 'run_json_path': None}}))\n",
        encoding="utf-8",
    )
    config = json.loads(json.dumps(base_config))
    config["main_app"]["command_prefix"] = [config["main_app"]["command_prefix"][0], str(broken_script)]

    candidate = build_candidate_from_dict(
        "cand_0099",
        config["compare_candidates"][0],
        parent_candidate_id=None,
        round_index=None,
    )
    result = evaluate_candidate_once(
        config,
        experiment_dir=tmp_path / "exp",
        candidate=candidate,
        benchmark_id="bench_dev",
        study_type="compare",
        decision="not_promoted",
        reason="test_missing_artifacts",
    )

    assert result.candidate_status == "failed"
    assert result.decision_reason == "main_app_launch_failed"
    assert result.metadata["failure_stage"] == "main_app_launch"


def test_evaluate_candidate_surfaces_main_payload_error_detail(base_config: dict, tmp_path: Path) -> None:
    failed_run_dir = tmp_path / "failed_main_run"
    payload = {
        "schema_version": "main_app_automation.v1",
        "run_id": "run_failed",
        "status": "failed",
        "is_terminal": True,
        "error_message": "unresolved with strong evidence requires ambiguity/conflict reason",
        "artifacts": {
            "run_dir": str(failed_run_dir),
            "run_json_path": str(failed_run_dir / "run.json"),
        },
    }
    broken_script = tmp_path / "contract_failed_main.py"
    broken_script.write_text(
        f"import json, sys\nprint(json.dumps({payload!r}))\nsys.exit(2)\n",
        encoding="utf-8",
    )
    config = json.loads(json.dumps(base_config))
    config["main_app"]["command_prefix"] = [config["main_app"]["command_prefix"][0], str(broken_script)]

    candidate = build_candidate_from_dict(
        "cand_0100",
        config["compare_candidates"][0],
        parent_candidate_id=None,
        round_index=None,
    )
    result = evaluate_candidate_once(
        config,
        experiment_dir=tmp_path / "exp",
        candidate=candidate,
        benchmark_id="bench_dev",
        study_type="compare",
        decision="not_promoted",
        reason="test_main_payload_error",
    )

    assert result.candidate_status == "failed"
    assert result.decision_reason == "main_app_launch_failed"
    assert result.metadata["launch_error"] == payload["error_message"]
    assert result.unscored_reason_detail == payload["error_message"]


def test_config_normalization_builds_smoke_dev_holdout_suites(base_config: dict) -> None:
    config = normalize_config(base_config)

    assert config["benchmark_suites"]["smoke_suite"]["benchmark_ids"] == ["bench_smoke"]
    assert config["benchmark_suites"]["dev_suite"]["benchmark_ids"] == ["bench_dev"]
    assert config["benchmark_suites"]["holdout_suite"]["benchmark_ids"] == ["bench_holdout"]


def test_compare_candidate_results_capture_realish_refs(base_config: dict, tmp_path: Path) -> None:
    candidate = build_candidate_from_dict(
        "cand_0002",
        base_config["compare_candidates"][1],
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
        reason="adapter_contract_test",
    )

    assert result.candidate_status == "completed"
    assert result.main_app_run_ref["artifact_paths"]["resolved_main_config_path"]
    assert result.main_app_run_ref["run_path"]
    assert result.eval_output_ref["summary_path"]
    assert result.primary_metrics["correctness"] == pytest.approx(0.81)
    assert result.guardrail_metrics["evidence_quality"] == pytest.approx(0.9)
