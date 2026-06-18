from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_DIR / "scripts"
BUILD_SCRIPT = SCRIPT_DIR / "build_review_package.py"
WRAPPER_SCRIPT = SCRIPT_DIR / "build_and_serve_review.py"
VALIDATE_SCRIPT = SCRIPT_DIR / "validate_review_package.py"
APPLY_SCRIPT = SCRIPT_DIR / "apply_review_decisions.py"
SCAFFOLD_SCRIPT = SCRIPT_DIR / "scaffold_benchmark_run.py"
RUNTIME_TMP = SKILL_DIR / "tests" / "tmp_runtime"

sys.path.insert(0, str(SCRIPT_DIR))
from build_and_serve_review import build_and_serve_review  # noqa: E402
from serve_review import serve  # noqa: E402


def make_workspace(name: str) -> Path:
    workspace = RUNTIME_TMP / f"{name}_{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=False)
    return workspace


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


def write_dummy_pdf(path: Path, text: str = "dummy") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
        + f"% {text}\n".encode("utf-8")
        + b"%%EOF\n"
    )


def make_run(tmp_path: Path, *, with_source_table: bool = True) -> Path:
    run_dir = tmp_path / "agent_review"
    write_dummy_pdf(run_dir / "pdfs" / "paper_a.pdf", "Paper A")
    write_dummy_pdf(run_dir / "pdfs" / "paper_b.pdf", "Paper B")
    if with_source_table:
        write_csv(
            run_dir / "source_table.csv",
            [
                {"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": "", "Weak field": ""},
                {"row_id": "row_2", "pdf_id": "paper_b", "Title": "Paper B", "Finding": "", "Weak field": ""},
            ],
            ["row_id", "pdf_id", "Title", "Finding", "Weak field"],
        )
    (run_dir / "review_input.json").write_text(
        json.dumps(
            {
                "schema_version": "papers_to_table.review_input.v1",
                "run_id": "agent_review",
                "pdfs": [
                    {"pdf_id": "paper_a", "path": "pdfs/paper_a.pdf", "label": "Paper A"},
                    {"pdf_id": "paper_b", "path": "pdfs/paper_b.pdf", "label": "Paper B"},
                ],
                "columns": [
                    {"column_name": "Finding", "description": "Main reported finding", "field_type": "text"},
                    {"column_name": "Weak field", "description": "Field with weak page evidence", "field_type": "text"},
                ],
                "rows": [
                    {"row_id": "row_1", "pdf_id": "paper_a", "values": {"Title": "Paper A"}},
                    {"row_id": "row_2", "pdf_id": "paper_b", "values": {"Title": "Paper B"}},
                ],
                "proposals": [
                    {
                        "row_id": "row_1",
                        "column_name": "Finding",
                        "proposed_value": "directly supported value",
                        "evidence": [
                            {
                                "pdf_id": "paper_a",
                                "source_type": "direct_quote",
                                "page_number": 1,
                                "quote_text": "Exact supporting sentence from the PDF.",
                            }
                        ],
                    },
                    {
                        "row_id": "row_2",
                        "column_name": "Weak field",
                        "proposed_value": "weakly inferred value",
                        "evidence": [
                            {
                                "pdf_id": "paper_b",
                                "page_number": 1,
                                "source_location": "Results",
                                "reasoning": "The agent inferred the value from page context without an exact quote.",
                            }
                        ],
                    },
                    {
                        "row_id": "row_2",
                        "column_name": "Finding",
                        "proposal_status": "no_data",
                        "evidence": [
                            {
                                "pdf_id": "paper_b",
                                "page_number": 1,
                                "quote_text": "The paper does not report the requested finding.",
                            }
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def build_package(run_dir: Path) -> dict:
    completed = run_cmd(str(BUILD_SCRIPT), "--run", str(run_dir), "--json")
    return json.loads(completed.stdout)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_instructions_fail_closed_on_csv_only_misread() -> None:
    instruction_files = {
        "SKILL.md": SKILL_DIR / "SKILL.md",
        "references/extraction_workflow.md": SKILL_DIR / "references" / "extraction_workflow.md",
        "templates/extraction_to_review_prompt.md": SKILL_DIR / "templates" / "extraction_to_review_prompt.md",
    }
    required_phrases = [
        "A request for CSV outputs is not a CSV-only request",
        "Return one completed CSV",
        "_filled.csv",
        "Before extracting any value",
        "review_input.json",
        "Every non-empty proposal must be written with structured evidence at authoring time",
        "build_and_serve_review.py",
        "serve_review.py",
    ]

    for label, path in instruction_files.items():
        text = path.read_text(encoding="utf-8")
        for phrase in required_phrases:
            assert phrase in text, f"{phrase!r} missing from {label}"


def test_authoring_validation_and_build_generate_mvp_artifacts() -> None:
    tmp_path = make_workspace("build")
    try:
        run_dir = make_run(tmp_path)
        validation = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)
        assert validation["ok"] is True

        result = build_package(run_dir)

        assert result["review_items"] == 3
        assert (run_dir / "review" / "index.html").exists()
        assert (run_dir / "review" / "review_package.json").exists()
        assert (run_dir / "normalized" / "proposals.jsonl").exists()
        assert (run_dir / "normalized" / "evidence.jsonl").exists()
        assert (run_dir / "summaries" / "validation_report.json").exists()
        assert (run_dir / "exports" / "draft_filled_table.csv").exists()

        proposals = read_jsonl(run_dir / "normalized" / "proposals.jsonl")
        evidence = read_jsonl(run_dir / "normalized" / "evidence.jsonl")
        assert proposals[0]["proposal_id"].startswith("prop_")
        assert evidence[0]["evidence_schema_version"] == "main_evidence"
        assert any(proposal["evidence_status"] == "inferred_weak" for proposal in proposals)
        assert (run_dir / "review" / "assets" / "pdf.mjs").exists()
        assert (run_dir / "review" / "assets" / "pdf.worker.mjs").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_writes_unreviewed_draft_filled_table_before_decisions() -> None:
    tmp_path = make_workspace("draft_table")
    try:
        run_dir = make_run(tmp_path)

        result = build_package(run_dir)

        draft_path = run_dir / "exports" / "draft_filled_table.csv"
        draft_rows = read_csv(draft_path)
        assert result["draft_filled_table_path"] == str(draft_path)
        assert draft_rows[0]["Finding"] == "directly supported value"
        assert draft_rows[1]["Weak field"] == "weakly inferred value"
        assert draft_rows[1]["Finding"] == ""
        assert not (run_dir / "review" / "decisions.jsonl").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_and_serve_wrapper_build_only_json_generates_review_package() -> None:
    tmp_path = make_workspace("wrapper_build_only")
    try:
        run_dir = make_run(tmp_path)

        result = json.loads(run_cmd(str(WRAPPER_SCRIPT), "--run", str(run_dir), "--build-only", "--json").stdout)

        assert result["validation_status"] == "ok"
        assert result["authoring_validation"] == "ok"
        assert result["generated_validation"] == "ok"
        assert result["served"] is False
        assert result["review_url"] is None
        assert result["review_items"] == 3
        assert (run_dir / "review" / "index.html").exists()
        assert (run_dir / "review" / "review_package.json").exists()
        assert (run_dir / "normalized" / "proposals.jsonl").exists()
        assert (run_dir / "normalized" / "evidence.jsonl").exists()
        assert (run_dir / "summaries" / "validation_report.json").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_and_serve_wrapper_can_start_localhost_server() -> None:
    tmp_path = make_workspace("wrapper_serve")
    try:
        run_dir = make_run(tmp_path)
        result, server = build_and_serve_review(run_dir, open_browser=False, quiet=True)
        try:
            assert result["served"] is True
            assert result["review_url"].startswith("http://127.0.0.1:")
            with urllib.request.urlopen(result["review_url"], timeout=5) as response:
                assert response.status == 200
                assert b"Papers-to-table rich review" in response.read()
        finally:
            if server is not None:
                server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_deterministic_ids_are_stable_across_rebuilds() -> None:
    tmp_path = make_workspace("deterministic")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)
        first_ids = [row["proposal_id"] for row in read_jsonl(run_dir / "normalized" / "proposals.jsonl")]

        build_package(run_dir)
        second_ids = [row["proposal_id"] for row in read_jsonl(run_dir / "normalized" / "proposals.jsonl")]

        assert first_ids == second_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoring_validation_rejects_non_empty_value_without_evidence() -> None:
    tmp_path = make_workspace("invalid")
    try:
        run_dir = make_run(tmp_path)
        payload = json.loads((run_dir / "review_input.json").read_text(encoding="utf-8"))
        payload["proposals"][0]["evidence"] = []
        (run_dir / "review_input.json").write_text(json.dumps(payload), encoding="utf-8")

        completed = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json"],
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 1
        report = json.loads(completed.stdout)
        assert any("non-empty proposed_value" in error for error in report["errors"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_valid_package_requires_only_quote_page_evidence_no_table_or_schema() -> None:
    tmp_path = make_workspace("minimal")
    try:
        run_dir = make_run(tmp_path, with_source_table=False)

        result = build_package(run_dir)
        package = json.loads((run_dir / "review" / "review_package.json").read_text(encoding="utf-8"))

        assert result["review_items"] == 3
        assert package["source"]["source_table_present"] is False
        assert not (run_dir / "assets" / "pages").exists()
        assert not (run_dir / "assets" / "figures").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_benchmark_run_creates_incomplete_review_input_skeleton() -> None:
    tmp_path = make_workspace("scaffold")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_b.pdf", "Paper B")
        write_csv(
            dataset_dir / "table_template.csv",
            [
                {"row_id": "row_1", "row_index": "0", "Title": "Paper A", "Finding": ""},
                {"row_id": "row_2", "row_index": "1", "Title": "Paper B", "Finding": ""},
            ],
            ["row_id", "row_index", "Title", "Finding"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [{"column_name": "Finding", "description": "Main reported finding", "field_type": "text"}],
            ["column_name", "description", "field_type"],
        )
        run_dir = tmp_path / "review_run"

        result = json.loads(run_cmd(str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--run", str(run_dir), "--json").stdout)
        payload = json.loads((run_dir / "review_input.json").read_text(encoding="utf-8"))

        assert result["status"] == "scaffolded_incomplete_until_proposals_are_added"
        assert (run_dir / "pdfs" / "paper_a.pdf").exists()
        assert (run_dir / "source_table.csv").exists()
        assert (run_dir / "schema.csv").exists()
        assert [row["row_id"] for row in payload["rows"]] == ["row_1", "row_2"]
        assert [row["pdf_id"] for row in payload["rows"]] == ["paper_a", "paper_b"]
        assert payload["columns"] == [{"column_name": "Finding", "description": "Main reported finding", "field_type": "text"}]
        assert payload["proposals"] == []
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_remains_portable_when_only_skill_directory_is_copied() -> None:
    tmp_path = make_workspace("portable")
    try:
        skill_copy = tmp_path / "portable_skill"
        shutil.copytree(SKILL_DIR, skill_copy, ignore=shutil.ignore_patterns("tmp_runtime", ".tmp", "__pycache__"))
        run_dir = make_run(tmp_path)

        completed = run_cmd(str(skill_copy / "scripts" / "build_review_package.py"), "--run", str(run_dir), "--json")
        result = json.loads(completed.stdout)

        assert result["pdfjs_assets_copied"] is True
        assert (run_dir / "review" / "assets" / "pdf.mjs").exists()
        assert (run_dir / "review" / "assets" / "pdf.worker.mjs").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_text_evidence_kinds_map_to_review_compatible_source_types() -> None:
    tmp_path = make_workspace("source_types")
    try:
        run_dir = make_run(tmp_path)
        payload = json.loads((run_dir / "review_input.json").read_text(encoding="utf-8"))
        payload["proposals"][0]["evidence"] = [
            {
                "pdf_id": "paper_a",
                "source_type": "table_text",
                "page_number": 1,
                "table_text": "Row entry copied from the results table.",
            },
            {
                "pdf_id": "paper_a",
                "page_number": 1,
                "caption_text": "Figure caption evidence that still behaves like direct text evidence.",
            },
        ]
        (run_dir / "review_input.json").write_text(json.dumps(payload), encoding="utf-8")

        build_package(run_dir)
        evidence = read_jsonl(run_dir / "normalized" / "evidence.jsonl")

        assert evidence[0]["source_type"] == "direct_quote"
        assert evidence[0]["authored_evidence_kind"] == "table_text"
        assert evidence[1]["source_type"] == "direct_quote"
        assert evidence[1]["authored_evidence_kind"] == "caption_text"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoring_validation_checks_highlight_regions_and_warns_on_ambiguous_coordinates() -> None:
    tmp_path = make_workspace("highlight_validation")
    try:
        run_dir = make_run(tmp_path)
        payload = json.loads((run_dir / "review_input.json").read_text(encoding="utf-8"))
        payload["proposals"][0]["evidence"] = [
            {
                "pdf_id": "paper_a",
                "quote_text": "Quoted text with invalid exact highlight coordinates.",
                "exact_highlight_regions": [{"x0": "1", "y0": 0.2, "x1": 0.4, "y1": 0.6}],
            },
            {
                "pdf_id": "paper_a",
                "page_number": 1,
                "quote_text": "Quoted text with ambiguous approximate highlight coordinates.",
                "approximate_highlight_regions": [{"x0": 12, "y0": 18, "x1": 42, "y1": 55}],
            },
        ]
        (run_dir / "review_input.json").write_text(json.dumps(payload), encoding="utf-8")

        completed = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json"],
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 1
        report = json.loads(completed.stdout)
        assert any("exact_highlight_regions[0].x0 must be a finite number" in error for error in report["errors"])
        assert any("exact_highlight_regions[0].page must be present" in error for error in report["errors"])
        assert any("small absolute coordinates" in warning for warning in report["warnings"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_apply_decisions_exports_accepted_only_csv() -> None:
    tmp_path = make_workspace("apply")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)
        proposals = read_jsonl(run_dir / "normalized" / "proposals.jsonl")
        decisions_path = run_dir / "review" / "downloaded_decisions.json"
        decisions_path.write_text(
            json.dumps(
                {
                    "decisions": [
                        {"proposal_id": proposals[0]["proposal_id"], "decision": "accepted", "cell_id": proposals[0]["cell_id"]},
                        {
                            "proposal_id": proposals[1]["proposal_id"],
                            "decision": "accepted_with_edit",
                            "edited_value": "reviewer edited value",
                            "cell_id": proposals[1]["cell_id"],
                        },
                        {"proposal_id": proposals[2]["proposal_id"], "decision": "confirmed_no_data", "cell_id": proposals[2]["cell_id"]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        result = json.loads(run_cmd(str(APPLY_SCRIPT), "--run", str(run_dir), "--decisions", str(decisions_path), "--json").stdout)

        final_rows = read_csv(run_dir / "exports" / "final_table.csv")
        assert result["accepted_changes_count"] == 2
        assert result["reviewed_bundle_path"] == str(run_dir / "exports" / "reviewed_bundle")
        assert final_rows[0]["Finding"] == "directly supported value"
        assert final_rows[1]["Weak field"] == "reviewer edited value"
        assert final_rows[1]["Finding"] == ""

        bundle_dir = run_dir / "exports" / "reviewed_bundle"
        assert sorted(path.name for path in bundle_dir.iterdir()) == ["audit", "filled_table_reviewed.csv", "manifest.json", "review"]
        assert sorted(path.name for path in (bundle_dir / "review").iterdir()) == ["decisions.jsonl", "evidence.jsonl", "proposals.jsonl"]
        audit_files = sorted(path.name for path in (bundle_dir / "audit").iterdir())
        assert "reviewer_summary.json" in audit_files
        assert "validation_report.json" in audit_files
        assert any(name.startswith("audit_log_") for name in audit_files)
        assert any(name.startswith("diagnostics_") for name in audit_files)
        assert read_csv(bundle_dir / "filled_table_reviewed.csv") == final_rows
        forbidden = {"pdfs", "source_table.csv", "schema.json", "schema.csv", "index.html", "assets"}
        assert forbidden.isdisjoint({path.name for path in bundle_dir.rglob("*")})
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_serve_review_bulk_accepts_only_provided_pending_ids() -> None:
    tmp_path = make_workspace("bulk_endpoint")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)
        proposals = read_jsonl(run_dir / "normalized" / "proposals.jsonl")
        server, url = serve(run_dir, open_browser=False, quiet=True)
        try:
            base_url = url.rsplit("/review/", 1)[0]
            existing_payload = json.dumps(
                {
                    "decisions": [
                        {
                            "proposal_id": proposals[0]["proposal_id"],
                            "cell_id": proposals[0]["cell_id"],
                            "decision": "rejected",
                        }
                    ]
                }
            ).encode("utf-8")
            existing_request = urllib.request.Request(
                base_url + "/api/decisions",
                data=existing_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(existing_request, timeout=5) as response:
                assert response.status == 200

            bulk_payload = json.dumps(
                {"proposal_ids": [proposals[0]["proposal_id"], proposals[1]["proposal_id"], "missing"]}
            ).encode("utf-8")
            bulk_request = urllib.request.Request(
                base_url + "/api/bulk-accept",
                data=bulk_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(bulk_request, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))

            decisions = read_jsonl(run_dir / "review" / "decisions.jsonl")
            assert result["accepted_count"] == 1
            by_proposal = {decision["proposal_id"]: decision for decision in decisions}
            assert by_proposal[proposals[0]["proposal_id"]]["decision"] == "rejected"
            assert by_proposal[proposals[1]["proposal_id"]]["decision"] == "accepted"
            assert by_proposal[proposals[1]["proposal_id"]]["decision_source"] == "human_bulk_accept"
        finally:
            server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_serve_review_writes_decisions_and_exports() -> None:
    tmp_path = make_workspace("serve")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)
        proposal = read_jsonl(run_dir / "normalized" / "proposals.jsonl")[0]
        server, url = serve(run_dir, open_browser=False, quiet=True)
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                assert response.status == 200
                assert b"Papers-to-table rich review" in response.read()
            html = (run_dir / "review" / "index.html").read_text(encoding="utf-8")
            assert "Saved locally" in html
            assert "Saved to server" in html
            assert "Partial quote match highlighted" in html
            assert "resize-left" in html
            assert "Export reviewed bundle" in html
            assert "decision_source=human_bulk_accept" in html
            assert "Text fallback - exact highlighting unavailable" in html
            assert "fallback shown because the quote text did not match rendered PDF text" in html

            payload = json.dumps(
                {
                    "decisions": [
                        {
                            "proposal_id": proposal["proposal_id"],
                            "cell_id": proposal["cell_id"],
                            "decision": "accepted",
                            "decision_source": "human_individual",
                        }
                    ]
                }
            ).encode("utf-8")
            request = urllib.request.Request(
                url.rsplit("/review/", 1)[0] + "/api/decisions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status == 200

            export_request = urllib.request.Request(url.rsplit("/review/", 1)[0] + "/api/export", data=b"{}", method="POST")
            with urllib.request.urlopen(export_request, timeout=5) as response:
                export_result = json.loads(response.read().decode("utf-8"))
            assert export_result["ok"] is True
            assert export_result["reviewed_bundle_path"] == str(run_dir / "exports" / "reviewed_bundle")
            assert (run_dir / "review" / "decisions.jsonl").exists()
            assert (run_dir / "exports" / "final_table.csv").exists()
            assert (run_dir / "exports" / "reviewed_bundle" / "filled_table_reviewed.csv").exists()
        finally:
            server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
