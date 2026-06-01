import csv
import io
import json
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from paper_eval.calibration import build_structured_calibration_report, write_structured_calibration_report
from paper_eval.cli import main


class StructuredCalibrationTests(unittest.TestCase):
    def test_build_report_groups_structured_failures_by_kind_and_column(self) -> None:
        root = Path.cwd() / ".tmp_structured_calibration_report"
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir(parents=True)
            scored_path = root / "scored_cells.jsonl"
            self._write_jsonl(
                scored_path,
                [
                    self._row("numeric", "efficiency", False, "numeric_unit_or_percent_format", True),
                    self._row("numeric", "efficiency", False, "numeric_hard_mismatch", False),
                    self._row("boolean", "status", True, None, False),
                    self._row("text", "notes", False, None, False),
                ],
            )

            report = build_structured_calibration_report([scored_path])

            self.assertEqual(report["structured_scored_cell_count"], 3)
            self.assertEqual(report["structured_deterministic_failure_count"], 2)
            self.assertEqual(report["structured_adjudication_eligible_count"], 1)
            self.assertEqual(report["structured_adjudication_eligible_failure_rate"], 0.5)
            self.assertEqual(report["failure_counts_by_field_type"], {"numeric": 2})
            self.assertEqual(report["failure_counts_by_kind"]["numeric_unit_or_percent_format"], 1)
            self.assertEqual(report["top_columns_by_eligible_failure_count"][0]["column_name"], "efficiency")
            self.assertEqual(len(report["examples_by_kind"]["numeric_unit_or_percent_format"]), 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_cli_writes_structured_calibration_artifacts(self) -> None:
        root = Path.cwd() / ".tmp_structured_calibration_cli"
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir(parents=True)
            eval_dir = root / "eval" / "per-run" / "run-a"
            eval_dir.mkdir(parents=True)
            self._write_jsonl(
                eval_dir / "scored_cells.jsonl",
                [
                    self._row("categorical", "method", False, "categorical_alias_gap", True),
                    self._row("boolean", "status", False, "boolean_contradiction", False),
                ],
            )
            output_dir = root / "calibration"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "calibrate-structured",
                        "--input",
                        str(root / "eval"),
                        "--out",
                        str(output_dir),
                        "--json-output",
                    ]
                )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["command"], "calibrate-structured")
            self.assertEqual(payload["structured_deterministic_failure_count"], 2)
            summary = json.loads((output_dir / "structured_calibration_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["structured_adjudication_eligible_count"], 1)
            with (output_dir / "structured_calibration_by_column.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["column_name"], "method")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_build_report_and_csv_outputs_handle_zero_failures_cleanly(self) -> None:
        root = Path.cwd() / ".tmp_structured_calibration_empty"
        shutil.rmtree(root, ignore_errors=True)
        try:
            root.mkdir(parents=True)
            scored_path = root / "scored_cells.jsonl"
            self._write_jsonl(
                scored_path,
                [
                    self._row("numeric", "efficiency", True, None, False),
                    self._row("text", "notes", False, None, False),
                ],
            )

            report = build_structured_calibration_report([scored_path], example_limit=0)
            artifact_paths = write_structured_calibration_report(root / "out", report)

            self.assertEqual(report["structured_scored_cell_count"], 1)
            self.assertEqual(report["structured_deterministic_failure_count"], 0)
            self.assertEqual(report["structured_adjudication_eligible_count"], 0)
            self.assertIsNone(report["structured_adjudication_eligible_failure_rate"])
            self.assertIsNone(report["structured_adjudication_eligible_rate"])
            self.assertEqual(report["examples_by_kind"], {})
            with Path(artifact_paths["by_column_csv"]).open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(
                    reader.fieldnames,
                    [
                        "column_name",
                        "field_type",
                        "structured_deterministic_failure_count",
                        "structured_adjudication_eligible_count",
                        "failure_kind_counts",
                    ],
                )
                self.assertEqual(list(reader), [])
            with Path(artifact_paths["by_kind_csv"]).open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(
                    reader.fieldnames,
                    [
                        "deterministic_failure_kind",
                        "structured_deterministic_failure_count",
                        "structured_adjudication_eligible_count",
                        "field_type_counts",
                    ],
                )
                self.assertEqual(list(reader), [])
            with Path(artifact_paths["examples_csv"]).open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(
                    reader.fieldnames,
                    [
                        "deterministic_failure_kind",
                        "adjudication_eligible",
                        "field_type",
                        "column_name",
                        "row_id",
                        "gold_value",
                        "proposed_value",
                        "scored_cells_path",
                    ],
                )
                self.assertEqual(list(reader), [])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def _row(
        self,
        field_type: str,
        column_name: str,
        is_correct: bool,
        deterministic_failure_kind: str | None,
        adjudication_eligible: bool,
    ) -> dict:
        return {
            "record_kind": "gold_cell",
            "run_id": "run-a",
            "row_id": "row-1",
            "column_name": column_name,
            "field_type": field_type,
            "was_scored": True,
            "is_correct": is_correct,
            "gold_value": "gold",
            "proposed_value": "proposed",
            "deterministic_failure_kind": deterministic_failure_kind,
            "adjudication_eligible": adjudication_eligible,
        }

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
