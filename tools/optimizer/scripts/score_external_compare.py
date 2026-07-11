from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.plotting import _is_bounded_correctness_metric, generate_suite_plots
from paper_optimizer.proposal_tables import write_proposal_tables
from paper_optimizer.report import generate_experiment_report
from paper_optimizer.results import ResultsWriter
from paper_optimizer.settings import load_config
from paper_optimizer.study import (
    _evaluate_external_result_with_suite_and_replicates,
    _external_candidate_id,
    _suite_id_for_study,
    _suite_plan,
)


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _score(row: dict[str, str], primary_metric: str) -> float | None:
    raw = row.get(f"primary.{primary_metric}") or row.get("primary_score")
    if raw in {None, ""}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _label(row: dict[str, str]) -> str:
    if str(row.get("prompt_bundle_id") or "") == "external_result":
        return row.get("text_model_id") or row.get("candidate_id") or "external"
    return row.get("text_model_id") or row.get("candidate_id") or "candidate"


def _combined_rows(
    *,
    internal_replicates: Path,
    external_replicates: Path,
    primary_metric: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, path in [("local_optimizer", internal_replicates), ("external_result", external_replicates)]:
        for row in _load_csv(path):
            score = _score(row, primary_metric)
            if score is None:
                continue
            rows.append(
                {
                    "source": source,
                    "candidate_id": row.get("candidate_id", ""),
                    "candidate_label": _label(row),
                    "suite_id": row.get("suite_id", ""),
                    "benchmark_id": row.get("benchmark_id", ""),
                    "replicate_index": row.get("replicate_index", ""),
                    "primary_metric": primary_metric,
                    "primary_score": score,
                    "runtime_seconds": row.get("runtime_seconds", ""),
                    "score_status": row.get("score_status", ""),
                }
            )
    return rows


def _plot_combined(rows: list[dict[str, Any]], path: Path, *, primary_metric: str) -> None:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(str(row["candidate_label"]), []).append(float(row["primary_score"]))
    if not grouped:
        return
    labels = sorted(grouped, key=lambda label: sum(grouped[label]) / len(grouped[label]), reverse=True)
    data = [grouped[label] for label in labels]
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(max(9, len(labels) * 1.15), 5.2))
    box = ax.boxplot(data, tick_labels=labels, showmeans=False, showfliers=False, patch_artist=True)
    for label, patch in zip(labels, box["boxes"]):
        if label.startswith("external_"):
            patch.set_facecolor("#f6c85f")
            patch.set_edgecolor("#a05a00")
            patch.set_linewidth(1.5)
        else:
            patch.set_facecolor("#d9e6ee")
            patch.set_edgecolor("#51636b")
            patch.set_linewidth(1.0)
    for x_index, values in enumerate(data, start=1):
        count = len(values)
        offsets = [0.0] if count == 1 else [(-0.18 + (0.36 * i / (count - 1))) for i in range(count)]
        label = labels[x_index - 1]
        is_external = label.startswith("external_")
        ax.scatter(
            [x_index + offset for offset in offsets],
            values,
            facecolors="#a05a00" if is_external else "#1f2d2f",
            edgecolors="#5c3300" if is_external else "#1f2d2f",
            linewidths=0.4,
            s=28 if is_external else 24,
            alpha=0.82,
            zorder=3,
        )
        mean_value = sum(values) / len(values)
        ax.hlines(
            mean_value,
            x_index - 0.31,
            x_index + 0.31,
            colors="#7a2e00" if is_external else "#0f172a",
            linewidth=2.2 if is_external else 1.8,
            zorder=4,
        )
    ax.set_xticklabels(labels, rotation=45, ha="right")
    for tick, label in zip(ax.get_xticklabels(), labels):
        if label.startswith("external_"):
            tick.set_fontweight("bold")
            tick.set_color("#7a2e00")
    ax.set_ylabel(primary_metric)
    ax.set_title("Model compare with external filled-table results")
    if _is_bounded_correctness_metric(primary_metric):
        ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score configured external results and plot them with an optimizer model-compare run.")
    parser.add_argument("--config", type=Path, default=Path("configs/compare_models.json"))
    parser.add_argument("--internal-experiment", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--suite", default=None)
    args = parser.parse_args()

    config_path = args.config.resolve()
    internal_experiment = args.internal_experiment.resolve()
    output_root = args.out.resolve()

    config = load_config(config_path)
    benchmarks = load_benchmarks(config)
    plan = _suite_plan(config, _suite_id_for_study(config, "compare", args.suite))
    primary_metric = plan.primary_metric
    experiment_dir = output_root / "experiment"
    writer = ResultsWriter(experiment_dir)
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": "external_compare",
            "study_type": "compare",
            "suite_id": plan.suite_id,
            "benchmark_ids": plan.benchmark_ids,
            "external_only": True,
        }
    )

    external_groups: dict[str, dict[str, dict[str, Any]]] = {}
    for benchmark_id in plan.benchmark_ids:
        benchmark = benchmarks.manifests[benchmark_id]
        for external_result in benchmark.external_results or []:
            external_groups.setdefault(_external_candidate_id(external_result), {})[benchmark_id] = external_result

    for _, external_results_by_benchmark in sorted(external_groups.items()):
        result = _evaluate_external_result_with_suite_and_replicates(
            config,
            writer,
            experiment_dir=experiment_dir,
            plan=plan,
            external_results_by_benchmark=external_results_by_benchmark,
            study_type="compare",
        )
        writer.append_result(result)

    generate_suite_plots(experiment_dir, primary_metric)
    write_proposal_tables(experiment_dir)
    generate_experiment_report(experiment_dir)

    combined = _combined_rows(
        internal_replicates=internal_experiment / "results" / "replicate_results.csv",
        external_replicates=experiment_dir / "results" / "replicate_results.csv",
        primary_metric=primary_metric,
    )
    _write_csv(output_root / "combined_model_compare_with_external_replicates.csv", combined)
    _plot_combined(
        combined,
        output_root / "plots" / "combined_model_compare_with_external_content_correctness.png",
        primary_metric=primary_metric,
    )


if __name__ == "__main__":
    main()
