from __future__ import annotations

from pathlib import Path
from typing import Any

from .benchmarks import load_benchmarks
from .bundle import candidate_hash, materialize_candidate_bundle
from .contracts import Candidate, CandidateResult
from .launch_eval import launch_eval_app, map_eval_summary_to_metric_groups
from .launch_main import LaunchError, launch_main_app
from .utils import flatten_dict


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
        runtime_seconds=main_launch.duration_seconds if main_launch is not None else None,
        runtime_metadata={
            "main_app_duration_seconds": main_launch.duration_seconds if main_launch is not None else None,
            "eval_duration_seconds": eval_launch.duration_seconds if eval_launch is not None else None,
            "total_duration_seconds": (
                (main_launch.duration_seconds if main_launch is not None else 0.0)
                + (eval_launch.duration_seconds if eval_launch is not None else 0.0)
            ),
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
        metadata=metadata,
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

    primary_metrics, guardrail_metrics, diagnostic_metrics = map_eval_summary_to_metric_groups(eval_summary, config["eval_app"])

    runtime_seconds = main_launch.duration_seconds if main_launch.duration_seconds > 0 else None
    runtime_metadata = {
        "main_app_duration_seconds": main_launch.duration_seconds,
        "eval_duration_seconds": eval_launch.duration_seconds,
        "total_duration_seconds": main_launch.duration_seconds + eval_launch.duration_seconds,
    }
    eval_metadata = eval_summary.get("metadata", {}) if isinstance(eval_summary.get("metadata"), dict) else {}
    if "page_count" in eval_metadata:
        runtime_metadata["page_count"] = eval_metadata.get("page_count")

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
        runtime_seconds=runtime_seconds,
        runtime_metadata=runtime_metadata,
        started_at=main_launch.started_at,
        ended_at=eval_launch.ended_at,
        candidate_status="completed",
        promotion_decision=decision,
        decision_reason=reason,
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
            "eval_summary": eval_summary,
            "eval_metadata": eval_metadata,
            "main_stdout": main_launch.stdout,
            "main_stderr": main_launch.stderr,
            "eval_stdout": eval_launch.stdout,
            "eval_stderr": eval_launch.stderr,
        },
    )
