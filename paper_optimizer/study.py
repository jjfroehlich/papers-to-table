from __future__ import annotations

from pathlib import Path
from typing import Any

from .acceptance import evaluate_promotion
from .benchmarks import Benchmarks, benchmark_id_for_split
from .bundle import build_candidate_from_dict
from .contracts import Candidate, CandidateResult, RoundSummary
from .pipeline import evaluate_candidate_once
from .plotting import generate_compare_plots, generate_optimize_plots
from .propose import propose_candidates
from .results import ResultsWriter, load_results_jsonl
from .utils import read_json


def _primary_metric_value(result: CandidateResult, metric_name: str) -> float:
    return float(result.primary_metrics.get(metric_name, float("-inf")))


def _rank_compare_results(results: list[CandidateResult], primary_metric: str) -> list[CandidateResult]:
    return sorted(
        results,
        key=lambda item: (
            item.candidate_status == "completed",
            _primary_metric_value(item, primary_metric),
            -(item.runtime_seconds or float("inf")),
        ),
        reverse=True,
    )


def _baseline_candidate(config: dict[str, Any]) -> Candidate:
    baseline = config["baseline_candidate"]
    return build_candidate_from_dict(
        "cand_0000",
        baseline,
        parent_candidate_id=None,
        round_index=0,
    )


def _candidate_from_dict_with_id(index: int, payload: dict[str, Any], round_index: int | None, parent_id: str | None) -> Candidate:
    return build_candidate_from_dict(
        f"cand_{index:04d}",
        payload,
        parent_candidate_id=parent_id,
        round_index=round_index,
    )


def run_compare_mode(config: dict[str, Any], benchmarks: Benchmarks, experiment_dir: Path) -> None:
    writer = ResultsWriter(experiment_dir)
    benchmark_id = benchmark_id_for_split(benchmarks, "dev")
    primary_metric = config["acceptance"]["primary_metric"]
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": "compare",
            "benchmark_id": benchmark_id,
        }
    )

    candidates_raw = list(config.get("compare_candidates", []))
    if not candidates_raw:
        candidates_raw = [config["baseline_candidate"]]

    candidates = [
        _candidate_from_dict_with_id(index=i + 1, payload=row, round_index=None, parent_id=None)
        for i, row in enumerate(candidates_raw)
    ]

    results: list[CandidateResult] = []

    for candidate in candidates:
        result = evaluate_candidate_once(
            config,
            experiment_dir=experiment_dir,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type="compare",
            decision="not_promoted",
            reason="compare_mode_fixed_comparison",
        )
        writer.append_result(result)
        results.append(result)

    ranked_results = _rank_compare_results(results, primary_metric)
    winner = ranked_results[0] if ranked_results and ranked_results[0].candidate_status == "completed" else None
    if winner is not None:
        writer.write_best_candidate(
            {
                "candidate_id": winner.candidate_id,
                "benchmark_id": benchmark_id,
                "study_type": "compare",
                "primary_metric": primary_metric,
                "primary_metric_value": winner.primary_metrics.get(primary_metric),
                "candidate_hash": winner.candidate_hash,
            }
        )
    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": "compare",
            "benchmark_id": benchmark_id,
            "primary_metric": primary_metric,
            "winner_candidate_id": winner.candidate_id if winner is not None else None,
            "candidate_count": len(results),
            "completed_candidate_count": sum(1 for result in results if result.candidate_status == "completed"),
            "failed_candidate_count": sum(1 for result in results if result.candidate_status != "completed"),
            "ranked_candidates": [
                {
                    "candidate_id": result.candidate_id,
                    "candidate_status": result.candidate_status,
                    "primary_metric_value": result.primary_metrics.get(primary_metric),
                    "runtime_seconds": result.runtime_seconds,
                }
                for result in ranked_results
            ],
        }
    )

    generate_compare_plots(experiment_dir, primary_metric)


def run_optimize_mode(config: dict[str, Any], benchmarks: Benchmarks, search_space: Any, experiment_dir: Path) -> None:
    writer = ResultsWriter(experiment_dir)
    benchmark_id = benchmark_id_for_split(benchmarks, "dev")

    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": "optimize",
            "benchmark_id": benchmark_id,
            "rounds": config.get("optimize", {}).get("rounds", 0),
            "batch_size": config.get("optimize", {}).get("batch_size", 1),
        }
    )

    incumbent_candidate = _baseline_candidate(config)
    incumbent_result = evaluate_candidate_once(
        config,
        experiment_dir=experiment_dir,
        candidate=incumbent_candidate,
        benchmark_id=benchmark_id,
        study_type="optimize",
        decision="incumbent",
        reason="baseline",
    )
    writer.append_result(incumbent_result)
    writer.write_best_candidate({
        "candidate_id": incumbent_candidate.candidate_id,
        "reason": "baseline",
    })
    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": "optimize",
            "benchmark_id": benchmark_id,
            "primary_metric": config["acceptance"]["primary_metric"],
            "current_best_candidate_id": incumbent_candidate.candidate_id,
        }
    )

    rounds = int(config.get("optimize", {}).get("rounds", 0))
    batch_size = int(config.get("optimize", {}).get("batch_size", 1))
    next_candidate_number = 1
    seen_signatures: set[tuple[str, str, str | None, str]] = {
        (
            incumbent_candidate.prompt_bundle_id,
            incumbent_candidate.text_model_id,
            incumbent_candidate.vision_model_id,
            str(sorted(incumbent_candidate.optimizer_knobs.items())),
        )
    }

    for round_index in range(1, rounds + 1):
        proposals = propose_candidates(
            incumbent_candidate,
            search_space=search_space,
            round_index=round_index,
            batch_size=batch_size,
            next_candidate_number_start=next_candidate_number,
        )

        filtered: list[Candidate] = []
        for candidate in proposals:
            signature = (
                candidate.prompt_bundle_id,
                candidate.text_model_id,
                candidate.vision_model_id,
                str(sorted(candidate.optimizer_knobs.items())),
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            filtered.append(candidate)

        if not filtered:
            summary = RoundSummary(
                round_index=round_index,
                incumbent_id_before=incumbent_candidate.candidate_id,
                promoted_candidate_id=None,
                incumbent_id_after=incumbent_candidate.candidate_id,
                challenger_ids=[],
                decision_notes=["no_unique_candidates"],
            )
            writer.write_round_summary(summary)
            continue

        next_candidate_number += len(filtered)

        promoted_id: str | None = None
        best_accepted_result = incumbent_result
        decision_notes: list[str] = []

        for candidate in filtered:
            challenger_result = evaluate_candidate_once(
                config,
                experiment_dir=experiment_dir,
                candidate=candidate,
                benchmark_id=benchmark_id,
                study_type="optimize",
                decision="rejected",
                reason="not_evaluated",
            )

            ok, reason = evaluate_promotion(incumbent_result, challenger_result, config["acceptance"])
            if ok:
                challenger_result.promotion_decision = "promoted"
                challenger_result.decision_reason = reason
                if (
                    challenger_result.primary_metrics.get(config["acceptance"]["primary_metric"], float("-inf"))
                    > best_accepted_result.primary_metrics.get(config["acceptance"]["primary_metric"], float("-inf"))
                ):
                    best_accepted_result = challenger_result
                    promoted_id = candidate.candidate_id
            else:
                challenger_result.promotion_decision = "rejected"
                challenger_result.decision_reason = reason
                decision_notes.append(f"{candidate.candidate_id}:{reason}")

            writer.append_result(challenger_result)

        incumbent_before = incumbent_candidate.candidate_id
        if promoted_id is not None:
            incumbent_result = best_accepted_result
            incumbent_candidate = Candidate(
                candidate_id=incumbent_result.candidate_id,
                prompt_bundle_id=incumbent_result.prompt_bundle_id,
                text_model_id=incumbent_result.text_model_id,
                vision_model_id=incumbent_result.vision_model_id,
                optimizer_knobs=incumbent_result.optimizer_knobs_flat,
                parent_candidate_id=incumbent_result.parent_candidate_id,
                round_index=round_index,
            )
            writer.write_best_candidate(
                {
                    "candidate_id": incumbent_result.candidate_id,
                    "round_index": round_index,
                    "reason": "promoted",
                }
            )
            writer.write_experiment_summary(
                {
                    "experiment_id": config["experiment_id"],
                    "study_type": "optimize",
                    "benchmark_id": benchmark_id,
                    "primary_metric": config["acceptance"]["primary_metric"],
                    "current_best_candidate_id": incumbent_result.candidate_id,
                    "current_best_score": incumbent_result.primary_metrics.get(config["acceptance"]["primary_metric"]),
                    "last_completed_round": round_index,
                }
            )

        summary = RoundSummary(
            round_index=round_index,
            incumbent_id_before=incumbent_before,
            promoted_candidate_id=promoted_id,
            incumbent_id_after=incumbent_candidate.candidate_id,
            challenger_ids=[candidate.candidate_id for candidate in filtered],
            decision_notes=decision_notes,
        )
        writer.write_round_summary(summary)

    generate_optimize_plots(experiment_dir, config["acceptance"]["primary_metric"])


def validate_best(config: dict[str, Any], benchmarks: Benchmarks, experiment_dir: Path, out_dir: Path) -> None:
    holdout_id = benchmark_id_for_split(benchmarks, "holdout")
    records = load_results_jsonl(experiment_dir)
    if not records:
        raise ValueError("No experiment records found")

    study_type = records[0].get("study_type", "optimize")
    primary_metric = config["acceptance"]["primary_metric"]

    if study_type == "optimize":
        ranked = sorted(records, key=lambda r: float(r.get("primary_metrics", {}).get(primary_metric, float("-inf"))), reverse=True)
        top = ranked[:1]
    else:
        top_k = int(config.get("compare", {}).get("holdout_top_k", 0))
        if top_k <= 0:
            return
        ranked = sorted(records, key=lambda r: float(r.get("primary_metrics", {}).get(primary_metric, float("-inf"))), reverse=True)
        top = ranked[:top_k]

    writer = ResultsWriter(out_dir)
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": study_type,
            "benchmark_id": holdout_id,
            "validation": True,
        }
    )

    for item in top:
        candidate = Candidate(
            candidate_id=str(item["candidate_id"]),
            prompt_bundle_id=str(item["prompt_bundle_id"]),
            text_model_id=str(item["text_model_id"]),
            vision_model_id=item.get("vision_model_id"),
            optimizer_knobs=dict(item.get("optimizer_knobs_flat", {})),
            parent_candidate_id=item.get("parent_candidate_id"),
            round_index=None,
        )
        result = evaluate_candidate_once(
            config,
            experiment_dir=out_dir,
            candidate=candidate,
            benchmark_id=holdout_id,
            study_type=study_type,
            decision="validated",
            reason="holdout_validation",
        )
        writer.append_result(result)


def summarize(config: dict[str, Any], experiment_dir: Path) -> None:
    manifest = read_json(experiment_dir / "experiment.json")
    study_type = manifest.get("study_type", "optimize")
    primary_metric = config["acceptance"]["primary_metric"]
    if study_type == "compare":
        generate_compare_plots(experiment_dir, primary_metric)
    else:
        generate_optimize_plots(experiment_dir, primary_metric)
