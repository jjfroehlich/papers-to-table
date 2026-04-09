from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

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


def _slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


def _candidate_labels(rows: list[dict[str, str]]) -> dict[str, str]:
    prompt_count = len({row.get("prompt_bundle_id") for row in rows if row.get("prompt_bundle_id") not in (None, "")})
    base_counts: dict[str, int] = {}
    for row in rows:
        base = row.get("text_model_id") or row.get("candidate_id") or "unknown"
        if prompt_count > 1 and row.get("prompt_bundle_id"):
            base = f"{base} [{row['prompt_bundle_id']}]"
        base_counts[base] = base_counts.get(base, 0) + 1

    labels: dict[str, str] = {}
    seen_counts: dict[str, int] = {}
    for row in rows:
        candidate_id = row.get("candidate_id", "")
        base = row.get("text_model_id") or candidate_id or "unknown"
        if prompt_count > 1 and row.get("prompt_bundle_id"):
            base = f"{base} [{row['prompt_bundle_id']}]"
        if base_counts.get(base, 0) > 1 and candidate_id:
            ordinal = seen_counts.get(base, 0) + 1
            seen_counts[base] = ordinal
            base = f"{base} ({candidate_id})"
        labels[candidate_id] = base
    return labels


def _category_score_rows(rows: list[dict[str, str]], *, category_key: str, primary_key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        category = row.get(category_key)
        if category in (None, ""):
            continue
        bucket = grouped.setdefault(
            str(category),
            {
                "scores": [],
                "candidate_count": 0,
            },
        )
        bucket["candidate_count"] += 1
        score = _safe_float(row.get(primary_key))
        if score is not None:
            bucket["scores"].append(score)

    return [
        {
            category_key: category,
            "candidate_count": bucket["candidate_count"],
            "scored_candidate_count": len(bucket["scores"]),
            "best_primary_score": max(bucket["scores"]) if bucket["scores"] else None,
            "avg_primary_score": (sum(bucket["scores"]) / len(bucket["scores"])) if bucket["scores"] else None,
        }
        for category, bucket in sorted(grouped.items())
    ]


def _write_category_plot(
    *,
    plots_dir: Path,
    rows: list[dict[str, Any]],
    category_key: str,
    title: str,
    filename_prefix: str,
) -> None:
    if not rows:
        return
    _write_plot_csv(plots_dir / f"{filename_prefix}.csv", rows)
    labels = [str(row[category_key]) for row in rows]
    values = [float(row["best_primary_score"]) if row["best_primary_score"] is not None else 0.0 for row in rows]
    colors = ["tab:blue" if row["best_primary_score"] is not None else "lightgray" for row in rows]
    plt.figure(figsize=(8, 4))
    bars = plt.bar(labels, values, color=colors)
    for bar, row in zip(bars, rows):
        if row["best_primary_score"] is None:
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                "NA",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("primary_score")
    plt.title(f"{title} (NA = unscored)")
    plt.tight_layout()
    plt.savefig(plots_dir / f"{filename_prefix}.png")
    plt.close()


def _first_present_key(row: dict[str, str], candidates: list[str]) -> str | None:
    for key in candidates:
        if key in row and row.get(key) not in (None, ""):
            return key
    return None


def generate_compare_plots(experiment_dir: Path, primary_metric: str) -> None:
    results_csv = experiment_dir / "results" / "results.csv"
    rows = _load_rows(results_csv)
    if not rows:
        return

    plots_dir = experiment_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    primary_key = f"primary.{primary_metric}"
    runtime_key = "runtime_seconds"
    candidate_labels = _candidate_labels(rows)

    grouped: list[dict[str, Any]] = []
    x_labels: list[str] = []
    y_values: list[float] = []
    bar_colors: list[str] = []

    for row in rows:
        candidate_id = row.get("candidate_id", "")
        score = _safe_float(row.get(primary_key))
        label = candidate_labels.get(candidate_id, candidate_id or "unknown")
        x_labels.append(label)
        y_values.append(score if score is not None else 0.0)
        bar_colors.append("tab:blue" if score is not None else "lightgray")
        grouped.append(
            {
                "candidate_id": candidate_id,
                "candidate_label": label,
                "text_model_id": row.get("text_model_id", ""),
                "prompt_bundle_id": row.get("prompt_bundle_id", ""),
                "candidate_status": row.get("candidate_status", ""),
                "primary_score": score,
                "primary_score_display": "NA" if score is None else score,
                "score_available": score is not None,
            }
        )

    _write_plot_csv(plots_dir / "compare_primary_by_candidate.csv", grouped)
    if x_labels and y_values:
        plt.figure(figsize=(10, 4))
        bars = plt.bar(x_labels, y_values, color=bar_colors)
        for bar, row in zip(bars, grouped):
            if not row["score_available"]:
                plt.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    "NA",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.title("Primary metric by candidate (NA = unscored)")
        plt.ylabel(primary_metric)
        plt.savefig(plots_dir / "compare_primary_by_candidate.png")
        plt.close()

    for category_key, title, filename_prefix in [
        ("text_model_id", "Best primary score by text model", "compare_primary_by_text_model"),
        ("prompt_bundle_id", "Best primary score by prompt bundle", "compare_primary_by_prompt_bundle"),
    ]:
        category_rows = _category_score_rows(rows, category_key=category_key, primary_key=primary_key)
        _write_category_plot(
            plots_dir=plots_dir,
            rows=category_rows,
            category_key=category_key,
            title=title,
            filename_prefix=filename_prefix,
        )

    knob_keys = sorted(key for key in rows[0].keys() if key.startswith("knob."))
    for knob_key in knob_keys:
        knob_rows = _category_score_rows(rows, category_key=knob_key, primary_key=primary_key)
        if not knob_rows:
            continue
        _write_category_plot(
            plots_dir=plots_dir,
            rows=knob_rows,
            category_key=knob_key,
            title=f"Best primary score by {knob_key}",
            filename_prefix=f"compare_primary_by_{_slugify(knob_key)}",
        )

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
        evidence_key = _first_present_key(
            row,
            [
                "guardrail.evidence_quality",
                "guardrail.anchor_valid_rate",
                "guardrail.correct_and_anchored_rate",
                "primary.correct_and_anchored_rate",
            ],
        )
        null_key = _first_present_key(
            row,
            [
                "guardrail.null_rate",
                "guardrail.null_count",
                "guardrail.missing_proposal_count",
                "diagnostic.unscored_text_cell_count",
            ],
        )
        failure_key = _first_present_key(
            row,
            [
                "guardrail.failure_rate",
                "guardrail.failure_count",
                "guardrail.join_failure_count",
                "diagnostic.join_failure_count",
                "diagnostic.contract_warning_count",
            ],
        )
        evidence = _safe_float(row.get(evidence_key)) if evidence_key is not None else None
        null_rate = _safe_float(row.get(null_key)) if null_key is not None else None
        failure_rate = _safe_float(row.get(failure_key)) if failure_key is not None else None

        if score is not None and runtime is not None:
            xs_runtime.append(runtime)
            ys_runtime.append(score)
            scatter_rows_runtime.append({
                "candidate_label": candidate_labels.get(row.get("candidate_id", ""), row.get("candidate_id", "")),
                "runtime_seconds": runtime,
                "primary_score": score,
                "candidate_id": row.get("candidate_id", ""),
                "text_model_id": row.get("text_model_id", ""),
            })
        elif runtime is not None:
            scatter_rows_runtime.append({
                "candidate_label": candidate_labels.get(row.get("candidate_id", ""), row.get("candidate_id", "")),
                "runtime_seconds": runtime,
                "primary_score": None,
                "candidate_id": row.get("candidate_id", ""),
                "text_model_id": row.get("text_model_id", ""),
            })

        if score is not None and evidence is not None:
            xs_evidence.append(evidence)
            ys_evidence.append(score)
            scatter_rows_evidence.append({
                "candidate_label": candidate_labels.get(row.get("candidate_id", ""), row.get("candidate_id", "")),
                "evidence_metric_value": evidence,
                "evidence_metric_name": evidence_key,
                "primary_score": score,
                "candidate_id": row.get("candidate_id", ""),
                "text_model_id": row.get("text_model_id", ""),
            })
        elif evidence is not None:
            scatter_rows_evidence.append({
                "candidate_label": candidate_labels.get(row.get("candidate_id", ""), row.get("candidate_id", "")),
                "evidence_metric_value": evidence,
                "evidence_metric_name": evidence_key,
                "primary_score": None,
                "candidate_id": row.get("candidate_id", ""),
                "text_model_id": row.get("text_model_id", ""),
            })

        trend_rows.append(
            {
                "candidate_id": row.get("candidate_id", ""),
                "candidate_label": candidate_labels.get(row.get("candidate_id", ""), row.get("candidate_id", "")),
                "null_metric_name": null_key,
                "null_metric_value": null_rate,
                "failure_metric_name": failure_key,
                "failure_metric_value": failure_rate,
                "candidate_status": row.get("candidate_status", ""),
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
        evidence_label = scatter_rows_evidence[0].get("evidence_metric_name") or "evidence_metric"
        plt.xlabel(str(evidence_label))
        plt.ylabel(primary_metric)
        plt.title("Correctness vs evidence quality")
        plt.tight_layout()
        plt.savefig(plots_dir / "compare_correctness_vs_evidence.png")
        plt.close()

    if trend_rows:
        labels = [str(r["candidate_label"]) for r in trend_rows]
        null_vals = [r["null_metric_value"] if r["null_metric_value"] is not None else 0.0 for r in trend_rows]
        fail_vals = [r["failure_metric_value"] if r["failure_metric_value"] is not None else 0.0 for r in trend_rows]
        plt.figure(figsize=(10, 4))
        null_label = trend_rows[0].get("null_metric_name") or "null_metric"
        fail_label = trend_rows[0].get("failure_metric_name") or "failure_metric"
        plt.plot(labels, null_vals, marker="o", label=str(null_label))
        plt.plot(labels, fail_vals, marker="x", label=str(fail_label))
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

    decision_counts_rows: list[dict[str, Any]] = []
    for rnd in rounds:
        entries = by_round[rnd]
        decision_counts_rows.append(
            {
                "round_index": rnd,
                "promoted_count": sum(1 for row in entries if row["promotion_decision"] == "promoted"),
                "rejected_count": sum(1 for row in entries if row["promotion_decision"] == "rejected"),
                "incumbent_count": sum(1 for row in entries if row["promotion_decision"] == "incumbent"),
            }
        )
    _write_plot_csv(plots_dir / "optimize_decision_counts_by_round.csv", decision_counts_rows)

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

    if decision_counts_rows:
        plt.figure(figsize=(8, 4))
        plt.plot(rounds, [row["promoted_count"] for row in decision_counts_rows], marker="o", label="promoted")
        plt.plot(rounds, [row["rejected_count"] for row in decision_counts_rows], marker="x", label="rejected")
        plt.plot(rounds, [row["incumbent_count"] for row in decision_counts_rows], marker="s", label="incumbent")
        plt.xlabel("round")
        plt.ylabel("candidate_count")
        plt.title("Decision counts by round")
        plt.legend()
        plt.tight_layout()
        plt.savefig(plots_dir / "optimize_decision_counts_by_round.png")
        plt.close()

    sample_row = rows[0]
    knob_keys = sorted(key for key in sample_row.keys() if key.startswith("knob."))
    for knob_key in knob_keys:
        sweep_rows: list[dict[str, Any]] = []
        xs: list[float] = []
        ys: list[float] = []
        for row in rows:
            knob_value = _safe_float(row.get(knob_key))
            score = _safe_float(row.get(primary_key))
            round_index = _safe_float(row.get("round_index"))
            if knob_value is None or score is None or round_index is None:
                continue
            xs.append(knob_value)
            ys.append(score)
            sweep_rows.append(
                {
                    "round_index": int(round_index),
                    knob_key: knob_value,
                    "primary_score": score,
                    "candidate_id": row.get("candidate_id", ""),
                }
            )
        if not sweep_rows:
            continue
        base_name = f"optimize_primary_by_{_slugify(knob_key)}"
        _write_plot_csv(plots_dir / f"{base_name}.csv", sweep_rows)
        plt.figure(figsize=(7, 4))
        plt.scatter(xs, ys)
        plt.xlabel(knob_key)
        plt.ylabel(primary_metric)
        plt.title(f"Primary score by {knob_key}")
        plt.tight_layout()
        plt.savefig(plots_dir / f"{base_name}.png")
        plt.close()
