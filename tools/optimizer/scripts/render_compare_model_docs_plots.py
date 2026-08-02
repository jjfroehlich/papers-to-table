from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.lines import Line2D

from paper_optimizer.plotting import _annotate_boxplot_means


@dataclass(frozen=True)
class PlotItem:
    candidate_id: str
    label: str
    position: float
    family: str


LOCAL_ITEMS = [
    PlotItem("cand_0010", "Gemma-4-12b-qat", 1, "local"),
    PlotItem("cand_0011", "Qwen3.6-27b", 2, "local"),
    PlotItem("cand_0002", "Gemma-4-12b", 3, "local"),
    PlotItem("cand_0009", "Qwen3.6-27b-mtp", 4, "local"),
    PlotItem("cand_0003", "Gemma-4-26b-a4b", 5, "local"),
    PlotItem("cand_0001", "Gemma-4-e4b", 6, "local"),
    PlotItem("cand_0007", "Ministral-3-14b-reasoning", 7, "local"),
    PlotItem("cand_0004", "GPT-Oss-20b", 8, "local"),
    PlotItem("cand_0006", "Nuextract3", 9, "local"),
    PlotItem("cand_0005", "Nemotron-3-nano-omni", 10, "local"),
    PlotItem("cand_0008", "Glm-4.6v-flash", 11, "local"),
]

COMMERCIAL_ITEMS = [
    PlotItem("ext_kitchin", "jkitchin/scientific-data-extraction", 13, "commercial"),
    PlotItem("ext_codex", "default", 14, "commercial"),
    PlotItem("ext_agentkit", 'jjfroehlich/agent-kit', 15, "commercial"),
]

CONTROL_ITEMS = [
    PlotItem("ext_gold", "positive", 20, "control"),
    PlotItem("ext_gold_word_shuffle", "negative\nwithin-field shuffle", 21, "control"),
    PlotItem("ext_gold_cross_field", "negative\ncross-field shuffle", 22, "control"),
]


def _load_scores(path: Path) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            candidate_id = str(row.get("candidate_id") or "").strip()
            score = str(row.get("primary_score") or "").strip()
            if candidate_id and score:
                grouped.setdefault(candidate_id, []).append(float(score) * 100.0)
    return grouped


def _at_positions(items: list[PlotItem], positions: list[float]) -> list[PlotItem]:
    if len(items) != len(positions):
        raise ValueError("Plot items and positions must have the same length")
    return [
        PlotItem(item.candidate_id, item.label, position, item.family)
        for item, position in zip(items, positions, strict=True)
    ]


def _group_rule(ax: object, start: float, end: float, label: str, *, italic_line: str | None = None) -> None:
    ax.plot([start, end], [-0.06, -0.06], transform=ax.get_xaxis_transform(), color="#111827", linewidth=1.0, clip_on=False)
    ax.text(
        (start + end) / 2,
        -0.085,
        label,
        transform=ax.get_xaxis_transform(),
        ha="center",
        va="top",
        fontsize=11,
        clip_on=False,
    )
    if italic_line:
        ax.text(
            (start + end) / 2,
            -0.14,
            italic_line,
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=10,
            fontstyle="italic",
            clip_on=False,
        )


def _render(
    *,
    scores: dict[str, list[float]],
    items: list[PlotItem],
    output_path: Path,
    figsize: tuple[float, float],
    group_rules: list[tuple[float, float, str, str | None]],
    failures: list[tuple[float, str]] | None = None,
    x_limit: tuple[float, float] | None = None,
    bar_underlay: bool = False,
    show_legend: bool = False,
) -> None:
    available = [item for item in items if item.candidate_id in scores]
    data = [scores[item.candidate_id] for item in available]
    positions = [item.position for item in available]
    colors = {
        "local": ("#78add0", "#5ba0ca"),
        "commercial": ("#d1d5db", "#9ca3af"),
        "control": ("#d1d5db", "#9ca3af"),
    }

    fig, ax = plt.subplots(figsize=figsize)
    if bar_underlay:
        ax.bar(
            positions,
            [sum(values) / len(values) for values in data],
            width=0.72,
            color=[colors[item.family][0] for item in available],
            edgecolor="#4b5563",
            linewidth=0.8,
            alpha=0.9,
            zorder=0,
        )

    box = ax.boxplot(
        data,
        positions=positions,
        widths=0.62,
        showmeans=True,
        meanline=True,
        showfliers=False,
        patch_artist=True,
        medianprops={"color": "#0b6fa4", "linewidth": 1.5},
        meanprops={"color": "#111827", "linestyle": "-", "linewidth": 2.2},
        whiskerprops={"color": "#6baed6", "linewidth": 1.0},
        capprops={"color": "#6baed6", "linewidth": 1.0},
    )
    for item, patch in zip(available, box["boxes"], strict=True):
        face, edge = colors[item.family]
        patch.set_facecolor(face)
        patch.set_edgecolor(edge)
        patch.set_alpha(0.62 if not bar_underlay else 0.28)

    for item, values in zip(available, data, strict=True):
        count = len(values)
        offsets = [0.0] if count == 1 else [(-0.16 + (0.32 * index / (count - 1))) for index in range(count)]
        ax.scatter(
            [item.position + offset for offset in offsets],
            values,
            color="#4b5563",
            s=16,
            alpha=0.58,
            linewidths=0,
            zorder=3,
        )

    ax.set_ylim(0, 110)
    _annotate_boxplot_means(
        ax,
        data,
        positions=positions,
        formatter=lambda value: f"{value:.1f}",
        color="#111827",
    )
    if x_limit:
        ax.set_xlim(*x_limit)
    ax.set_ylabel("Score (%)", fontsize=12)
    ax.set_xticks(positions, [item.label for item in available], rotation=45, ha="right", fontsize=9)
    ax.tick_params(axis="x", pad=42)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="both", width=1.2)
    ax.grid(False)

    for start, end, label, italic_line in group_rules:
        _group_rule(ax, start, end, label, italic_line=italic_line)
    for position, label in failures or []:
        ax.text(position, 8, label, ha="center", va="bottom", fontsize=10, color="#111827")

    if show_legend:
        ax.legend(
            handles=[
                Line2D([0], [0], color="#111827", linewidth=2.2, label="mean (value labeled)"),
                Line2D([0], [0], color="#0b6fa4", linewidth=1.5, label="median"),
                Line2D([0], [0], marker="o", color="none", markerfacecolor="#4b5563", markersize=4, label="replicate"),
            ],
            loc="center left",
            bbox_to_anchor=(1.01, 0.18),
            frameon=False,
            fontsize=9,
        )

    fig.subplots_adjust(left=0.10, right=0.97 if not show_legend else 0.84, top=0.96, bottom=0.47)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, pil_kwargs={"quality": 92})
    plt.close(fig)


def render_all(input_csv: Path, output_dir: Path) -> None:
    scores = _load_scores(input_csv)
    prefix = "20260615_004637_compare_models_plots_v2"

    _render(
        scores=scores,
        items=LOCAL_ITEMS + COMMERCIAL_ITEMS + CONTROL_ITEMS,
        output_path=output_dir / f"{prefix}_scores_of_all_candidates.jpg",
        figsize=(20, 8.5),
        group_rules=[
            (0.4, 11.6, "Papers-to-table", None),
            (12.4, 15.6, "Codex", "GPT-5.5xhigh"),
            (16.5, 18.5, "Local agents", None),
            (19.4, 22.6, "Controls", None),
        ],
        failures=[(17, "failed"), (18, "failed")],
        x_limit=(0, 23.6),
        show_legend=True,
    )

    selected_local = _at_positions(
        [LOCAL_ITEMS[index] for index in [0, 1, 6, 7, 8, 9, 10]],
        [1, 2, 3, 4, 5, 6, 7],
    )
    agent_item = PlotItem("ext_agentkit", 'Codex with “agent-kit”\nGPT-5.5xhigh', 9, "commercial")
    common = dict(
        scores=scores,
        items=selected_local + [agent_item],
        figsize=(9.5, 7.8),
        group_rules=[(0.4, 7.6, "Papers-to-table", None), (8.4, 9.6, "Commercial", None)],
        x_limit=(0, 10.2),
    )
    _render(output_path=output_dir / f"{prefix}_main_plot_docs.jpg", **common)
    _render(output_path=output_dir / f"{prefix}_main_plot_readme.jpg", bar_underlay=True, **common)

    _render(
        scores=scores,
        items=[LOCAL_ITEMS[0], LOCAL_ITEMS[1]],
        output_path=output_dir / f"{prefix}_compare_to_local_agents.jpg",
        figsize=(5.5, 7.5),
        group_rules=[(0.4, 2.6, "Papers-to-table", None), (3.4, 4.6, "Codex\nLocal", None), (4.8, 6.2, "Hermes\nLocal", None)],
        failures=[(4, "failed"), (5.5, "failed")],
        x_limit=(0, 6.5),
    )

    _render(
        scores=scores,
        items=[
            PlotItem("ext_codex", "default", 1, "commercial"),
            PlotItem("ext_agentkit", '“agent-kit” skill', 2, "commercial"),
        ],
        output_path=output_dir / f"{prefix}_agent_kit.jpg",
        figsize=(4.0, 7.5),
        group_rules=[(0.4, 2.6, "Codex", "GPT-5.5xhigh")],
        x_limit=(0, 3),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the published 20260615 model-comparison boxplots.")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    render_all(args.input_csv.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
