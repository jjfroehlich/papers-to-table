from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_package_common import review_input_path, safe_filename  # noqa: E402

SCRATCH_DIRNAME = "scratch_delete_after_success"
SCRATCH_ROOT_MARKER = ".papers_to_table_scratch_root"
SCRATCH_RUN_MARKER = ".papers_to_table_scratch"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_schema_columns(schema_path: Path | None, table_headers: list[str]) -> list[dict[str, object]]:
    if schema_path is None:
        return [
            {"column_name": header, "field_type": "text"}
            for header in table_headers
            if header not in {"row_id", "row_index", "pdf_id"}
        ]

    if schema_path.suffix.lower() == ".json":
        data = json.loads(schema_path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and isinstance(data.get("columns"), list):
            return data["columns"]
        if isinstance(data, list):
            return data
        raise ValueError(f"Cannot infer columns from JSON schema: {schema_path}")

    _, rows = read_csv(schema_path)
    columns: list[dict[str, object]] = []
    for row in rows:
        name = row.get("column_name") or row.get("name") or row.get("column")
        if not name:
            continue
        column: dict[str, object] = {"column_name": name}
        if row.get("description"):
            column["description"] = row["description"]
        if row.get("field_type"):
            column["field_type"] = row["field_type"]
        if row.get("allowed_values"):
            column["allowed_values"] = [value.strip() for value in row["allowed_values"].split("|") if value.strip()]
        columns.append(column)
    return columns


def choose_existing(dataset_dir: Path, names: list[str]) -> Path | None:
    for name in names:
        candidate = dataset_dir / name
        if candidate.exists():
            return candidate
    return None


def infer_pdf_for_row(row: dict[str, str], row_index: int, pdf_entries: list[dict[str, str]]) -> str | None:
    explicit = row.get("pdf_id") or row.get("PDF") or row.get("pdf") or row.get("pdf_file")
    if explicit:
        explicit_stem = Path(explicit).stem
        for pdf in pdf_entries:
            if explicit in {pdf["pdf_id"], pdf["label"], Path(pdf["path"]).name} or explicit_stem == pdf["pdf_id"]:
                return pdf["pdf_id"]
        return explicit_stem
    if row_index < len(pdf_entries):
        return pdf_entries[row_index]["pdf_id"]
    return None


def scaffold(dataset_dir: Path, run_dir: Path, *, force: bool = False, output_root: Path | None = None) -> dict[str, object]:
    dataset_dir = dataset_dir.resolve()
    run_dir = run_dir.resolve()
    output_root = output_root.resolve() if output_root is not None else None
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory does not exist: {dataset_dir}")
    if run_dir.exists() and any(run_dir.iterdir()) and not force:
        raise FileExistsError(f"Run directory is not empty: {run_dir}. Re-run with --force to add/overwrite scaffold files.")

    pdf_source_dir = dataset_dir / "pdfs"
    if not pdf_source_dir.exists():
        raise FileNotFoundError(f"Expected PDFs in: {pdf_source_dir}")
    pdf_files = sorted(path for path in pdf_source_dir.iterdir() if path.suffix.lower() == ".pdf")
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {pdf_source_dir}")

    table_path = choose_existing(dataset_dir, ["table_template.csv", "source_table.csv"])
    if table_path is None:
        raise FileNotFoundError(f"Expected table_template.csv or source_table.csv in: {dataset_dir}")

    schema_path = choose_existing(dataset_dir, ["schema.json", "schema.csv"])
    table_headers, table_rows = read_csv(table_path)

    run_dir.mkdir(parents=True, exist_ok=True)
    if output_root is not None:
        (output_root / "runs").mkdir(parents=True, exist_ok=True)
        scratch_root = output_root / SCRATCH_DIRNAME
        scratch_run = scratch_root / run_dir.name
        scratch_run.mkdir(parents=True, exist_ok=True)
        (scratch_root / SCRATCH_ROOT_MARKER).write_text("papers-to-table scratch root\n", encoding="utf-8")
        (scratch_run / SCRATCH_RUN_MARKER).write_text("delete-after-success scratch\n", encoding="utf-8")
        (output_root / "logs").mkdir(parents=True, exist_ok=True)
    pdf_entries: list[dict[str, str]] = []
    for pdf_path in pdf_files:
        pdf_entries.append({"pdf_id": pdf_path.stem, "path": str(pdf_path.resolve()), "label": pdf_path.stem})

    columns = read_schema_columns(schema_path, table_headers)
    rows: list[dict[str, object]] = []
    for index, row in enumerate(table_rows):
        row_id = row.get("row_id") or f"row_{index + 1}"
        values = {key: value for key, value in row.items() if value not in {"", None}}
        label = row.get("Title") or row.get("title") or row_id
        rows.append(
            {
                "row_id": row_id,
                "pdf_id": infer_pdf_for_row(row, index, pdf_entries),
                "label": label,
                "values": values,
            }
        )

    output_table_name = f"{safe_filename(dataset_dir.name, 'filled_table')}_filled.csv"
    review_input = {
        "schema_version": "papers_to_table.review_input.v1",
        "run_id": run_dir.name,
        "output_table_name": output_table_name,
        "source_table_path": str(table_path.resolve()),
        "schema_path": str(schema_path.resolve()) if schema_path is not None else None,
        "pdfs": pdf_entries,
        "columns": columns,
        "rows": rows,
        "proposals": [],
    }
    if output_root is not None:
        review_input["output_table_path"] = str(output_root / output_table_name)
    filled_table = Path(str(review_input["output_table_path"])) if "output_table_path" in review_input else run_dir / output_table_name
    path = review_input_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review_input, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "run_dir": str(run_dir),
        "review_input": str(path),
        "filled_table": str(filled_table),
        "output_root": str(output_root) if output_root is not None else None,
        "pdfs": len(pdf_entries),
        "rows": len(rows),
        "columns": len(columns),
        "source_table": str(table_path.resolve()),
        "schema": str(schema_path.resolve()) if schema_path is not None else None,
        "status": "scaffolded_incomplete_until_proposals_are_added",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a papers-to-table review run from a benchmark dataset folder.")
    parser.add_argument("--dataset-dir", required=True, type=Path, help="Benchmark dataset folder containing pdfs/, table_template.csv, and schema.*")
    parser.add_argument("--run", type=Path, help="Run directory to create or update with scaffold files. Defaults to OUTPUT_ROOT/runs/<dataset> when --output-root is set.")
    parser.add_argument("--output-root", type=Path, help="Output workspace root for final *_filled.csv files and organized runs/scratch/logs subfolders.")
    parser.add_argument("--force", action="store_true", help="Allow writing scaffold files into a non-empty run directory")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    if args.run is None and args.output_root is None:
        parser.error("Pass --run or --output-root.")
    run_dir = args.run
    if run_dir is None:
        run_dir = args.output_root / "runs" / safe_filename(args.dataset_dir.name, "dataset")  # type: ignore[operator]

    result = scaffold(args.dataset_dir, run_dir, force=args.force, output_root=args.output_root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Scaffolded incomplete review input: {result['review_input']}")
        print(f"PDFs: {result['pdfs']} Rows: {result['rows']} Columns: {result['columns']}")
        print("Add evidence-backed proposals, then run build_and_serve_review.py.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
