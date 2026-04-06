from __future__ import annotations

from pathlib import Path
from typing import Any

from .bundle import materialize_candidate_bundle
from .contracts import Candidate, CandidateResult
from .launch_eval import launch_eval_app
from .launch_main import launch_main_app
from .utils import flatten_dict


def _extract_metrics(eval_summary: dict[str, Any]) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    primary = {k: float(v) for k, v in eval_summary.get("primary_metrics", {}).items()}
    guardrail = {k: float(v) for k, v in eval_summary.get("guardrail_metrics", {}).items()}
    diagnostic = {k: float(v) for k, v in eval_summary.get("diagnostic_metrics", {}).items()}

    # Convenience fallback if eval summary exposes one flat metrics dict.
    if not primary and not guardrail and not diagnostic:
        flat = eval_summary.get("metrics", {})
        if isinstance(flat, dict):
            primary = {k: float(v) for k, v in flat.items() if isinstance(v, (int, float))}

    return primary, guardrail, diagnostic


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

    main_out = experiment_dir / "runs" / candidate.candidate_id / "main"
    eval_out = experiment_dir / "runs" / candidate.candidate_id / "eval"

    main_launch = launch_main_app(
        config,
        candidate=candidate,
        candidate_manifest_path=candidate_manifest_path,
        benchmark_id=benchmark_id,
        out_dir=main_out,
    )

    main_ref_path = main_out / config["main_app"].get("run_reference_file", "main_run.json")
    eval_launch, eval_summary = launch_eval_app(
        config,
        benchmark_id=benchmark_id,
        main_run_ref_path=main_ref_path,
        out_dir=eval_out,
    )

    primary_metrics, guardrail_metrics, diagnostic_metrics = _extract_metrics(eval_summary)

    runtime_seconds = float(eval_summary.get("runtime_seconds", 0.0))
    if runtime_seconds <= 0:
        runtime_seconds = 0.0

    return CandidateResult(
        schema_version=str(config["schema_version"]),
        experiment_id=str(config["experiment_id"]),
        study_type=study_type,
        benchmark_id=benchmark_id,
        candidate_id=candidate.candidate_id,
        parent_candidate_id=candidate.parent_candidate_id,
        round_index=candidate.round_index,
        prompt_bundle_id=candidate.prompt_bundle_id,
        text_model_id=candidate.text_model_id,
        vision_model_id=candidate.vision_model_id,
        optimizer_knobs_flat=flatten_dict(candidate.optimizer_knobs),
        primary_metrics=primary_metrics,
        guardrail_metrics=guardrail_metrics,
        diagnostic_metrics=diagnostic_metrics,
        runtime_seconds=runtime_seconds,
        started_at=main_launch.started_at,
        ended_at=eval_launch.ended_at,
        promotion_decision=decision,
        decision_reason=reason,
        main_app_run_ref={
            "run_id": main_launch.run_id,
            "run_path": main_launch.run_path,
            "output_path": main_launch.output_path,
            "return_code": main_launch.return_code,
        },
        eval_output_ref={
            "output_path": eval_launch.output_path,
            "return_code": eval_launch.return_code,
        },
        metadata={
            "main_stdout": main_launch.stdout,
            "main_stderr": main_launch.stderr,
            "eval_stdout": eval_launch.stdout,
            "eval_stderr": eval_launch.stderr,
        },
    )
