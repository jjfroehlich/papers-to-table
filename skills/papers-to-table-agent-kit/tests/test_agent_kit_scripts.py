from __future__ import annotations

import csv
import json
import os
import signal
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_DIR / "scripts"
BUILD_SCRIPT = SCRIPT_DIR / "build_review_package.py"
WRAPPER_SCRIPT = SCRIPT_DIR / "build_and_serve_review.py"
LAUNCH_SCRIPT = SCRIPT_DIR / "launch_review_servers.py"
PREPARE_WORKSPACE_SCRIPT = SCRIPT_DIR / "prepare_output_workspace.py"
CLEANUP_SCRATCH_SCRIPT = SCRIPT_DIR / "cleanup_scratch.py"
FINALIZE_HANDOFF_SCRIPT = SCRIPT_DIR / "finalize_extraction_handoff.py"
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


def run_validation(run_dir: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    completed = subprocess.run(
        [sys.executable, str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json"],
        text=True,
        capture_output=True,
    )
    return completed, json.loads(completed.stdout)


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
    input_dir = tmp_path / "source_inputs"
    write_dummy_pdf(input_dir / "pdfs" / "paper_a.pdf", "Paper A")
    write_dummy_pdf(input_dir / "pdfs" / "paper_b.pdf", "Paper B")
    source_table_path = input_dir / "source_table.csv"
    schema_path = input_dir / "schema.csv"
    if with_source_table:
        write_csv(
            source_table_path,
            [
                {"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": "", "Weak field": ""},
                {"row_id": "row_2", "pdf_id": "paper_b", "Title": "Paper B", "Finding": "", "Weak field": ""},
            ],
            ["row_id", "pdf_id", "Title", "Finding", "Weak field"],
        )
    write_csv(
        schema_path,
        [
            {"column_name": "Finding", "description": "Main reported finding", "field_type": "text"},
            {"column_name": "Weak field", "description": "Field with weak page evidence", "field_type": "text"},
        ],
        ["column_name", "description", "field_type"],
    )
    payload = {
        "schema_version": "papers_to_table.review_input.v1",
        "run_id": "agent_review",
        "output_table_name": "agent_review_filled.csv",
        "source_table_path": str(source_table_path.resolve()) if with_source_table else None,
        "schema_path": str(schema_path.resolve()),
        "pdfs": [
            {"pdf_id": "paper_a", "path": str((input_dir / "pdfs" / "paper_a.pdf").resolve()), "label": "Paper A"},
            {"pdf_id": "paper_b", "path": str((input_dir / "pdfs" / "paper_b.pdf").resolve()), "label": "Paper B"},
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
    review_input_path = run_dir / "extraction" / "review_input.json"
    review_input_path.parent.mkdir(parents=True, exist_ok=True)
    review_input_path.write_text(json.dumps(payload), encoding="utf-8")
    return run_dir


def build_package(run_dir: Path, *, with_review: bool = False) -> dict:
    args = [str(BUILD_SCRIPT), "--run", str(run_dir), "--json"]
    if with_review:
        args.append("--with-review")
    completed = run_cmd(*args)
    return json.loads(completed.stdout)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_review_input(run_dir: Path) -> dict:
    return json.loads((run_dir / "extraction" / "review_input.json").read_text(encoding="utf-8"))


def write_review_input(run_dir: Path, payload: dict) -> None:
    (run_dir / "extraction" / "review_input.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def assert_no_old_layout(run_dir: Path) -> None:
    for name in ("pdfs", "normalized", "summaries", "exports", "review", "source_table.csv", "schema.json", "schema.csv"):
        assert not (run_dir / name).exists(), f"old layout artifact should not exist: {name}"


def test_instructions_describe_lean_optional_review_contract() -> None:
    instruction_files = {
        "SKILL.md": SKILL_DIR / "SKILL.md",
        "references/extraction_workflow.md": SKILL_DIR / "references" / "extraction_workflow.md",
        "templates/extraction_to_review_prompt.md": SKILL_DIR / "templates" / "extraction_to_review_prompt.md",
    }
    required_phrases = [
        "extraction/review_input.json",
        "output_table_name",
        "output_table_path",
        "scratch_delete_after_success",
        "prepare_output_workspace.py",
        "cleanup_scratch.py",
        "finalize_extraction_handoff.py",
        "human_review",
        "Do you want to review the results in the browser interface?",
        "exact clickable URL",
        "/human_review/index.html",
        "proposal-level `rationale`",
        "cell-by-cell",
        "validate_review_package.py --run RUN_DIR --mode authoring --json",
        "generic-rationale",
        "reused-evidence",
        "launch_review_servers.py",
        "_reviewed.csv",
    ]
    for label, path in instruction_files.items():
        text = path.read_text(encoding="utf-8")
        for phrase in required_phrases:
            assert phrase in text, f"{phrase!r} missing from {label}"


def test_authoring_validation_and_default_build_generate_lean_extraction_artifacts() -> None:
    tmp_path = make_workspace("build")
    try:
        run_dir = make_run(tmp_path)
        validation = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)
        assert validation["ok"] is True

        result = build_package(run_dir)

        assert result["review_items"] == 3
        assert result["filled_table_path"] == str(run_dir / "agent_review_filled.csv")
        assert result["human_review_built"] is False
        assert (run_dir / "agent_review_filled.csv").exists()
        assert (run_dir / "extraction" / "review_input.json").exists()
        assert (run_dir / "extraction" / "proposals.jsonl").exists()
        assert (run_dir / "extraction" / "evidence.jsonl").exists()
        assert (run_dir / "extraction" / "validation_report.json").exists()
        assert (run_dir / "extraction" / "extraction_summary.json").exists()
        assert not (run_dir / "human_review").exists()
        assert_no_old_layout(run_dir)

        proposals = read_jsonl(run_dir / "extraction" / "proposals.jsonl")
        evidence = read_jsonl(run_dir / "extraction" / "evidence.jsonl")
        assert proposals[0]["proposal_id"].startswith("prop_")
        assert evidence[0]["evidence_schema_version"] == "main_evidence"
        weak_proposal = next(proposal for proposal in proposals if proposal["evidence_status"] == "inferred_weak")
        assert weak_proposal["rationale"] == "The agent inferred the value from page context without an exact quote."
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_writes_root_filled_table_before_decisions() -> None:
    tmp_path = make_workspace("filled_table")
    try:
        run_dir = make_run(tmp_path)

        result = build_package(run_dir)

        filled_path = run_dir / "agent_review_filled.csv"
        rows = read_csv(filled_path)
        assert result["filled_table_path"] == str(filled_path)
        assert rows[0]["Finding"] == "directly supported value"
        assert rows[1]["Weak field"] == "weakly inferred value"
        assert rows[1]["Finding"] == ""
        assert not (run_dir / "human_review" / "decisions.jsonl").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_output_table_path_writes_filled_and_reviewed_tables_to_output_root() -> None:
    tmp_path = make_workspace("output_path")
    try:
        run_dir = make_run(tmp_path)
        output_root = tmp_path / "paper_outputs"
        input_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["output_table_path"] = str(output_root / "agent_review_filled.csv")
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        result = build_package(run_dir, with_review=True)

        assert result["filled_table_path"] == str(output_root / "agent_review_filled.csv")
        assert (output_root / "agent_review_filled.csv").exists()
        assert not (run_dir / "agent_review_filled.csv").exists()

        proposals = read_jsonl(run_dir / "extraction" / "proposals.jsonl")
        decisions_path = run_dir / "human_review" / "downloaded_decisions.json"
        decisions_path.write_text(
            json.dumps({"decisions": [{"proposal_id": proposals[0]["proposal_id"], "decision": "accepted"}]}),
            encoding="utf-8",
        )
        export_result = json.loads(run_cmd(str(APPLY_SCRIPT), "--run", str(run_dir), "--decisions", str(decisions_path), "--json").stdout)

        assert export_result["reviewed_table_path"] == str(output_root / "agent_review_reviewed.csv")
        assert (output_root / "agent_review_reviewed.csv").exists()
        assert not (run_dir / "agent_review_reviewed.csv").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_explicit_review_build_creates_human_review_package() -> None:
    tmp_path = make_workspace("review_build")
    try:
        run_dir = make_run(tmp_path)

        result = build_package(run_dir, with_review=True)

        assert result["human_review_built"] is True
        assert (run_dir / "human_review" / "index.html").exists()
        assert (run_dir / "human_review" / "review_package.json").exists()
        assert (run_dir / "human_review" / "assets").exists()
        assert not (run_dir / "human_review" / "assets" / "pdf-data.js").exists()
        package = json.loads((run_dir / "human_review" / "review_package.json").read_text(encoding="utf-8"))
        assert Path(package["pdfs"][0]["path"]).is_absolute()
        assert package["source"]["output_table_name"] == "agent_review_filled.csv"
        assert_no_old_layout(run_dir)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_and_serve_wrapper_build_only_json_generates_optional_review_package() -> None:
    tmp_path = make_workspace("wrapper_build_only")
    try:
        run_dir = make_run(tmp_path)

        result = json.loads(run_cmd(str(WRAPPER_SCRIPT), "--run", str(run_dir), "--build-only", "--json").stdout)

        assert result["validation_status"] == "ok"
        assert result["served"] is False
        assert result["review_url"] is None
        assert result["human_review_built"] is True
        assert (run_dir / "agent_review_filled.csv").exists()
        assert (run_dir / "human_review" / "index.html").exists()
        assert (run_dir / "human_review" / "review_package.json").exists()
        assert (run_dir / "extraction" / "proposals.jsonl").exists()
        assert (run_dir / "extraction" / "evidence.jsonl").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_and_serve_wrapper_can_start_localhost_server() -> None:
    tmp_path = make_workspace("wrapper_serve")
    try:
        run_dir = make_run(tmp_path)
        result, server = build_and_serve_review(run_dir, open_browser=False, quiet=True)
        try:
            assert result["served"] is True
            assert "/human_review/index.html" in result["review_url"]
            with urllib.request.urlopen(result["review_url"], timeout=5) as response:
                assert response.status == 200
                assert b"Papers-to-table rich review" in response.read()
            base_url = result["review_url"].rsplit("/human_review/", 1)[0]
            with urllib.request.urlopen(base_url + "/review", timeout=5) as response:
                assert response.status == 200
                assert response.geturl().endswith("/human_review/index.html")
            worker_asset = next((run_dir / "human_review" / "assets").glob("pdf.worker*.mjs"))
            with urllib.request.urlopen(base_url + f"/human_review/assets/{worker_asset.name}", timeout=5) as response:
                assert response.status == 200
                assert "javascript" in response.headers.get("Content-Type", "")
        finally:
            if server is not None:
                server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_launch_review_servers_starts_background_server_and_returns_urls() -> None:
    tmp_path = make_workspace("launch_servers")
    process_id: int | None = None
    try:
        run_dir = make_run(tmp_path)

        completed = subprocess.run(
            [
                sys.executable,
                str(LAUNCH_SCRIPT),
                "--run",
                str(run_dir),
                "--build",
                "--start-port",
                "0",
                "--quiet",
                "--json",
            ],
            check=True,
            text=True,
            capture_output=True,
            timeout=20,
        )
        result = json.loads(completed.stdout)
        assert result["ok"] is True
        server = result["servers"][0]
        process_id = int(server["process_id"])
        assert server["status"] == "running"
        assert server["review_url"].endswith("/human_review/index.html")
        assert Path(server["stdout_log"]).exists()
        assert Path(server["stderr_log"]).exists()

        with urllib.request.urlopen(server["review_url"], timeout=5) as response:
            assert response.status == 200
            assert b"Papers-to-table rich review" in response.read()
    finally:
        if process_id is not None:
            try:
                os.kill(process_id, signal.SIGTERM)
                time.sleep(0.2)
            except OSError:
                pass
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_prepare_output_workspace_and_cleanup_scratch_preserve_outputs_and_runs() -> None:
    tmp_path = make_workspace("workspace_cleanup")
    try:
        output_dir = tmp_path / "outputs"
        prepared = json.loads(
            run_cmd(
                str(PREPARE_WORKSPACE_SCRIPT),
                "--output-dir",
                str(output_dir),
                "--run-id",
                "dataset one",
                "--run-id",
                "dataset_two",
                "--json",
            ).stdout
        )

        assert Path(prepared["runs_dir"]) == output_dir / "runs"
        assert Path(prepared["scratch_dir"]) == output_dir / "scratch_delete_after_success"
        assert Path(prepared["logs_dir"]) == output_dir / "logs"
        first_run = prepared["runs"][0]
        assert first_run["run_id"] == "dataset_one"
        assert Path(first_run["run_dir"]).exists()
        assert Path(first_run["scratch_dir"]).exists()
        assert Path(first_run["log_dir"]).exists()
        assert first_run["output_table_path"].endswith("dataset_one_filled.csv")
        assert (output_dir / "scratch_delete_after_success" / ".papers_to_table_scratch_root").exists()
        assert (Path(first_run["scratch_dir"]) / ".papers_to_table_scratch").exists()

        output_csv = output_dir / "dataset_one_filled.csv"
        output_csv.write_text("row_id,Finding\nrow_1,value\n", encoding="utf-8")
        provenance_file = Path(first_run["run_dir"]) / "extraction" / "review_input.json"
        provenance_file.parent.mkdir(parents=True, exist_ok=True)
        provenance_file.write_text("{}", encoding="utf-8")
        scratch_file = Path(first_run["scratch_dir"]) / "page.txt"
        scratch_file.write_text("temporary extracted text", encoding="utf-8")
        unmarked_scratch = output_dir / "scratch_delete_after_success" / "manual_notes"
        unmarked_scratch.mkdir()
        (unmarked_scratch / "note.txt").write_text("not created by the helper", encoding="utf-8")

        cleanup = json.loads(run_cmd(str(CLEANUP_SCRATCH_SCRIPT), "--output-dir", str(output_dir), "--json").stdout)

        assert str(Path(first_run["scratch_dir"])) in cleanup["deleted"]
        assert str(unmarked_scratch.resolve()) in cleanup["skipped"]
        assert output_csv.exists()
        assert provenance_file.exists()
        assert (output_dir / "runs").exists()
        assert not Path(first_run["scratch_dir"]).exists()
        assert unmarked_scratch.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_finalize_handoff_outputs_exact_review_question_for_valid_package() -> None:
    tmp_path = make_workspace("handoff_ok")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)

        result = json.loads(
            run_cmd(
                str(FINALIZE_HANDOFF_SCRIPT),
                "--output-dir",
                str(tmp_path),
                "--run",
                str(run_dir),
                "--json",
            ).stdout
        )

        assert result["ok"] is True
        assert result["review_question"] == "Do you want to review the results in the browser interface?"
        assert result["required_final_prompt"] == "Do you want to review the results in the browser interface?"
        assert result["runs"][0]["filled_table_path"] == str(run_dir / "agent_review_filled.csv")
        assert result["runs"][0]["validation_status"] == "ok"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_finalize_handoff_fails_when_package_builder_was_skipped() -> None:
    tmp_path = make_workspace("handoff_missing_artifacts")
    try:
        run_dir = make_run(tmp_path)
        (run_dir / "agent_review_filled.csv").write_text("row_id,Finding\nrow_1,value\n", encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(FINALIZE_HANDOFF_SCRIPT),
                "--output-dir",
                str(tmp_path),
                "--run",
                str(run_dir),
                "--json",
            ],
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 1
        result = json.loads(completed.stdout)
        assert result["ok"] is False
        errors = "\n".join(result["errors"])
        assert "proposals.jsonl" in errors
        assert "validation_report.json" in errors
        assert result["review_question"] == "Do you want to review the results in the browser interface?"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_finalize_handoff_fails_on_unresolved_generic_rationale_warning() -> None:
    tmp_path = make_workspace("handoff_generic_rationale")
    try:
        run_dir = make_run(tmp_path)
        input_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["proposals"][0]["rationale"] = "Extracted from the provided PDF evidence for Finding."
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        build_package(run_dir)

        completed = subprocess.run(
            [
                sys.executable,
                str(FINALIZE_HANDOFF_SCRIPT),
                "--output-dir",
                str(tmp_path),
                "--run",
                str(run_dir),
                "--json",
            ],
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 1
        result = json.loads(completed.stdout)
        assert result["ok"] is False
        assert any("Unresolved provenance-quality warning" in error for error in result["errors"])
        assert any("generic proposal-level rationale" in error for error in result["errors"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_deterministic_ids_are_stable_across_rebuilds() -> None:
    tmp_path = make_workspace("deterministic")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir)
        first_ids = [row["proposal_id"] for row in read_jsonl(run_dir / "extraction" / "proposals.jsonl")]

        build_package(run_dir)
        second_ids = [row["proposal_id"] for row in read_jsonl(run_dir / "extraction" / "proposals.jsonl")]

        assert first_ids == second_ids
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoring_validation_rejects_non_empty_value_without_evidence() -> None:
    tmp_path = make_workspace("invalid")
    try:
        run_dir = make_run(tmp_path)
        input_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["proposals"][0]["evidence"] = []
        input_path.write_text(json.dumps(payload), encoding="utf-8")

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


def test_authoring_validation_warns_on_reused_evidence_and_generic_rationale() -> None:
    tmp_path = make_workspace("quality_warnings")
    try:
        run_dir = make_run(tmp_path)
        input_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["proposals"][0]["rationale"] = "Extracted from the provided PDF evidence for Finding."
        payload["proposals"][1]["row_id"] = "row_1"
        payload["proposals"][1]["column_name"] = "Weak field"
        payload["proposals"][1]["proposed_value"] = "another value"
        payload["proposals"][1]["rationale"] = "Extracted from the provided PDF evidence for Weak field."
        payload["proposals"][1]["evidence"] = json.loads(json.dumps(payload["proposals"][0]["evidence"]))
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        report = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)

        assert report["ok"] is True
        warnings = "\n".join(report["warnings"])
        assert "generic proposal-level rationale" in warnings
        assert "reuse the same evidence set" in warnings
        assert "row_id=row_1" in warnings
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoring_validation_warns_on_formulaic_rationale_but_allows_specific_summary() -> None:
    tmp_path = make_workspace("formulaic_rationale")
    try:
        run_dir = make_run(tmp_path)
        input_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        payload["proposals"][0]["rationale"] = (
            "The quoted PDF sentence supports 'directly supported value' for Finding because it states the exact finding "
            "reported for row_1."
        )
        payload["proposals"][1]["rationale"] = (
            "The Results page context supports 'weakly inferred value' for Weak field because it describes the field but "
            "does not provide an exact reusable quote."
        )
        payload["proposals"][2]["rationale"] = (
            "The quote says the requested finding is not reported, so the Finding cell for row_2 should remain blank."
        )
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        specific_report = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)
        assert not any("generic proposal-level rationale" in warning for warning in specific_report["warnings"])

        payload["proposals"][0]["rationale"] = (
            "For Finding, the proposed value 'directly supported value' is supported by the page-specific evidence "
            "because it states or shows the relevant method, assay, result, or figure."
        )
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        formulaic_report = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)
        assert any("generic proposal-level rationale" in warning for warning in formulaic_report["warnings"])

        payload["proposals"][0]["rationale"] = (
            "For column Finding, the value 'directly supported value' is recorded because the cited paper_a page 1 "
            "evidence specifically describes that field."
        )
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        transcript_style_report = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)
        assert any("generic proposal-level rationale" in warning for warning in transcript_style_report["warnings"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_valid_package_requires_only_quote_page_evidence_no_table_or_schema_copy() -> None:
    tmp_path = make_workspace("minimal")
    try:
        run_dir = make_run(tmp_path, with_source_table=False)

        result = build_package(run_dir)
        summary = json.loads((run_dir / "extraction" / "extraction_summary.json").read_text(encoding="utf-8"))

        assert result["review_items"] == 3
        assert summary["review_status"] == "not_human_reviewed"
        assert_no_old_layout(run_dir)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_benchmark_run_creates_reference_only_review_input_skeleton() -> None:
    tmp_path = make_workspace("scaffold")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_b.pdf", "Paper B")
        write_csv(
            dataset_dir / "table_template.csv",
            [
                {"row_id": "row_1", "row_index": "0", "pdf_id": "paper_a", "Title": "Paper A", "Finding": ""},
                {"row_id": "row_2", "row_index": "1", "pdf_id": "paper_b", "Title": "Paper B", "Finding": ""},
            ],
            ["row_id", "row_index", "pdf_id", "Title", "Finding"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [{"column_name": "Finding", "description": "Main reported finding", "field_type": "text"}],
            ["column_name", "description", "field_type"],
        )
        run_dir = tmp_path / "review_run"

        result = json.loads(run_cmd(str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--run", str(run_dir), "--json").stdout)
        payload = json.loads((run_dir / "extraction" / "review_input.json").read_text(encoding="utf-8"))

        assert result["status"] == "scaffolded_incomplete_until_proposals_are_added"
        assert result["mapping_mode"] == "explicit"
        assert result["mapped_rows"] == 2
        assert result["unmapped_rows"] == 0
        assert result["extraction_mode"] == "fill_blanks"
        assert result["eligible_target_cells"] == 2
        assert result["filled_table"].endswith("dataset_filled.csv")
        assert payload["extraction_mode"] == "fill_blanks"
        assert payload["output_table_name"] == "dataset_filled.csv"
        assert Path(payload["pdfs"][0]["path"]).is_absolute()
        assert Path(payload["source_table_path"]).is_absolute()
        assert Path(payload["schema_path"]).is_absolute()
        assert [row["row_id"] for row in payload["rows"]] == ["row_1", "row_2"]
        assert [row["pdf_id"] for row in payload["rows"]] == ["paper_a", "paper_b"]
        assert payload["columns"] == [{"column_name": "Finding", "description": "Main reported finding", "field_type": "text"}]
        assert payload["proposals"] == []
        assert_no_old_layout(run_dir)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_fails_closed_when_companion_table_contains_missing_approved_values() -> None:
    tmp_path = make_workspace("scaffold_baseline_guard")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_csv(
            dataset_dir / "table_template.csv",
            [{"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": ""}],
            ["row_id", "pdf_id", "Title", "Finding"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [{"column_name": "Finding", "field_type": "text"}],
            ["column_name", "field_type"],
        )
        write_csv(
            dataset_dir / "archived_complete_table" / "human_reviewed.csv",
            [{"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": "approved value"}],
            ["row_id", "pdf_id", "Title", "Finding"],
        )
        run_dir = tmp_path / "review_run"

        completed = subprocess.run(
            [sys.executable, str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--run", str(run_dir)],
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 1
        assert "Potential pre-existing human-reviewed target values" in completed.stderr
        assert "human_reviewed.csv" in completed.stderr
        assert not run_dir.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_detects_missing_approved_values_in_xlsx_companion() -> None:
    from openpyxl import Workbook

    tmp_path = make_workspace("scaffold_xlsx_baseline_guard")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_csv(
            dataset_dir / "table_template.csv",
            [{"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": ""}],
            ["row_id", "pdf_id", "Title", "Finding"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [{"column_name": "Finding", "field_type": "text"}],
            ["column_name", "field_type"],
        )
        workbook_path = dataset_dir / "supplemental_data" / "approved_values.xlsx"
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "literature_MPRAs"
        sheet.append(["row_id", "pdf_id", "Title", "Finding"])
        sheet.append(["row_1", "paper_a", "Paper A", "approved from workbook"])
        workbook.save(workbook_path)
        run_dir = tmp_path / "review_run"

        completed = subprocess.run(
            [sys.executable, str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--run", str(run_dir)],
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 1
        assert "approved_values.xlsx [literature_MPRAs]" in completed.stderr
        assert not run_dir.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoritative_baseline_is_preserved_visible_validated_and_reported() -> None:
    tmp_path = make_workspace("scaffold_authoritative_baseline")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_b.pdf", "Paper B")
        write_csv(
            dataset_dir / "table_template.csv",
            [
                {"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": ""},
                {"row_id": "row_2", "pdf_id": "paper_b", "Title": "Paper B", "Finding": ""},
            ],
            ["row_id", "pdf_id", "Title", "Finding"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [{"column_name": "Finding", "field_type": "text"}],
            ["column_name", "field_type"],
        )
        authoritative = dataset_dir / "reviewed" / "approved.csv"
        write_csv(
            authoritative,
            [
                {"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": "approved value"},
                {"row_id": "row_2", "pdf_id": "paper_b", "Title": "Paper B", "Finding": ""},
            ],
            ["row_id", "pdf_id", "Title", "Finding"],
        )
        run_dir = tmp_path / "review_run"

        result = json.loads(
            run_cmd(
                str(SCAFFOLD_SCRIPT),
                "--dataset-dir", str(dataset_dir),
                "--run", str(run_dir),
                "--authoritative-table", str(authoritative),
                "--json",
            ).stdout
        )
        payload_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        manifest = json.loads((run_dir / "extraction" / "baseline_manifest.json").read_text(encoding="utf-8"))
        baseline_rows = read_csv(Path(payload["source_table_path"]))

        assert result["baseline_status"] == "authoritative_baseline_applied"
        assert result["authoritative_restored_cells"] == 1
        assert manifest["restored_cells"] == 1
        assert baseline_rows[0]["Finding"] == "approved value"
        assert payload["rows"][0]["values"]["Finding"] == "approved value"

        payload["proposals"] = [{
            "row_id": "row_1",
            "column_name": "Finding",
            "proposed_value": "replacement",
            "rationale": "The quote supports a replacement.",
            "evidence": [{"pdf_id": "paper_a", "page_number": 1, "quote_text": "replacement"}],
        }]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        completed, report = run_validation(run_dir)
        assert completed.returncode == 1
        assert any("targets populated cell" in error for error in report["errors"])

        payload["proposals"] = [{
            "row_id": "row_2",
            "column_name": "Finding",
            "proposed_value": "new extraction",
            "rationale": "The page-one sentence states the new extraction for Finding.",
            "evidence": [{"pdf_id": "paper_b", "source_type": "direct_quote", "page_number": 1, "quote_text": "new extraction"}],
        }]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        build_package(run_dir)
        summary = json.loads((run_dir / "extraction" / "extraction_summary.json").read_text(encoding="utf-8"))
        assert summary["value_provenance"] == "mixed_preexisting_human_reviewed_and_agent_extracted"
        assert summary["preexisting_human_reviewed_cell_count"] == 1
        assert "preserves pre-existing human-reviewed values" in summary["notes"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoring_validation_rejects_hidden_preexisting_target_values() -> None:
    tmp_path = make_workspace("hidden_baseline_value")
    try:
        run_dir = make_run(tmp_path)
        payload_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        source_path = Path(payload["source_table_path"])
        rows = read_csv(source_path)
        rows[0]["Finding"] = "approved value"
        write_csv(source_path, rows, list(rows[0]))

        completed, report = run_validation(run_dir)

        assert completed.returncode == 1
        assert any("does not preserve source target value byte-for-byte" in error for error in report["errors"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_benchmark_run_output_root_places_runs_and_final_csv_in_workspace() -> None:
    tmp_path = make_workspace("scaffold_output_root")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_csv(
            dataset_dir / "table_template.csv",
            [{"row_id": "row_1", "row_index": "0", "pdf_id": "paper_a", "Title": "Paper A", "Finding": ""}],
            ["row_id", "row_index", "pdf_id", "Title", "Finding"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [{"column_name": "Finding", "description": "Main reported finding", "field_type": "text"}],
            ["column_name", "description", "field_type"],
        )
        output_root = tmp_path / "outputs"

        result = json.loads(run_cmd(str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--output-root", str(output_root), "--json").stdout)
        run_dir = output_root / "runs" / "dataset"
        payload_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))

        assert result["run_dir"] == str(run_dir.resolve())
        assert result["filled_table"] == str(output_root.resolve() / "dataset_filled.csv")
        assert payload["output_table_name"] == "dataset_filled.csv"
        assert payload["output_table_path"] == str(output_root.resolve() / "dataset_filled.csv")
        assert (output_root / "scratch_delete_after_success").exists()
        assert (output_root / "scratch_delete_after_success" / ".papers_to_table_scratch_root").exists()
        assert (output_root / "scratch_delete_after_success" / "dataset" / ".papers_to_table_scratch").exists()
        assert (output_root / "logs").exists()

        payload["proposals"] = [
            {
                "row_id": "row_1",
                "column_name": "Finding",
                "proposed_value": "supported finding",
                "rationale": "The page-one quote supports 'supported finding' for Finding because it states the finding directly.",
                "evidence": [
                    {
                        "pdf_id": "paper_a",
                        "source_type": "direct_quote",
                        "page_number": 1,
                        "quote_text": "The paper reports a supported finding.",
                    }
                ],
            }
        ]
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        build_result = build_package(run_dir)

        assert build_result["filled_table_path"] == str(output_root.resolve() / "dataset_filled.csv")
        assert (output_root / "dataset_filled.csv").exists()
        assert not (run_dir / "dataset_filled.csv").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_requires_explicit_pdf_mapping_and_fails_before_creating_run() -> None:
    tmp_path = make_workspace("scaffold_mapping_required")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_csv(
            dataset_dir / "table_template.csv",
            [{"row_id": "row_1", "Title": "Paper A", "Finding": ""}],
            ["row_id", "Title", "Finding"],
        )
        run_dir = tmp_path / "review_run"

        completed = subprocess.run(
            [sys.executable, str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--run", str(run_dir)],
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 1
        assert "not explicitly mapped" in completed.stderr
        assert not run_dir.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_positional_mapping_is_an_explicit_equal_count_fallback() -> None:
    tmp_path = make_workspace("scaffold_positional")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_b.pdf", "Paper B")
        write_csv(
            dataset_dir / "table_template.csv",
            [
                {"row_id": "row_1", "Title": "Paper A", "Finding": ""},
                {"row_id": "row_2", "Title": "Paper B", "Finding": ""},
            ],
            ["row_id", "Title", "Finding"],
        )
        run_dir = tmp_path / "review_run"

        result = json.loads(
            run_cmd(
                str(SCAFFOLD_SCRIPT),
                "--dataset-dir",
                str(dataset_dir),
                "--run",
                str(run_dir),
                "--allow-positional-pdf-fallback",
                "--json",
            ).stdout
        )
        payload = json.loads((run_dir / "extraction" / "review_input.json").read_text(encoding="utf-8"))

        assert result["mapping_mode"] == "positional_explicit_opt_in"
        assert [row["pdf_id"] for row in payload["rows"]] == ["paper_a", "paper_b"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_allows_table_only_rows_but_rejects_duplicate_pdf_assignment() -> None:
    tmp_path = make_workspace("scaffold_partial_dataset")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_b.pdf", "Paper B")
        table_path = dataset_dir / "table_template.csv"
        write_csv(
            table_path,
            [
                {"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": "known"},
                {"row_id": "row_2", "pdf_id": "paper_b", "Title": "Paper B", "Finding": ""},
                {"row_id": "row_3", "pdf_id": "", "Title": "Table-only paper", "Finding": ""},
            ],
            ["row_id", "pdf_id", "Title", "Finding"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [{"column_name": "Finding", "field_type": "text"}],
            ["column_name", "field_type"],
        )
        run_dir = tmp_path / "review_run"

        result = json.loads(
            run_cmd(
                str(SCAFFOLD_SCRIPT),
                "--dataset-dir",
                str(dataset_dir),
                "--run",
                str(run_dir),
                "--extraction-mode",
                "fill_and_verify",
                "--json",
            ).stdout
        )
        payload = json.loads((run_dir / "extraction" / "review_input.json").read_text(encoding="utf-8"))

        assert result["mapped_rows"] == 2
        assert result["unmapped_rows"] == 1
        assert result["populated_target_cells"] == 1
        assert result["blank_target_cells"] == 1
        assert result["eligible_target_cells"] == 2
        assert result["source_table_target_cells"] == 3
        assert result["table_only_target_cells"] == 1
        assert result["rows_with_populated_targets"] == 1
        assert payload["extraction_mode"] == "fill_and_verify"
        assert payload["rows"][2]["pdf_id"] is None

        write_csv(
            table_path,
            [
                {"row_id": "row_1", "pdf_id": "paper_a", "Title": "Paper A", "Finding": ""},
                {"row_id": "row_2", "pdf_id": "paper_a", "Title": "Duplicate", "Finding": ""},
            ],
            ["row_id", "pdf_id", "Title", "Finding"],
        )
        duplicate_run = tmp_path / "duplicate_run"
        completed = subprocess.run(
            [sys.executable, str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--run", str(duplicate_run)],
            text=True,
            capture_output=True,
        )
        assert completed.returncode == 1
        assert "duplicate assignments" in completed.stderr
        assert not duplicate_run.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_scaffold_normalizes_json_and_pipe_delimited_allowed_values() -> None:
    tmp_path = make_workspace("scaffold_allowed_values")
    try:
        dataset_dir = tmp_path / "dataset"
        write_dummy_pdf(dataset_dir / "pdfs" / "paper_a.pdf", "Paper A")
        write_csv(
            dataset_dir / "table_template.csv",
            [{"row_id": "row_1", "pdf_id": "paper_a", "Design": "", "Readout": ""}],
            ["row_id", "pdf_id", "Design", "Readout"],
        )
        write_csv(
            dataset_dir / "schema.csv",
            [
                {"column_name": "Design", "field_type": "categorical", "allowed_values": '["A", "B"]'},
                {"column_name": "Readout", "field_type": "categorical", "allowed_values": "C|D"},
            ],
            ["column_name", "field_type", "allowed_values"],
        )
        run_dir = tmp_path / "review_run"

        run_cmd(str(SCAFFOLD_SCRIPT), "--dataset-dir", str(dataset_dir), "--run", str(run_dir))
        payload = json.loads((run_dir / "extraction" / "review_input.json").read_text(encoding="utf-8"))

        assert payload["columns"][0]["allowed_values"] == ["A", "B"]
        assert payload["columns"][1]["allowed_values"] == ["C", "D"]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_remains_portable_when_only_skill_directory_is_copied() -> None:
    tmp_path = make_workspace("portable")
    try:
        skill_copy = tmp_path / "portable_skill"
        shutil.copytree(SKILL_DIR, skill_copy, ignore=shutil.ignore_patterns("tmp_runtime", ".tmp", "__pycache__"))
        run_dir = make_run(tmp_path)

        completed = run_cmd(str(skill_copy / "scripts" / "build_review_package.py"), "--run", str(run_dir), "--with-review", "--json")
        result = json.loads(completed.stdout)

        assert result["review_app_assets_copied"] is True
        assert (run_dir / "human_review" / "index.html").exists()
        assert any(path.name.startswith("index-") and path.suffix == ".js" for path in (run_dir / "human_review" / "assets").iterdir())
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_text_evidence_kinds_map_to_review_compatible_source_types() -> None:
    tmp_path = make_workspace("source_types")
    try:
        run_dir = make_run(tmp_path)
        input_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
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
        input_path.write_text(json.dumps(payload), encoding="utf-8")

        build_package(run_dir)
        evidence = read_jsonl(run_dir / "extraction" / "evidence.jsonl")

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
        input_path = run_dir / "extraction" / "review_input.json"
        payload = json.loads(input_path.read_text(encoding="utf-8"))
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
        input_path.write_text(json.dumps(payload), encoding="utf-8")

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


def test_apply_decisions_exports_accepted_only_reviewed_csv() -> None:
    tmp_path = make_workspace("apply")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir, with_review=True)
        proposals = read_jsonl(run_dir / "extraction" / "proposals.jsonl")
        decisions_path = run_dir / "human_review" / "downloaded_decisions.json"
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

        reviewed_rows = read_csv(run_dir / "agent_review_reviewed.csv")
        assert result["accepted_changes_count"] == 2
        assert result["reviewed_table_path"] == str(run_dir / "agent_review_reviewed.csv")
        assert reviewed_rows[0]["Finding"] == "directly supported value"
        assert reviewed_rows[1]["Weak field"] == "reviewer edited value"
        assert reviewed_rows[1]["Finding"] == ""
        assert (run_dir / "human_review" / "decisions.jsonl").exists()
        assert (run_dir / "human_review" / "reviewer_summary.json").exists()
        assert any(path.name.startswith("audit_log_") for path in (run_dir / "human_review").iterdir())
        assert any(path.name.startswith("diagnostics_") for path in (run_dir / "human_review").iterdir())
        assert_no_old_layout(run_dir)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_serve_review_bulk_accepts_only_provided_pending_ids() -> None:
    tmp_path = make_workspace("bulk_endpoint")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir, with_review=True)
        proposals = read_jsonl(run_dir / "extraction" / "proposals.jsonl")
        server, url = serve(run_dir, open_browser=False, quiet=True)
        try:
            base_url = url.rsplit("/human_review/", 1)[0]
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

            decisions = read_jsonl(run_dir / "human_review" / "decisions.jsonl")
            assert result["accepted_count"] == 1
            by_proposal = {decision["proposal_id"]: decision for decision in decisions}
            assert by_proposal[proposals[0]["proposal_id"]]["decision"] == "rejected"
            assert by_proposal[proposals[1]["proposal_id"]]["decision"] == "accepted"
            assert by_proposal[proposals[1]["proposal_id"]]["decision_source"] == "human_bulk_accept"
        finally:
            server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_serve_review_bulk_selection_is_pending_only_unless_replacement_is_confirmed() -> None:
    tmp_path = make_workspace("bulk_selection_endpoint")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir, with_review=True)
        proposals = read_jsonl(run_dir / "extraction" / "proposals.jsonl")
        server, url = serve(run_dir, open_browser=False, quiet=True)
        try:
            base_url = url.rsplit("/human_review/", 1)[0]

            def post(path: str, payload: dict) -> dict:
                request = urllib.request.Request(
                    base_url + path,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    return json.loads(response.read().decode("utf-8"))

            post(
                "/api/decisions",
                {"decisions": [{
                    "proposal_id": proposals[0]["proposal_id"],
                    "cell_id": proposals[0]["cell_id"],
                    "decision": "accepted",
                }]},
            )
            first = post(
                "/api/proposals/bulk-decision",
                {
                    "proposal_ids": [proposals[0]["proposal_id"], proposals[1]["proposal_id"]],
                    "decision": "rejected",
                    "replace_existing": False,
                },
            )
            assert first["recorded_count"] == 1
            assert first["skipped_proposal_ids"] == [proposals[0]["proposal_id"]]

            replaced = post(
                "/api/proposals/bulk-decision",
                {
                    "proposal_ids": [proposals[0]["proposal_id"]],
                    "decision": "confirmed_no_data",
                    "replace_existing": True,
                },
            )
            assert replaced["recorded_count"] == 1
            decisions = read_jsonl(run_dir / "human_review" / "decisions.jsonl")
            by_proposal = {decision["proposal_id"]: decision for decision in decisions}
            assert by_proposal[proposals[0]["proposal_id"]]["decision"] == "confirmed_no_data"
            assert by_proposal[proposals[0]["proposal_id"]]["decision_source"] == "human_bulk_selection"
        finally:
            server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_serve_review_react_adapter_endpoints_and_pdf_reference_serving() -> None:
    tmp_path = make_workspace("react_adapter")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir, with_review=True)
        proposal = read_jsonl(run_dir / "extraction" / "proposals.jsonl")[0]
        server, url = serve(run_dir, open_browser=False, quiet=True)
        try:
            base_url = url.rsplit("/human_review/", 1)[0]
            with urllib.request.urlopen(base_url + "/api/proposals", timeout=5) as response:
                proposals_payload = json.loads(response.read().decode("utf-8"))
            assert proposals_payload["count"] == 3
            assert proposals_payload["proposals"][0]["paper_title"] == "Paper A"

            with urllib.request.urlopen(base_url + f"/api/proposals/{proposal['proposal_id']}", timeout=5) as response:
                detail_payload = json.loads(response.read().decode("utf-8"))
            assert detail_payload["proposal"]["proposal_id"] == proposal["proposal_id"]
            assert detail_payload["evidence"][0]["quote_text"] == "Exact supporting sentence from the PDF."
            assert detail_payload["row_context"]["Title"] == "Paper A"

            with urllib.request.urlopen(base_url + "/api/review-table", timeout=5) as response:
                table_payload = json.loads(response.read().decode("utf-8"))
            assert table_payload["proposal_count"] == 3
            assert table_payload["rows"][0]["cells"]["Finding"]["proposal"]["proposal_id"] == proposal["proposal_id"]

            with urllib.request.urlopen(base_url + "/api/progress-review", timeout=5) as response:
                progress_payload = json.loads(response.read().decode("utf-8"))
            assert progress_payload["pending"] == 3

            with urllib.request.urlopen(base_url + "/api/assets/pdf/paper_a", timeout=5) as response:
                assert response.status == 200
                assert response.read(8).startswith(b"%PDF")

            try:
                urllib.request.urlopen(base_url + "/api/assets/pdf/missing", timeout=5)
                raise AssertionError("missing PDF should 404")
            except urllib.error.HTTPError as exc:
                assert exc.code == 404

            decision_payload = json.dumps({"decision": "accepted"}).encode("utf-8")
            decision_request = urllib.request.Request(
                base_url + f"/api/proposals/{proposal['proposal_id']}/decision",
                data=decision_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(decision_request, timeout=5) as response:
                decision_result = json.loads(response.read().decode("utf-8"))
            assert decision_result["decision"] == "accepted"
            assert decision_result["decision_source"] == "human_individual"
        finally:
            server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_serve_review_writes_decisions_and_exports_reviewed_table() -> None:
    tmp_path = make_workspace("serve")
    try:
        run_dir = make_run(tmp_path)
        build_package(run_dir, with_review=True)
        proposal = read_jsonl(run_dir / "extraction" / "proposals.jsonl")[0]
        server, url = serve(run_dir, open_browser=False, quiet=True)
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                assert response.status == 200
                assert b"Papers-to-table rich review" in response.read()
            html = (run_dir / "human_review" / "index.html").read_text(encoding="utf-8")
            assert "__REVIEW_PACKAGE_JSON__" not in html
            assert "window.__REVIEW_PACKAGE__ = {" in html
            assert "./assets/index-" in html
            assert "./logo_1.svg" in html or (run_dir / "human_review" / "logo_1.svg").exists()
            assert 'type="module"' not in html
            assert "crossorigin" not in html
            assert '<script defer src="./assets/index-' in html
            assert "pdf-data.js" not in html

            app_source = (SKILL_DIR / "review_app" / "src" / "App.tsx").read_text(encoding="utf-8")
            review_workspace_source = (SKILL_DIR / "review_app" / "src" / "components" / "ReviewWorkspace.tsx").read_text(encoding="utf-8")
            action_source = (SKILL_DIR / "review_app" / "src" / "components" / "ReviewActionArea.tsx").read_text(encoding="utf-8")
            evidence_source = (SKILL_DIR / "review_app" / "src" / "components" / "EvidenceViewer.tsx").read_text(encoding="utf-8")
            queue_source = (SKILL_DIR / "review_app" / "src" / "components" / "ProposalQueue.tsx").read_text(encoding="utf-8")
            assert "Evidence-backed extraction and review" in app_source
            assert "Agent skill review" in app_source
            assert "Export reviewed table" in review_workspace_source
            assert "Finish review" in review_workspace_source
            assert "Export reviewed bundle" not in review_workspace_source
            assert "reviewed_bundle" not in review_workspace_source
            assert "Download mode" not in review_workspace_source
            assert "downloaded_decisions.json" in review_workspace_source
            assert "role=\"separator\"" in review_workspace_source
            assert "decision_source=human_bulk_accept" in action_source
            assert "Quote-anchored highlight" in evidence_source
            assert "Quote + page fallback" in evidence_source
            assert "Approximate region highlight" in evidence_source
            assert "evidence?.table_text" in evidence_source
            assert "PDF rendering and quote highlights require localhost serving" in evidence_source
            assert "loadFileModePdfData" not in evidence_source
            assert "embeddedFileModePdfData" not in evidence_source
            assert "By Paper" in queue_source
            assert "By Column" in queue_source
            assert "As Table" in queue_source

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
                url.rsplit("/human_review/", 1)[0] + "/api/decisions",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status == 200

            export_request = urllib.request.Request(url.rsplit("/human_review/", 1)[0] + "/api/export", data=b"{}", method="POST")
            with urllib.request.urlopen(export_request, timeout=5) as response:
                export_result = json.loads(response.read().decode("utf-8"))
            assert export_result["ok"] is True
            assert export_result["reviewed_table_path"] == str(run_dir / "agent_review_reviewed.csv")
            assert (run_dir / "human_review" / "decisions.jsonl").exists()
            assert (run_dir / "agent_review_reviewed.csv").exists()
            assert_no_old_layout(run_dir)
        finally:
            server.shutdown()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoring_validation_enforces_number_and_categorical_fields() -> None:
    tmp_path = make_workspace("typed_values")
    try:
        run_dir = make_run(tmp_path)
        payload = read_review_input(run_dir)
        payload["columns"] = [
            {"column_name": "Count", "field_type": "number"},
            {
                "column_name": "Readout",
                "field_type": "categorical",
                "allowed_values": ["RNA/DNAseq", "RNAseq"],
            },
        ]
        evidence = [{"pdf_id": "paper_a", "page_number": 1, "quote_text": "The assay tested 100 constructs."}]
        payload["proposals"] = [
            {"row_id": "row_1", "column_name": "Count", "proposed_value": "100", "evidence": evidence},
            {"row_id": "row_1", "column_name": "Readout", "proposed_value": "sequencing-based", "evidence": evidence},
        ]
        write_review_input(run_dir, payload)

        completed, report = run_validation(run_dir)

        assert completed.returncode == 1
        assert report["ok"] is False
        assert any("finite JSON number" in error for error in report["errors"])
        assert any("is not an allowed value" in error for error in report["errors"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_authoring_validation_checks_derivation_requirements() -> None:
    tmp_path = make_workspace("derivation_validation")
    try:
        run_dir = make_run(tmp_path)
        payload = read_review_input(run_dir)
        payload["columns"] = [{"column_name": "Estimate", "field_type": "number"}]
        payload["proposals"] = [
            {
                "row_id": "row_1",
                "column_name": "Estimate",
                "proposed_value": 12,
                "reason_codes": ["calculation"],
                "evidence": [{"pdf_id": "paper_a", "page_number": 1, "quote_text": "Six groups of two."}],
            },
            {
                "row_id": "row_2",
                "column_name": "Estimate",
                "proposed_value": 20,
                "reason_codes": ["figure_estimate"],
                "numeric_value_form": "exact",
                "evidence": [{"pdf_id": "paper_b", "page_number": 1, "quote_text": "See Figure 2."}],
            },
            {
                "row_id": "row_2",
                "column_name": "Estimate",
                "proposed_value": 0,
                "reason_codes": ["absence_inference"],
                "evidence": [],
            },
        ]
        write_review_input(run_dir, payload)

        completed, report = run_validation(run_dir)

        assert completed.returncode == 1
        assert report["ok"] is False
        assert any("has no calculation" in error for error in report["errors"])
        assert any("lacks page-specific figure_ref" in error for error in report["errors"])
        assert any("must use numeric_value_form='approximate'" in error for error in report["errors"])
        assert any("absence inference requires" in error for error in report["errors"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_default_fill_blanks_rejects_proposal_for_populated_cell() -> None:
    tmp_path = make_workspace("populated_default")
    try:
        run_dir = make_run(tmp_path)
        source_path = Path(read_review_input(run_dir)["source_table_path"])
        rows = read_csv(source_path)
        rows[0]["Finding"] = "existing value"
        write_csv(source_path, rows, list(rows[0]))

        completed, report = run_validation(run_dir)

        assert completed.returncode == 1
        assert report["ok"] is False
        assert any("targets populated cell" in error for error in report["errors"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_fill_and_verify_preserves_unreviewed_value_and_applies_accepted_correction() -> None:
    tmp_path = make_workspace("verify_mode")
    try:
        run_dir = make_run(tmp_path)
        payload = read_review_input(run_dir)
        source_path = Path(payload["source_table_path"])
        rows = read_csv(source_path)
        rows[0]["Finding"] = "existing value"
        write_csv(source_path, rows, list(rows[0]))
        payload["extraction_mode"] = "fill_and_verify"
        payload["rows"][0]["values"]["Finding"] = "existing value"
        payload["proposals"] = [
            {
                "row_id": "row_1",
                "column_name": "Finding",
                "proposed_value": "corrected value",
                "rationale": "The Results sentence reports corrected value for the current study.",
                "reason_codes": ["direct"],
                "evidence": [
                    {
                        "pdf_id": "paper_a",
                        "source_type": "direct_quote",
                        "page_number": 1,
                        "quote_text": "The current study reports corrected value.",
                    }
                ],
            }
        ]
        write_review_input(run_dir, payload)

        validation = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)
        assert validation["ok"] is True
        build_package(run_dir, with_review=True)

        proposal = read_jsonl(run_dir / "extraction" / "proposals.jsonl")[0]
        assert proposal["is_verify_mode"] is True
        assert proposal["existing_value"] == "existing value"
        assert read_csv(run_dir / "agent_review_filled.csv")[0]["Finding"] == "existing value"

        run_cmd(str(APPLY_SCRIPT), "--run", str(run_dir), "--accept-all", "--json")
        assert read_csv(run_dir / "agent_review_reviewed.csv")[0]["Finding"] == "corrected value"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_mixed_derivation_fixture_builds_and_routes_inferences_to_attention() -> None:
    tmp_path = make_workspace("mixed_derivations")
    try:
        run_dir = make_run(tmp_path)
        payload = read_review_input(run_dir)
        payload["columns"] = [
            {"column_name": "Direct", "field_type": "text"},
            {"column_name": "Calculated", "field_type": "number"},
            {"column_name": "Figure estimate", "field_type": "number"},
            {"column_name": "UMI?", "field_type": "text"},
        ]
        payload["proposals"] = [
            {
                "row_id": "row_1", "column_name": "Direct", "proposed_value": "yes", "reason_codes": ["direct"],
                "rationale": "The Methods explicitly state yes for the current assay.",
                "evidence": [{"pdf_id": "paper_a", "page_number": 1, "quote_text": "The current assay used this method."}],
            },
            {
                "row_id": "row_1", "column_name": "Calculated", "proposed_value": 12, "reason_codes": ["calculation"],
                "numeric_value_form": "exact", "calculation": "6 construct groups x 2 constructs/group = 12 constructs",
                "rationale": "Two compatible Methods operands yield 12 constructs for the same post-QC library.",
                "evidence": [{"pdf_id": "paper_a", "page_number": 1, "quote_text": "Six groups contained two constructs each."}],
            },
            {
                "row_id": "row_2", "column_name": "Figure estimate", "proposed_value": 18, "reason_codes": ["figure_estimate"],
                "numeric_value_form": "approximate", "rationale": "Rendered Figure 2B shows approximately 18 items.",
                "evidence": [{"pdf_id": "paper_b", "page_number": 1, "figure_ref": "Figure 2B", "caption_text": "Counts per sequence.", "approximate_highlight_regions": [{"page": 1, "x0": 0.1, "y0": 0.1, "x1": 0.4, "y1": 0.4}]}],
            },
            {
                "row_id": "row_2", "column_name": "UMI?", "proposed_value": "no (inferred)", "reason_codes": ["absence_inference"],
                "rationale": "Methods, primer sequences, and protocol annotations were audited without a UMI or random-N molecular identifier; reporter barcodes were not treated as UMIs.",
                "evidence": [{"pdf_id": "paper_b", "page_number": 1, "source_location": "Methods and primer audit", "reasoning": "The documented primer and library-preparation scope contains reporter barcodes but no UMI."}],
            },
        ]
        write_review_input(run_dir, payload)

        validation = json.loads(run_cmd(str(VALIDATE_SCRIPT), "--run", str(run_dir), "--mode", "authoring", "--json").stdout)
        assert validation["ok"] is True
        build_package(run_dir)
        proposals = read_jsonl(run_dir / "extraction" / "proposals.jsonl")
        absence = next(item for item in proposals if "absence_inference" in item["reason_codes"])
        figure = next(item for item in proposals if "figure_estimate" in item["reason_codes"])
        calculation = next(item for item in proposals if "calculation" in item["reason_codes"])
        assert absence["review_bucket"] == "attention"
        assert "absence_inference" in absence["warning_flags"]
        assert figure["review_bucket"] == "attention"
        assert figure["numeric_value_form"] == "approximate"
        assert calculation["evidence_status"] == "inferred_strong"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
