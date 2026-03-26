"""
Batch 6 — T106

Performance smoke tests for representative small and medium batches.

These tests verify that key pipeline operations complete within reasonable
time bounds so that obvious regressions in parsing, retrieval, extraction,
and review loading are caught early.

All tests use in-memory data (no real PDFs or LLM calls) so they are fast
and deterministic.

Time bounds are intentionally generous to avoid false failures on slow CI
machines. The goal is to catch catastrophic regressions (e.g., an O(n²)
loop) rather than micro-benchmark performance.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.app.artifacts import RunArtifacts
from backend.app.export import generate_audit_log, generate_diagnostics, generate_xlsx_export
from backend.app.ids import make_cell_id, make_proposal_id, make_review_decision_id
from backend.app.parsing import (
    ExtractedMetadata,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
)
from backend.app.retrieval import build_chunks, build_retrieval_result
from backend.app.review import list_proposals
from backend.app.schemas import ExportCandidate, ReviewDecision

from openpyxl import Workbook


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parsed_doc(pdf_id: str, n_blocks: int = 50) -> ParsedDocument:
    """Build a ParsedDocument with n_blocks text blocks."""
    blocks = [
        ParsedBlock(
            block_id=f"{pdf_id}_b{i}",
            block_type="paragraph",
            text=f"Paragraph {i}: This is a detailed description of the experimental results for block {i}.",
            normalized_text=f"paragraph {i}: this is a detailed description of the experimental results for block {i}.",
            page_no=(i // 10) + 1,
            reading_order=i,
        )
        for i in range(n_blocks)
    ]
    full_text = " ".join(b.text for b in blocks)
    return ParsedDocument(
        pdf_id=pdf_id,
        source_path=f"/fake/{pdf_id}.pdf",
        metadata=ExtractedMetadata(title=f"Paper {pdf_id}"),
        pages=[ParsedPage(page_no=p + 1, width=595.0, height=842.0) for p in range(5)],
        blocks=blocks,
        figures=[],
        tables=[],
        full_text=full_text,
        normalized_full_text=full_text.lower(),
    )


def _make_artifacts(tmp_path: Path, run_id: str) -> RunArtifacts:
    return RunArtifacts.create(tmp_path / "out", run_id)


def _make_candidate(
    row_id: str,
    column_name: str,
    accepted_value: str,
    run_id: str = "run_perf",
    pdf_id: str = "pdf_a",
) -> ExportCandidate:
    cell_id = make_cell_id(row_id, column_name)
    proposal_id = make_proposal_id(run_id, pdf_id, cell_id)
    return ExportCandidate(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        cell_id=cell_id,
        accepted_value=accepted_value,
        decision=ReviewDecision.ACCEPT,
    )


def _make_simple_xlsx(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))


# ---------------------------------------------------------------------------
# T106 — Retrieval performance
# ---------------------------------------------------------------------------


class TestRetrievalPerformance:
    """Build chunks and run retrieval over medium-sized documents."""

    def test_build_chunks_small_doc_under_500ms(self) -> None:
        """Building retrieval chunks for a small doc (50 blocks) should take < 500ms."""
        doc = _make_parsed_doc("pdf_perf_small", n_blocks=50)
        start = time.perf_counter()
        chunks = build_chunks(doc)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"build_chunks took {elapsed:.3f}s, expected < 0.5s"
        assert len(chunks) > 0

    def test_retrieval_query_small_doc_under_500ms(self) -> None:
        """Retrieval for a small doc (50 blocks) with a short query should take < 500ms."""
        doc = _make_parsed_doc("pdf_perf_ret", n_blocks=50)
        chunks = build_chunks(doc)
        start = time.perf_counter()
        result = build_retrieval_result(
            doc=doc,
            chunks=chunks,
            column_name="Method",
            column_description="primary experimental method technique",
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"build_retrieval_result took {elapsed:.3f}s, expected < 0.5s"
        assert result is not None

    def test_retrieval_medium_doc_under_2s(self) -> None:
        """Retrieval for a medium doc (200 blocks) should take < 2s."""
        doc = _make_parsed_doc("pdf_perf_med", n_blocks=200)
        chunks = build_chunks(doc)
        start = time.perf_counter()
        result = build_retrieval_result(
            doc=doc,
            chunks=chunks,
            column_name="Dataset",
            column_description="main dataset benchmark evaluation corpus",
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"build_retrieval_result (200 blocks) took {elapsed:.3f}s, expected < 2s"


# ---------------------------------------------------------------------------
# T106 — Review loading performance
# ---------------------------------------------------------------------------


class TestReviewLoadingPerformance:
    """Review state loading for many proposals should remain fast."""

    def test_list_proposals_100_under_1s(self, tmp_path: Path) -> None:
        """Listing 100 proposals from disk should take < 1s."""
        run_id = "perf_list"
        artifacts = _make_artifacts(tmp_path, run_id)

        for i in range(100):
            row_id = f"Row {i}"
            col = f"Col{i % 5}"
            cell_id = make_cell_id(row_id, col)
            proposal_id = make_proposal_id(run_id, f"pdf_{i}", cell_id)
            artifacts.append_jsonl("proposals/proposals.jsonl", {
                "proposal_id": proposal_id,
                "run_id": run_id,
                "pdf_id": f"pdf_{i}",
                "row_id": row_id,
                "column_name": col,
                "cell_id": cell_id,
                "source_mode": "text",
                "proposal_state": "found",
                "support_label": "direct_evidence",
                "proposed_value": f"value_{i}",
                "status_flags": [],
            })

        start = time.perf_counter()
        proposals = list_proposals(artifacts)
        elapsed = time.perf_counter() - start

        assert len(proposals) == 100
        assert elapsed < 1.0, f"list_proposals (100 items) took {elapsed:.3f}s, expected < 1s"

    def test_list_proposals_with_decisions_500_under_3s(self, tmp_path: Path) -> None:
        """Listing 500 proposals with decisions attached should take < 3s."""
        run_id = "perf_list_dec"
        artifacts = _make_artifacts(tmp_path, run_id)

        for i in range(500):
            row_id = f"Row {i}"
            col = "Method"
            cell_id = make_cell_id(row_id, col)
            proposal_id = make_proposal_id(run_id, f"pdf_{i}", cell_id)
            artifacts.append_jsonl("proposals/proposals.jsonl", {
                "proposal_id": proposal_id,
                "run_id": run_id,
                "pdf_id": f"pdf_{i}",
                "row_id": row_id,
                "column_name": col,
                "cell_id": cell_id,
                "source_mode": "text",
                "proposal_state": "found",
                "support_label": "direct_evidence",
                "proposed_value": f"value_{i}",
                "status_flags": [],
            })
            artifacts.append_jsonl("review/decisions.jsonl", {
                "decision_id": make_review_decision_id(run_id, proposal_id, 0),
                "run_id": run_id,
                "proposal_id": proposal_id,
                "cell_id": cell_id,
                "decision": "accept",
                "edited_value": None,
                "decided_at": datetime.now(timezone.utc).isoformat(),
            })

        start = time.perf_counter()
        proposals = list_proposals(artifacts)
        elapsed = time.perf_counter() - start

        assert len(proposals) == 500
        assert elapsed < 3.0, f"list_proposals (500 items + decisions) took {elapsed:.3f}s, expected < 3s"


# ---------------------------------------------------------------------------
# T106 — Export performance
# ---------------------------------------------------------------------------


class TestExportPerformance:
    """Export operations over small and medium batches should remain fast."""

    def test_xlsx_export_50_rows_under_2s(self, tmp_path: Path) -> None:
        """Exporting a workbook with 50 rows and 10 changes should take < 2s."""
        source = tmp_path / "source.xlsx"
        headers = ["Title"] + [f"Col{i}" for i in range(10)]
        rows = [[f"Row{i}"] + [f"val_{i}_{j}" for j in range(10)] for i in range(50)]
        _make_simple_xlsx(source, headers, rows)

        candidates = [
            _make_candidate(f"Row{i}", f"Col{i % 10}", f"new_val_{i}")
            for i in range(10)
        ]
        table_rows = [
            {h: (row[hi] if hi < len(row) else None) for hi, h in enumerate(headers)}
            for row in rows
        ]

        output = tmp_path / "out.xlsx"
        start = time.perf_counter()
        generate_xlsx_export(
            source_path=source,
            table_rows=table_rows,
            candidates=candidates,
            output_path=output,
        )
        elapsed = time.perf_counter() - start

        assert output.is_file()
        assert elapsed < 2.0, f"generate_xlsx_export (50 rows) took {elapsed:.3f}s, expected < 2s"

    def test_audit_log_100_entries_under_500ms(self, tmp_path: Path) -> None:
        """Generating an audit log with 100 entries should take < 500ms."""
        candidates = [
            _make_candidate(f"Row{i}", f"Col{i % 5}", f"new_val_{i}")
            for i in range(100)
        ]
        row_lookup = {f"Row{i}": {f"Col{j}": f"old_{i}_{j}" for j in range(5)} for i in range(100)}
        decision_records = [
            {
                "proposal_id": c.proposal_id,
                "decision_id": f"dec_{i}",
                "decided_at": datetime.now(timezone.utc).isoformat(),
            }
            for i, c in enumerate(candidates)
        ]

        output = tmp_path / "audit.csv"
        start = time.perf_counter()
        generate_audit_log(
            candidates=candidates,
            row_lookup=row_lookup,
            decision_records=decision_records,
            output_path=output,
        )
        elapsed = time.perf_counter() - start

        assert output.is_file()
        assert elapsed < 0.5, f"generate_audit_log (100 entries) took {elapsed:.3f}s, expected < 0.5s"

    def test_diagnostics_1000_proposals_under_1s(self) -> None:
        """Generating diagnostics for 1000 proposals should take < 1s."""
        proposals = [
            {
                "proposal_id": f"p{i}",
                "row_id": f"Row{i}",
                "column_name": "Method",
                "pdf_id": f"pdf_{i}",
                "proposal_state": "found" if i % 5 != 0 else "blocked",
                "status_flags": ["weak_evidence"] if i % 7 == 0 else [],
            }
            for i in range(1000)
        ]
        candidates = [
            _make_candidate(f"Row{i}", "Method", f"val_{i}")
            for i in range(100)
        ]

        start = time.perf_counter()
        diag = generate_diagnostics(
            run_id="perf_diag",
            proposals=proposals,
            decision_records=[],
            unresolved_matches=[],
            feature_warnings=[],
            candidates=candidates,
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"generate_diagnostics (1000 proposals) took {elapsed:.3f}s, expected < 1s"
        assert diag["export_summary"]["accepted_changes"] == 100
