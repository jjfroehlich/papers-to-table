from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_rows(results_csv: Path) -> list[dict[str, str]]:
    if not results_csv.exists():
        return []
    with results_csv.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_plot_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def generate_compare_plots(experiment_dir: Path, primary_metric: str) -> None:
    results_csv = experiment_dir / "results" / "results.csv"
    rows = _load_rows(results_csv)
    if not rows:
        return

    plots_dir = experiment_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    primary_key = f"primary.{primary_metric}"
    runtime_key = "runtime_seconds"

    grouped: list[dict[str, Any]] = []
    x_labels: list[str] = []
    y_values: list[float] = []

    for row in rows:
        score = _safe_float(row.get(primary_key))
        if score is None:
            continue
        label = row.get("candidate_id", "unknown")
        x_labels.append(label)
        y_values.append(score)
        grouped.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "text_model_id": row.get("text_model_id", ""),
                "prompt_bundle_id": row.get("prompt_bundle_id", ""),
                "primary_score": score,
            }
        )

    _write_plot_csv(plots_dir / "compare_primary_by_candidate.csv", grouped)
    if x_labels and y_values:
        plt.figure(figsize=(10, 4))
        plt.bar(x_labels, y_values)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.title("Primary metric by candidate")
        plt.ylabel(primary_metric)
        plt.savefig(plots_dir / "compare_primary_by_candidate.png")
        plt.close()

    scatter_rows_runtime: list[dict[str, Any]] = []
    scatter_rows_evidence: list[dict[str, Any]] = []
    trend_rows: list[dict[str, Any]] = []
    xs_runtime: list[float] = []
    ys_runtime: list[float] = []
    xs_evidence: list[float] = []
    ys_evidence: list[float] = []

    for row in rows:
        score = _safe_float(row.get(primary_key))
        runtime = _safe_float(row.get(runtime_key))
        evidence = _safe_float(row.get("guardrail.evidence_quality"))
        null_rate = _safe_float(row.get("guardrail.null_rate"))
        failure_rate = _safe_float(row.get("guardrail.failure_rate"))

        if score is not None and runtime is not None:
            xs_runtime.append(runtime)
            ys_runtime.append(score)
            scatter_rows_runtime.append({"runtime_seconds": runtime, "primary_score": score, "candidate_id": row.get("candidate_id", "")})

        if score is not None and evidence is not None:
            xs_evidence.append(evidence)
            ys_evidence.append(score)
            scatter_rows_evidence.append({"evidence_quality": evidence, "primary_score": score, "candidate_id": row.get("candidate_id", "")})

        trend_rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "null_rate": null_rate,
                "failure_rate": failure_rate,
            }
        )

    _write_plot_csv(plots_dir / "compare_correctness_vs_runtime.csv", scatter_rows_runtime)
    _write_plot_csv(plots_dir / "compare_correctness_vs_evidence.csv", scatter_rows_evidence)
    _write_plot_csv(plots_dir / "compare_null_failure_trends.csv", trend_rows)

    if xs_runtime and ys_runtime:
        plt.figure(figsize=(6, 4))
        plt.scatter(xs_runtime, ys_runtime)
        plt.xlabel("runtime_seconds")
        plt.ylabel(primary_metric)
        plt.title("Correctness vs runtime")
        plt.tight_layout()
        plt.savefig(plots_dir / "compare_correctness_vs_runtime.png")
        plt.close()

    if xs_evidence and ys_evidence:
        plt.figure(figsize=(6, 4))
        plt.scatter(xs_evidence, ys_evidence)
        plt.xlabel("evidence_quality")
        plt.ylabel(primary_metric)
        plt.title("Correctness vs evidence quality")
        plt.tight_layout()
        plt.savefig(plots_dir / "compare_correctness_vs_evidence.png")
        plt.close()

    if trend_rows:
        labels = [r["candidate_id"] for r in trend_rows]
        null_vals = [r["null_rate"] if r["null_rate"] is not None else 0.0 for r in trend_rows]
        fail_vals = [r["failure_rate"] if r["failure_rate"] is not None else 0.0 for r in trend_rows]
        plt.figure(figsize=(10, 4))
        plt.plot(labels, null_vals, marker="o", label="null_rate")
        plt.plot(labels, fail_vals, marker="x", label="failure_rate")
        plt.xticks(rotation=45, ha="right")
        plt.legend()
        plt.tight_layout()
        plt.title("Null/failure trends")
        plt.savefig(plots_dir / "compare_null_failure_trends.png")
        plt.close()


def generate_optimize_plots(experiment_dir: Path, primary_metric: str) -> None:
    results_csv = experiment_dir / "results" / "results.csv"
    rows = _load_rows(results_csv)
    if not rows:
        return

    plots_dir = experiment_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    primary_key = f"primary.{primary_metric}"

    typed_rows: list[dict[str, Any]] = []
    for row in rows:
        round_index = _safe_float(row.get("round_index"))
        score = _safe_float(row.get(primary_key))
        runtime = _safe_float(row.get("runtime_seconds"))
        typed_rows.append(
            {
                "round_index": int(round_index) if round_index is not None else None,
                "candidate_id": row.get("candidate_id", ""),
                "parent_candidate_id": row.get("parent_candidate_id", ""),
                "score": score,
                "runtime_seconds": runtime,
                "promotion_decision": row.get("promotion_decision", ""),
            }
        )

    typed_rows = [r for r in typed_rows if r["round_index"] is not None]
    if not typed_rows:
        return

    _write_plot_csv(plots_dir / "optimize_points.csv", typed_rows)

    by_round: dict[int, list[dict[str, Any]]] = {}
    for row in typed_rows:
        by_round.setdefault(row["round_index"], []).append(row)

    rounds = sorted(by_round)
    best_by_round: list[float] = []
    runtime_by_round: list[float] = []
    delta_by_round: list[float] = []
    champion_trace: list[float] = []

    incumbent_best: float | None = None
    for rnd in rounds:
        scores = [r["score"] for r in by_round[rnd] if r["score"] is not None]
        runtimes = [r["runtime_seconds"] for r in by_round[rnd] if r["runtime_seconds"] is not None]
        if scores:
            round_best = max(scores)
            best_by_round.append(round_best)
            champion_trace.append(round_best)
            if incumbent_best is None:
                delta_by_round.append(0.0)
            else:
                delta_by_round.append(round_best - incumbent_best)
            incumbent_best = max(incumbent_best or round_best, round_best)
        else:
            best_by_round.append(0.0)
            champion_trace.append(0.0)
            delta_by_round.append(0.0)

        runtime_by_round.append(sum(runtimes) / len(runtimes) if runtimes else 0.0)

    best_rows = [{"round_index": r, "best_score": s} for r, s in zip(rounds, best_by_round)]
    delta_rows = [{"round_index": r, "score_delta": d} for r, d in zip(rounds, delta_by_round)]
    runtime_rows = [{"round_index": r, "avg_runtime": t} for r, t in zip(rounds, runtime_by_round)]

    _write_plot_csv(plots_dir / "optimize_best_by_round.csv", best_rows)
    _write_plot_csv(plots_dir / "optimize_delta_by_round.csv", delta_rows)
    _write_plot_csv(plots_dir / "optimize_runtime_by_round.csv", runtime_rows)

    plt.figure(figsize=(7, 4))
    plt.plot(rounds, best_by_round, marker="o", label="best_score")
    plt.xlabel("round")
    plt.ylabel(primary_metric)
    plt.title("Best score by round")
    plt.tight_layout()
    plt.savefig(plots_dir / "optimize_best_by_round.png")
    plt.close()

    plt.figure(figsize=(8, 4))
    for rnd in rounds:
        scores = [r["score"] for r in by_round[rnd] if r["score"] is not None]
        plt.scatter([rnd] * len(scores), scores)
    plt.xlabel("round")
    plt.ylabel(primary_metric)
    plt.title("All candidate scores by round")
    plt.tight_layout()
    plt.savefig(plots_dir / "optimize_all_scores_by_round.png")
    plt.close()

    plt.figure(figsize=(7, 4))
    plt.plot(rounds, runtime_by_round, marker="o")
    plt.xlabel("round")
    plt.ylabel("avg_runtime_seconds")
    plt.title("Runtime by round")
    plt.tight_layout()
    plt.savefig(plots_dir / "optimize_runtime_by_round.png")
    plt.close()

    plt.figure(figsize=(7, 4))
    plt.bar(rounds, delta_by_round)
    plt.xlabel("round")
    plt.ylabel("score_delta")
    plt.title("Score delta by round")
    plt.tight_layout()
    plt.savefig(plots_dir / "optimize_score_delta_by_round.png")
    plt.close()

    plt.figure(figsize=(7, 4))
    plt.plot(rounds, champion_trace, marker="o")
    plt.xlabel("round")
    plt.ylabel(primary_metric)
    plt.title("Champion lineage trace")
    plt.tight_layout()
    plt.savefig(plots_dir / "optimize_champion_lineage.png")
    plt.close()

    best_so_far: list[float] = []
    cur: float | None = None
    for score in best_by_round:
        cur = score if cur is None else max(cur, score)
        best_so_far.append(cur)

    plt.figure(figsize=(7, 4))
    plt.plot(rounds, best_so_far, marker="o")
    plt.xlabel("round")
    plt.ylabel(primary_metric)
    plt.title("Optimization history (best-so-far)")
    plt.tight_layout()
    plt.savefig(plots_dir / "optimize_history_best_so_far.png")
    plt.close()
