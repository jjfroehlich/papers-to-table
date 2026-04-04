import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from paper_eval.cli import main
from paper_eval.errors import ContractError
from paper_eval.gold_loader import load_gold
from paper_eval.run_loader import load_run


class LoaderAndCliTests(unittest.TestCase):
    def test_run_loader_requires_stable_join_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run-a"
            (run_dir / "proposals").mkdir(parents=True)
            (run_dir / "run.json").write_text(json.dumps({"run_id": "run-a"}), encoding="utf-8")
            (run_dir / "proposals" / "proposals.jsonl").write_text(
                json.dumps({"run_id": "run-a", "column_name": "outcome", "cell_id": "cell-1"}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ContractError):
                load_run(run_dir)

    def test_gold_xlsx_uses_first_sheet_by_default_and_supports_selection(self) -> None:
        try:
            from openpyxl import Workbook
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(str(exc))

        with tempfile.TemporaryDirectory() as temp_dir:
            gold_path = Path(temp_dir) / "gold.xlsx"
            workbook = Workbook()
            first = workbook.active
            first.title = "First"
            first.append(["row_id", "status"])
            first.append(["row-1", "yes"])
            second = workbook.create_sheet("Second")
            second.append(["row_id", "status"])
            second.append(["row-2", "no"])
            workbook.save(gold_path)

            default_gold = load_gold(gold_path)
            explicit_gold = load_gold(gold_path, sheet_name="Second")

            self.assertEqual(default_gold.sheet_name, "First")
            self.assertEqual(default_gold.cells[0].row_id, "row-1")
            self.assertEqual(explicit_gold.sheet_name, "Second")
            self.assertEqual(explicit_gold.cells[0].row_id, "row-2")

    def test_cli_scores_single_run_and_outputs_expected_artifacts(self) -> None:
        try:
            from openpyxl import Workbook  # noqa: F401
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(str(exc))

        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            run_dir = self._create_run_bundle(base / "run-a")
            gold_path = base / "gold.csv"
            gold_path.write_text(
                "row_id,row_index,status,score,score__cell_id,notes\n"
                "row-1,1,yes,10,cell-score-1,\n"
                "row-2,2,,11,cell-score-2,Text gold\n"
                "row-3,3,no,20,cell-score-3,\n",
                encoding="utf-8",
            )
            schema_path = base / "schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "global_numeric_tolerance": {"abs_tol": 0.1},
                        "columns": {
                            "status": {"field_type": "boolean"},
                            "score": {"field_type": "numeric", "numeric_tolerance": {"abs_tol": 0.5}},
                            "notes": {"field_type": "text", "scoring_policy": "judge"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            output_dir = base / "out"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "evaluate",
                        "--run",
                        str(run_dir),
                        "--gold",
                        str(gold_path),
                        "--schema",
                        str(schema_path),
                        "--out",
                        str(output_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertIn("Scored run run-a", stdout.getvalue())

            run_output = output_dir / "per-run" / "run-a"
            self.assertTrue((run_output / "scored_cells.jsonl").exists())
            self.assertTrue((run_output / "scored_cells.csv").exists())
            self.assertTrue((run_output / "run_summary.json").exists())
            self.assertTrue((run_output / "run_summary.csv").exists())

            summary = json.loads((run_output / "run_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["metrics"]["gold_present_cell_count"], 6)
            self.assertEqual(summary["metrics"]["gold_empty_cell_count"], 3)
            self.assertEqual(summary["metrics"]["filled_on_gold_empty_count"], 1)
            self.assertEqual(summary["metrics"]["missing_proposal_count"], 0)
            self.assertEqual(summary["metrics"]["cell_id_mismatch_count"], 1)
            self.assertEqual(summary["metrics"]["unmatched_proposal_count"], 1)
            self.assertEqual(summary["metrics"]["unscored_text_cell_count"], 1)
            self.assertAlmostEqual(summary["metrics"]["structured_accuracy"], 1.0)

            rows = self._read_csv(run_output / "scored_cells.csv")
            row_1_score = self._find_row(rows, row_id="row-1", column_name="score")
            row_2_status = self._find_row(rows, row_id="row-2", column_name="status")
            row_3_score = self._find_row(rows, row_id="row-3", column_name="score")
            note_row = self._find_row(rows, row_id="row-2", column_name="notes")

            self.assertEqual(row_1_score["was_scored"], "True")
            self.assertEqual(row_1_score["is_correct"], "True")
            self.assertIn('"allowed_error": 0.5', row_1_score["diagnostics"])
            self.assertEqual(row_2_status["join_status"], "gold_empty_diagnostic")
            self.assertIn("filled_on_gold_empty", row_2_status["diagnostic_flags"])
            self.assertEqual(row_3_score["join_status"], "cell_id_mismatch")
            self.assertEqual(note_row["was_scored"], "False")
            self.assertIn("text_scoring_not_implemented_in_batch_1", note_row["diagnostic_flags"])

    def test_cli_supports_runs_root_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            runs_root = base / "runs"
            self._create_run_bundle(runs_root / "run-a")
            gold_path = base / "gold.csv"
            gold_path.write_text("row_id,status\nrow-1,yes\n", encoding="utf-8")
            output_dir = base / "out"

            exit_code = main(
                [
                    "evaluate",
                    "--runs-root",
                    str(runs_root),
                    "--gold",
                    str(gold_path),
                    "--out",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "per-run" / "run-a" / "run_summary.json").exists())

    def test_cli_supports_repeated_run_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            run_a = self._create_run_bundle(base / "run-a")
            run_b = self._create_run_bundle(base / "run-b")
            gold_path = base / "gold.csv"
            gold_path.write_text("row_id,status\nrow-1,yes\n", encoding="utf-8")
            output_dir = base / "out"

            exit_code = main(
                [
                    "evaluate",
                    "--run",
                    str(run_a),
                    "--run",
                    str(run_b),
                    "--gold",
                    str(gold_path),
                    "--out",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "per-run" / "run-a" / "run_summary.json").exists())
            self.assertTrue((output_dir / "per-run" / "run-b" / "run_summary.json").exists())

    def test_gold_loader_supports_long_form(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            gold_path = Path(temp_dir) / "gold.csv"
            gold_path.write_text(
                "row_id,column_name,cell_id,gold_value\nrow-1,status,cell-1,yes\n",
                encoding="utf-8",
            )
            gold = load_gold(gold_path)
            self.assertEqual(gold.cells[0].cell_id, "cell-1")
            self.assertEqual(gold.cells[0].column_name, "status")

    def _create_run_bundle(self, run_dir: Path) -> Path:
        (run_dir / "proposals").mkdir(parents=True)
        (run_dir / "inputs").mkdir(parents=True)
        (run_dir / "summaries").mkdir(parents=True)
        (run_dir / "run.json").write_text(
            json.dumps({"run_id": run_dir.name, "run_mode": "eval", "provider_text_model_id": "model-1"}),
            encoding="utf-8",
        )
        (run_dir / "config.snapshot.json").write_text(json.dumps({"config_hash": "cfg-1"}), encoding="utf-8")
        (run_dir / "inputs" / "input_summary.json").write_text(json.dumps({"pdf_id": "pdf-1"}), encoding="utf-8")
        (run_dir / "summaries" / "run_summary.json").write_text(json.dumps({"status": "complete"}), encoding="utf-8")
        proposal_rows = [
            {
                "run_id": run_dir.name,
                "row_id": "row-1",
                "column_name": "status",
                "cell_id": "cell-status-1",
                "proposed_value": "true",
                "field_type": "boolean",
            },
            {
                "run_id": run_dir.name,
                "row_id": "row-1",
                "column_name": "score",
                "cell_id": "cell-score-1",
                "proposed_value": "10.4",
                "field_type": "numeric",
            },
            {
                "run_id": run_dir.name,
                "row_id": "row-2",
                "column_name": "status",
                "cell_id": "cell-status-2",
                "proposed_value": "false",
                "field_type": "boolean",
            },
            {
                "run_id": run_dir.name,
                "row_id": "row-2",
                "column_name": "score",
                "cell_id": "cell-score-2",
                "proposed_value": "11.0",
                "field_type": "numeric",
            },
            {
                "run_id": run_dir.name,
                "row_id": "row-2",
                "column_name": "notes",
                "cell_id": "cell-notes-2",
                "proposed_value": "Some text",
                "field_type": "text",
            },
            {
                "run_id": run_dir.name,
                "row_id": "row-3",
                "column_name": "status",
                "cell_id": "cell-status-3",
                "proposed_value": "no",
                "field_type": "boolean",
            },
            {
                "run_id": run_dir.name,
                "row_id": "row-3",
                "column_name": "score",
                "cell_id": "proposal-cell-mismatch",
                "proposed_value": "20.0",
                "field_type": "numeric",
            },
            {
                "run_id": run_dir.name,
                "row_id": "row-9",
                "column_name": "status",
                "cell_id": "cell-status-9",
                "proposed_value": "yes",
                "field_type": "boolean",
            },
        ]
        with (run_dir / "proposals" / "proposals.jsonl").open("w", encoding="utf-8") as handle:
            for row in proposal_rows:
                handle.write(json.dumps(row))
                handle.write("\n")
        return run_dir

    def _read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def _find_row(self, rows: list[dict[str, str]], *, row_id: str, column_name: str) -> dict[str, str]:
        for row in rows:
            if row["row_id"] == row_id and row["column_name"] == column_name:
                return row
        raise AssertionError(f"Row not found for {row_id} / {column_name}")


if __name__ == "__main__":
    unittest.main()
