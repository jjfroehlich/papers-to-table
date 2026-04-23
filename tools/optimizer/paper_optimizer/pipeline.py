from __future__ import annotations

from pathlib import Path
from typing import Any

from .benchmarks import load_benchmarks
from .bundle import candidate_hash, materialize_candidate_bundle
from .contracts import Candidate, CandidateResult
from .launch_eval import launch_eval_app, map_eval_summary_to_metric_groups
from .launch_main import LaunchError, launch_main_app
from .utils import flatten_dict, read_json
from .validation import validate_eval_summary_contract, validate_main_launch_contract


def _score_status(*, candidate_status: str, scored: bool, prompt_only_degraded_mode_used: bool) -> str:
    if candidate_status != "completed":
        return "failed"
    if not scored:
        return "unscored"
    if prompt_only_degraded_mode_used:
        return "scored_degraded"
    return "scored"


def _read_json_if_exists(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def _load_main_reviewer_summary(main_launch: Any | None) -> dict[str, Any]:
    if main_launch is None:
        return {}
    artifact_paths = main_launch.artifact_paths if isinstance(main_launch.artifact_paths, dict) else {}
    reviewer_summary_path = artifact_paths.get("reviewer_summary_path")
    if isinstance(reviewer_summary_path, str):
        return _read_json_if_exists(Path(reviewer_summary_path))
    run_path = main_launch.run_path if isinstance(main_launch.run_path, str) else None
    if run_path:
        return _read_json_if_exists(Path(run_path) / "summaries" / "reviewer_summary.json")
    return {}


def _load_main_run_artifacts(main_launch: Any | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if main_launch is None or not isinstance(main_launch.run_path, str):
        return {}, {}
    run_dir = Path(main_launch.run_path)
    return (
        _read_json_if_exists(run_dir / "diagnostics" / "provider_request_counts.json"),
        _read_json_if_exists(run_dir / "diagnostics" / "run_stats.json"),
    )


def _coalesce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    return None


def _failure_result(
    config: dict[str, Any],
    *,
    candidate: Candidate,
    benchmark_id: str,
    study_type: str,
    decision: str,
    reason: str,
    candidate_dir: Path,
    main_launch: Any | None = None,
    eval_launch: Any | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> CandidateResult:
    candidate_manifest_path = candidate_dir / "candidate.json"
    metadata = dict(extra_metadata or {})
    if main_launch is not None:
        metadata.update(
            {
                "main_stdout": main_launch.stdout,
                "main_stderr": main_launch.stderr,
            }
        )
    if eval_launch is not None:
        metadata.update(
            {
                "eval_stdout": eval_launch.stdout,
                "eval_stderr": eval_launch.stderr,
            }
        )
    reviewer_summary = _load_main_reviewer_summary(main_launch)
    provider_request_counts, run_stats = _load_main_run_artifacts(main_launch)
    runtime_total = (
        (main_launch.duration_seconds if main_launch is not None else 0.0)
        + (eval_launch.duration_seconds if eval_launch is not None else 0.0)
    )

    return CandidateResult(
        schema_version=str(config["schema_version"]),
        experiment_id=str(config["experiment_id"]),
        study_type=study_type,
        benchmark_id=benchmark_id,
        candidate_id=candidate.candidate_id,
        parent_candidate_id=candidate.parent_candidate_id,
        round_index=candidate.round_index,
        candidate_hash=candidate_hash(candidate),
        candidate_manifest_path=str(candidate_manifest_path.resolve()),
        candidate_bundle_dir=str(candidate_dir.resolve()),
        prompt_bundle_id=candidate.prompt_bundle_id,
        text_model_id=candidate.text_model_id,
        vision_model_id=candidate.vision_model_id,
        optimizer_knobs_flat=flatten_dict(candidate.optimizer_knobs),
        primary_metrics={},
        guardrail_metrics={},
        diagnostic_metrics={},
        scored=False,
        score_status="failed",
        unscored_reason=reason,
        unscored_reason_detail=str(metadata.get("launch_error") or reason),
        runtime_seconds=runtime_total if runtime_total > 0 else None,
        runtime_metadata={
            "main_app_duration_seconds": main_launch.duration_seconds if main_launch is not None else None,
            "eval_duration_seconds": eval_launch.duration_seconds if eval_launch is not None else None,
            "total_duration_seconds": runtime_total,
            "provider_request_counts": (provider_request_counts.get("counts") if isinstance(provider_request_counts.get("counts"), dict) else {}),
            "run_stats_counters": (run_stats.get("counters") if isinstance(run_stats.get("counters"), dict) else {}),
        },
        started_at=(main_launch.started_at if main_launch is not None else ""),
        ended_at=(
            eval_launch.ended_at
            if eval_launch is not None
            else (main_launch.ended_at if main_launch is not None else "")
        ),
        candidate_status="failed",
        promotion_decision=decision,
        decision_reason=reason,
        structured_output_mode=reviewer_summary.get("structured_output_mode"),
        structured_output_reason=reviewer_summary.get("structured_output_reason"),
        prompt_only_degraded_mode_used=bool(reviewer_summary.get("prompt_only_degraded_mode_used", False)),
        parse_repair_used=bool(reviewer_summary.get("parse_repair_used", False)),
        extraction_contract_valid=_coalesce_bool(reviewer_summary.get("extraction_contract_valid")),
        extraction_contract_warnings=list(reviewer_summary.get("extraction_contract_warnings", []) or []),
        retrieval_mode=reviewer_summary.get("retrieval_mode"),
        retrieval_top_k=reviewer_summary.get("retrieval_top_k"),
        recall_rescue_enabled=_coalesce_bool(reviewer_summary.get("recall_rescue_enabled")),
        whole_document_mode=_coalesce_bool(reviewer_summary.get("whole_document_mode")),
        whole_document_max_chars=reviewer_summary.get("whole_document_max_chars"),
        recall_rescue_used=_coalesce_bool(reviewer_summary.get("recall_rescue_used")),
        recall_rescue_invocation_count=reviewer_summary.get("recall_rescue_invocation_count"),
        whole_document_used_count=((reviewer_summary.get("retrieval_provenance") or {}).get("whole_document_used_count") if isinstance(reviewer_summary.get("retrieval_provenance"), dict) else None),
        main_app_run_ref={
            "run_id": main_launch.run_id if main_launch is not None else None,
            "run_path": main_launch.run_path if main_launch is not None else None,
            "output_path": main_launch.output_path if main_launch is not None else None,
            "return_code": main_launch.return_code if main_launch is not None else None,
            "payload": main_launch.payload if main_launch is not None else {},
            "artifact_paths": main_launch.artifact_paths if main_launch is not None else {},
        },
        eval_output_ref={
            "output_path": eval_launch.output_path if eval_launch is not None else None,
            "return_code": eval_launch.return_code if eval_launch is not None else None,
            "summary_path": eval_launch.summary_path if eval_launch is not None else None,
            "payload": eval_launch.payload if eval_launch is not None else {},
            "artifact_paths": eval_launch.artifact_paths if eval_launch is not None else {},
        },
        metadata={
            **metadata,
            "provider_request_counts": provider_request_counts,
            "run_stats": run_stats,
        },
    )


def evaluate_candidate_once(
    config: dict[str, Any],
    *,
    experiment_dir: Path,
    candidate: Candidate,
    benchmark_id: str,
    study_type: str,
    decision: str,
    reason: str,
) -> CandidateResult:
    candidate_dir = materialize_candidate_bundle(experiment_dir, candidate, benchmark_id)
    candidate_manifest_path = candidate_dir / "candidate.json"
    benchmarks = load_benchmarks(config)
    benchmark = benchmarks.manifests[benchmark_id]

    main_out = experiment_dir / "runs" / candidate.candidate_id / "main"
    eval_out = experiment_dir / "runs" / candidate.candidate_id / "eval"

    try:
        main_launch = launch_main_app(
            config,
            candidate=candidate,
            candidate_manifest_path=candidate_manifest_path,
            benchmark=benchmark,
            benchmark_id=benchmark_id,
            out_dir=main_out,
        )
    except (LaunchError, ValueError) as exc:
        return _failure_result(
            config,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type=study_type,
            decision=decision,
            reason=reason,
            candidate_dir=candidate_dir,
            extra_metadata={"launch_error": str(exc), "failure_stage": "main_app_launch"},
        )

    main_ref_path = main_out / config["main_app"].get("run_reference_file", "main_run.json")
    if not main_launch.success or not main_launch.run_path:
        return _failure_result(
            config,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type=study_type,
            decision=decision,
            reason="main_app_launch_failed",
            candidate_dir=candidate_dir,
            main_launch=main_launch,
            extra_metadata={"failure_stage": "main_app_launch"},
        )

    main_contract_errors = validate_main_launch_contract(candidate, main_launch)
    if main_contract_errors:
        return _failure_result(
            config,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type=study_type,
            decision=decision,
            reason="main_app_contract_invalid",
            candidate_dir=candidate_dir,
            main_launch=main_launch,
            extra_metadata={
                "failure_stage": "main_app_contract",
                "contract_errors": main_contract_errors,
                "deterministic_gate": {"stage": "main_app_contract", "passed": False, "failures": main_contract_errors},
            },
        )

    try:
        eval_launch, eval_summary = launch_eval_app(
            config,
            benchmark=benchmark,
            benchmark_id=benchmark_id,
            main_run_ref_path=main_ref_path,
            main_run_dir=Path(main_launch.run_path),
            out_dir=eval_out,
        )
    except ValueError as exc:
        return _failure_result(
            config,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type=study_type,
            decision=decision,
            reason="eval_launch_failed",
            candidate_dir=candidate_dir,
            main_launch=main_launch,
            extra_metadata={"launch_error": str(exc), "failure_stage": "eval_launch"},
        )

    if not eval_launch.success or not eval_summary:
        return _failure_result(
            config,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type=study_type,
            decision=decision,
            reason="eval_launch_failed",
            candidate_dir=candidate_dir,
            main_launch=main_launch,
            eval_launch=eval_launch,
            extra_metadata={"failure_stage": "eval_launch"},
        )

    eval_contract_errors = validate_eval_summary_contract(config, eval_launch, eval_summary)
    if eval_contract_errors:
        return _failure_result(
            config,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type=study_type,
            decision=decision,
            reason="eval_contract_invalid",
            candidate_dir=candidate_dir,
            main_launch=main_launch,
            eval_launch=eval_launch,
            extra_metadata={
                "failure_stage": "eval_contract",
                "contract_errors": eval_contract_errors,
                "deterministic_gate": {"stage": "eval_contract", "passed": False, "failures": eval_contract_errors},
            },
        )

    primary_metrics, guardrail_metrics, diagnostic_metrics = map_eval_summary_to_metric_groups(eval_summary, config["eval_app"])

    provider_request_counts, run_stats = _load_main_run_artifacts(main_launch)
    runtime_seconds = (main_launch.duration_seconds + eval_launch.duration_seconds) or None
    runtime_metadata = {
        "main_app_duration_seconds": main_launch.duration_seconds,
        "eval_duration_seconds": eval_launch.duration_seconds,
        "total_duration_seconds": main_launch.duration_seconds + eval_launch.duration_seconds,
        "provider_request_counts": (provider_request_counts.get("counts") if isinstance(provider_request_counts.get("counts"), dict) else {}),
        "run_stats_counters": (run_stats.get("counters") if isinstance(run_stats.get("counters"), dict) else {}),
    }
    eval_metadata = eval_summary.get("metadata", {}) if isinstance(eval_summary.get("metadata"), dict) else {}
    reviewer_summary = _load_main_reviewer_summary(main_launch)
    scored = bool(eval_summary.get("scored", primary_metrics.get(config["acceptance"]["primary_metric"]) is not None))
    unscored_reason = eval_summary.get("unscored_reason")
    unscored_reason_detail = eval_summary.get("unscored_reason_detail")
    if "page_count" in eval_metadata:
        runtime_metadata["page_count"] = eval_metadata.get("page_count")
    degraded_for_structure = bool(reviewer_summary.get("prompt_only_degraded_mode_used", False)) or reviewer_summary.get("structured_output_mode") == "none"
    if reviewer_summary.get("extraction_contract_valid") is False:
        degraded_for_structure = True
    score_status = _score_status(
        candidate_status="completed",
        scored=scored,
        prompt_only_degraded_mode_used=degraded_for_structure,
    )
    primary_metric_name = str(config["acceptance"]["primary_metric"])
    if scored and primary_metrics.get(primary_metric_name) is None:
        scored = False
        score_status = "unscored"
        unscored_reason = "metric_projection_failure"
        unscored_reason_detail = f"configured primary metric '{primary_metric_name}' was not projected from the eval summary"

    return CandidateResult(
        schema_version=str(config["schema_version"]),
        experiment_id=str(config["experiment_id"]),
        study_type=study_type,
        benchmark_id=benchmark_id,
        candidate_id=candidate.candidate_id,
        parent_candidate_id=candidate.parent_candidate_id,
        round_index=candidate.round_index,
        candidate_hash=candidate_hash(candidate),
        candidate_manifest_path=str(candidate_manifest_path.resolve()),
        candidate_bundle_dir=str(candidate_dir.resolve()),
        prompt_bundle_id=candidate.prompt_bundle_id,
        text_model_id=candidate.text_model_id,
        vision_model_id=candidate.vision_model_id,
        optimizer_knobs_flat=flatten_dict(candidate.optimizer_knobs),
        primary_metrics=primary_metrics,
        guardrail_metrics=guardrail_metrics,
        diagnostic_metrics=diagnostic_metrics,
        scored=scored,
        score_status=score_status,
        unscored_reason=unscored_reason,
        unscored_reason_detail=unscored_reason_detail,
        runtime_seconds=runtime_seconds,
        runtime_metadata=runtime_metadata,
        started_at=main_launch.started_at,
        ended_at=eval_launch.ended_at,
        candidate_status="completed",
        promotion_decision=decision,
        decision_reason=reason,
        structured_output_mode=reviewer_summary.get("structured_output_mode"),
        structured_output_reason=reviewer_summary.get("structured_output_reason"),
        prompt_only_degraded_mode_used=bool(reviewer_summary.get("prompt_only_degraded_mode_used", False)),
        parse_repair_used=bool(reviewer_summary.get("parse_repair_used", False)),
        extraction_contract_valid=_coalesce_bool(reviewer_summary.get("extraction_contract_valid")),
        extraction_contract_warnings=list(reviewer_summary.get("extraction_contract_warnings", []) or []),
        retrieval_mode=reviewer_summary.get("retrieval_mode"),
        retrieval_top_k=reviewer_summary.get("retrieval_top_k"),
        recall_rescue_enabled=_coalesce_bool(reviewer_summary.get("recall_rescue_enabled")),
        whole_document_mode=_coalesce_bool(reviewer_summary.get("whole_document_mode")),
        whole_document_max_chars=reviewer_summary.get("whole_document_max_chars"),
        recall_rescue_used=_coalesce_bool(reviewer_summary.get("recall_rescue_used")),
        recall_rescue_invocation_count=reviewer_summary.get("recall_rescue_invocation_count"),
        whole_document_used_count=((reviewer_summary.get("retrieval_provenance") or {}).get("whole_document_used_count") if isinstance(reviewer_summary.get("retrieval_provenance"), dict) else None),
        main_app_run_ref={
            "run_id": main_launch.run_id,
            "run_path": main_launch.run_path,
            "output_path": main_launch.output_path,
            "return_code": main_launch.return_code,
            "payload": main_launch.payload,
            "artifact_paths": main_launch.artifact_paths,
        },
        eval_output_ref={
            "output_path": eval_launch.output_path,
            "return_code": eval_launch.return_code,
            "summary_path": eval_launch.summary_path,
            "payload": eval_launch.payload,
            "artifact_paths": eval_launch.artifact_paths,
        },
        metadata={
            "deterministic_gate": {"stage": "acceptance", "passed": True, "failures": []},
            "contract_errors": [],
            "eval_summary": eval_summary,
            "eval_metadata": eval_metadata,
            "reviewer_summary": reviewer_summary,
            "provider_request_counts": provider_request_counts,
            "run_stats": run_stats,
            "main_stdout": main_launch.stdout,
            "main_stderr": main_launch.stderr,
            "eval_stdout": eval_launch.stdout,
            "eval_stderr": eval_launch.stderr,
        },
    )
