from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = SKILL_DIR / "scripts" / "build_review_package.py"
APPLY_SCRIPT = SKILL_DIR / "scripts" / "apply_review_decisions.py"


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run_cmd(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], check=True, text=True, capture_output=True)


def workspace(name: str) -> Path:
    root = SKILL_DIR / "tests" / ".tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}_{uuid.uuid4().hex[:12]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def make_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run_agent"
    fieldnames = ["row_id", "Title", "Method", "Main finding", "Rejected value", "No data field"]
    source_rows = [
        {
            "row_id": "row_1",
            "Title": "Paper One",
            "Method": "",
            "Main finding": "",
            "Rejected value": "",
            "No data field": "",
        }
    ]
    draft_rows = [
        {
            "row_id": "row_1",
            "Title": "Paper One",
            "Method": "spatial transcriptomics",
            "Main finding": "higher resolution mapping",
            "Rejected value": "unsupported claim",
            "No data field": "not reported",
        }
    ]
    write_csv(run_dir / "inputs" / "source_table.csv", source_rows, fieldnames)
    write_csv(run_dir / "tables" / "draft_table.csv", draft_rows, fieldnames)
    (run_dir / "inputs" / "schema.json").parent.mkdir(parents=True, exist_ok=True)
    (run_dir / "inputs" / "schema.json").write_text(
        json.dumps(
            {
                "columns": [
                    {"column_name": "Method", "description": "Primary method"},
                    {"column_name": "Main finding", "description": "Main finding"},
                    {"column_name": "Rejected value", "description": "A value to reject"},
                    {"column_name": "No data field", "description": "A value to mark no data"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence" / "evidence_notes.json").write_text(
        json.dumps(
            [
                {
                    "row_id": "row_1",
                    "column_name": "Method",
                    "evidence": "The paper uses spatial transcriptomics throughout the methods.",
                    "rationale": "The methods section directly names the assay.",
                    "source_pdf": "paper_one.pdf",
                    "page_number": 3,
                    "confidence": "high",
                },
                {
                    "row_id": "row_1",
                    "column_name": "Main finding",
                    "evidence": "The authors report higher resolution mapping in the results.",
                    "rationale": "This is the main result sentence.",
                    "source_pdf": "paper_one.pdf",
                    "page_number": 7,
                    "confidence": "medium",
                    "needs_review": True,
                    "caveat": "Summarized wording.",
                },
                {
                    "row_id": "row_1",
                    "column_name": "Rejected value",
                    "evidence": "Weak support only.",
                    "rationale": "Included to test rejection.",
                    "source_pdf": "paper_one.pdf",
                },
                {
                    "row_id": "row_1",
                    "column_name": "No data field",
                    "rationale": "Included to test confirmed no data.",
                    "source_pdf": "paper_one.pdf",
                },
            ]
        ),
        encoding="utf-8",
    )
    return run_dir


def build_package(run_dir: Path) -> dict:
    completed = run_cmd(str(BUILD_SCRIPT), "--run", str(run_dir), "--json")
    return json.loads(completed.stdout)


def proposal_map(run_dir: Path) -> dict[str, dict]:
    proposals = []
    for line in (run_dir / "proposals" / "proposals.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            proposals.append(json.loads(line))
    return {proposal["column_name"]: proposal for proposal in proposals}


def test_build_review_package_from_table_and_lightweight_evidence() -> None:
    tmp_path = workspace("build_review")
    try:
        run_dir = make_run(tmp_path)
        result = build_package(run_dir)

        review_data = json.loads((run_dir / "review" / "review_data.json").read_text(encoding="utf-8"))
        review_html = (run_dir / "review" / "review.html").read_text(encoding="utf-8")

        assert result["review_items"] == 4
        assert review_data["coverage"]["policy"] == "sparse_non_empty_values_only"
        assert any(item["rationale"] == "The methods section directly names the assay." for item in review_data["items"])
        assert "spatial transcriptomics" in review_html
        assert "The paper uses spatial transcriptomics" in review_html
        assert "Auto-accept all proposals" in review_html
        assert "Review proposals first" in review_html
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_apply_decisions_exports_accepted_values_without_mutating_source() -> None:
    tmp_path = workspace("apply_decisions")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)
        proposals = proposal_map(run_dir)
        source_before = (run_dir / "inputs" / "source_table.csv").read_text(encoding="utf-8")
        decisions_path = run_dir / "review" / "downloaded_decisions.json"
        decisions_path.write_text(
            json.dumps(
                {
                    "decisions": [
                        {"proposal_id": proposals["Method"]["proposal_id"], "decision": "accepted"},
                        {
                            "proposal_id": proposals["Main finding"]["proposal_id"],
                            "decision": "accepted_with_edit",
                            "edited_value": "higher-resolution spatial map",
                        },
                        {"proposal_id": proposals["Rejected value"]["proposal_id"], "decision": "rejected"},
                        {"proposal_id": proposals["No data field"]["proposal_id"], "decision": "confirmed_no_data"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        run_cmd(str(APPLY_SCRIPT), "--run", str(run_dir), "--decisions", str(decisions_path), "--json")

        final_rows = read_csv(run_dir / "exports" / "final_table.csv")
        assert final_rows[0]["Method"] == "spatial transcriptomics"
        assert final_rows[0]["Main finding"] == "higher-resolution spatial map"
        assert final_rows[0]["Rejected value"] == ""
        assert final_rows[0]["No data field"] == ""
        assert (run_dir / "inputs" / "source_table.csv").read_text(encoding="utf-8") == source_before
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_auto_accept_records_automation_accept_all() -> None:
    tmp_path = workspace("auto_accept")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)

        run_cmd(str(APPLY_SCRIPT), "--run", str(run_dir), "--accept-all", "--json")

        decisions = [
            json.loads(line)
            for line in (run_dir / "review" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert decisions
        assert {decision["decision_source"] for decision in decisions} == {"automation_accept_all"}
        audit_files = list((run_dir / "exports").glob("audit_log_*.json"))
        audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
        assert all(entry["auto_accepted"] for entry in audit["entries"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_sparse_coverage_policy_is_reported() -> None:
    tmp_path = workspace("sparse_report")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)

        report = (run_dir / "summaries" / "run_report.md").read_text(encoding="utf-8")
        assert "sparse_non_empty_values_only" in report
        assert "Omitted blank cells" in report
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_report_handoff_labels_reviewed_and_draft_values() -> None:
    tmp_path = workspace("handoff")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)
        proposals = proposal_map(run_dir)
        decisions_path = run_dir / "review" / "partial_decisions.json"
        decisions_path.write_text(
            json.dumps({"decisions": [{"proposal_id": proposals["Method"]["proposal_id"], "decision": "accepted"}]}),
            encoding="utf-8",
        )

        run_cmd(str(APPLY_SCRIPT), "--run", str(run_dir), "--decisions", str(decisions_path), "--json")

        handoff = json.loads((run_dir / "summaries" / "report_handoff.json").read_text(encoding="utf-8"))
        assert handoff["summary"]["human_reviewed"] == 1
        assert handoff["summary"]["draft_unreviewed"] == 3
        labels = {item["column_name"]: item["handoff_label"] for item in handoff["items"]}
        assert labels["Method"] == "human_reviewed"
        assert labels["Main finding"] == "draft_unreviewed"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_bootstrap_seed_table_and_column_plan_can_build_review_package() -> None:
    tmp_path = workspace("bootstrap")
    try:
        run_dir = tmp_path / "bootstrap_run"
        write_csv(
            run_dir / "inputs" / "seed_table.csv",
            [{"row_id": "row_pdf_1", "PDF": "paper.pdf", "Main claim": "Agent-created claim"}],
            ["row_id", "PDF", "Main claim"],
        )
        (run_dir / "inputs" / "schema.json").write_text(
            json.dumps({"columns": [{"column_name": "Main claim", "description": "Main claim from the paper"}]}),
            encoding="utf-8",
        )

        build_package(run_dir)

        review_data = json.loads((run_dir / "review" / "review_data.json").read_text(encoding="utf-8"))
        assert review_data["columns"][0]["column_name"] == "Main claim"
        assert review_data["items"][0]["proposed_value"] == "Agent-created claim"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
