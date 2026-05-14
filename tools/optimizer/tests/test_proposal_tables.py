from __future__ import annotations

import csv
import json
from pathlib import Path

from paper_optimizer.proposal_tables import write_proposal_tables


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_write_proposal_tables_exports_proposals_scored_cells_and_difficulty(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment"
    app_run_dir = experiment_dir / "runs" / "cand_0001" / "app" / "out" / "run_1"
    eval_run_dir = experiment_dir / "runs" / "cand_0001" / "eval" / "per-run" / "run_1"
    results_dir = experiment_dir / "results"
    results_dir.mkdir(parents=True)

    with (results_dir / "replicate_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_id",
                "text_model_id",
                "benchmark_id",
                "suite_id",
                "replicate_index",
                "replicate_id",
                "main_app_run_path",
                "eval_summary_path",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "cand_0001",
                "text_model_id": "provider/spatial-model-long-name",
                "benchmark_id": "bench_spatial_transcriptomics",
                "suite_id": "dev_suite",
                "replicate_index": "1",
                "replicate_id": "rep_1",
                "main_app_run_path": str(app_run_dir),
                "eval_summary_path": str(eval_run_dir / "summary.json"),
            }
        )

    _write_jsonl(
        app_run_dir / "proposals" / "proposals.jsonl",
        [
            {
                "proposal_id": "prop_1",
                "run_id": "run_1",
                "pdf_id": "paper_1",
                "row_id": "row_1",
                "column_name": "Spatial platform or method",
                "cell_id": "cell_1",
                "state": "filled",
                "support": "supported",
                "proposed_value": "Visium",
                "text_model_id": "provider/spatial-model-long-name",
                "metadata_diagnostics": {"candidate_count": 1, "candidate_values": ["Visium"]},
            }
        ],
    )
    _write_jsonl(
        eval_run_dir / "scored_cells.jsonl",
        [
            {
                "run_id": "run_1",
                "row_id": "row_1",
                "row_index": 0,
                "column_name": "Authors",
                "gold_value": "A. Author",
                "proposed_value": "A. Author",
                "is_gold_present": True,
                "was_scored": True,
                "is_correct": True,
                "join_status": "matched",
                "proposal_count": 1,
            },
            {
                "run_id": "run_1",
                "row_id": "row_1",
                "row_index": 0,
                "column_name": "Spatial platform or method",
                "cell_id": "cell_1",
                "gold_value": "Visium",
                "proposed_value": "Visium",
                "is_gold_present": True,
                "was_scored": True,
                "is_correct": True,
                "join_status": "matched",
                "proposal_count": 1,
            },
            {
                "run_id": "run_1",
                "row_id": "row_2",
                "row_index": 1,
                "column_name": "Main analysis output",
                "gold_value": "cell-type map",
                "is_gold_present": True,
                "was_scored": False,
                "is_correct": None,
                "join_status": "missing_proposal",
                "diagnostic_flags": ["missing_proposal_for_gold_present"],
                "proposal_count": 0,
            },
        ],
    )

    manifest = write_proposal_tables(experiment_dir)

    output_dir = experiment_dir / "results" / "proposal_tables"
    assert manifest["proposal_row_count"] == 1
    assert manifest["scored_cell_row_count"] == 3
    assert (output_dir / "all_proposals.csv").exists()
    assert not (output_dir / "spatial_transcriptomics_scored_cells.csv").exists()
    assert (output_dir / "by_benchmark" / "bench_spatial_transcriptomics_scored_cells.csv").exists()

    proposals = _read_csv(output_dir / "all_proposals.csv")
    assert proposals[0]["candidate_label"] == "spatial-model-long-name (cand_0001)"
    assert proposals[0]["proposed_value"] == "Visium"
    assert proposals[0]["metadata_candidate_values"] == '["Visium"]'

    difficulty = _read_csv(output_dir / "by_benchmark" / "bench_spatial_transcriptomics_column_difficulty.csv")
    assert "Authors" not in {row["column_name"] for row in difficulty}
    difficult_content_column = next(row for row in difficulty if row["column_name"] == "Main analysis output")
    assert difficult_content_column["gold_present_cell_count"] == "1"
    assert difficult_content_column["missing_proposal_cell_count"] == "1"
    assert difficult_content_column["correctness_gold_present_mean"] == "0.0"
