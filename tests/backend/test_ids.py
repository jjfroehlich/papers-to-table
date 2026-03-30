"""Tests for stable ID generation."""
from __future__ import annotations

import re

import pytest

from backend.app.ids import (
    generate_cell_id,
    generate_evidence_id,
    generate_pdf_id,
    generate_proposal_id,
    generate_review_decision_id,
    generate_row_id,
    generate_run_id,
)


class TestRunId:
    def test_format(self):
        rid = generate_run_id()
        assert re.match(r"^run_\d{8}_\d{6}_[a-z0-9]{6}$", rid), f"Bad format: {rid}"

    def test_uniqueness(self):
        ids = {generate_run_id() for _ in range(20)}
        assert len(ids) == 20  # all unique due to suffix

    def test_starts_with_run(self):
        assert generate_run_id().startswith("run_")


class TestCellId:
    def test_deterministic(self):
        a = generate_cell_id("row_abc", "Journal")
        b = generate_cell_id("row_abc", "Journal")
        assert a == b

    def test_different_columns_differ(self):
        a = generate_cell_id("row_abc", "Journal")
        b = generate_cell_id("row_abc", "Abstract")
        assert a != b

    def test_different_rows_differ(self):
        a = generate_cell_id("row_abc", "Journal")
        b = generate_cell_id("row_def", "Journal")
        assert a != b

    def test_prefix(self):
        assert generate_cell_id("row_1", "Col").startswith("cell_")

    def test_length_reasonable(self):
        cid = generate_cell_id("row_abc", "Journal")
        assert len(cid) < 50


class TestPdfId:
    def test_stable(self):
        a = generate_pdf_id("paper_1.pdf")
        b = generate_pdf_id("paper_1.pdf")
        assert a == b

    def test_different_files(self):
        a = generate_pdf_id("paper_1.pdf")
        b = generate_pdf_id("paper_2.pdf")
        assert a != b

    def test_prefix(self):
        assert generate_pdf_id("paper.pdf").startswith("pdf_")

    def test_no_spaces(self):
        pid = generate_pdf_id("my paper file.pdf")
        assert " " not in pid


class TestRowId:
    def test_deterministic(self):
        a = generate_row_id(0, "Some Title")
        b = generate_row_id(0, "Some Title")
        assert a == b

    def test_different_indices(self):
        a = generate_row_id(0, "Title")
        b = generate_row_id(1, "Title")
        assert a != b

    def test_prefix(self):
        assert generate_row_id(0, "").startswith("row_")


class TestProposalId:
    def test_contains_run_and_cell(self):
        pid = generate_proposal_id("run_20240315_143022_abc123", "cell_abc123def456")
        assert "run_20240315_143022_abc123" in pid
        assert "cell_abc123def456" in pid

    def test_prefix(self):
        pid = generate_proposal_id("run_1", "cell_1")
        assert pid.startswith("prop_")


class TestEvidenceId:
    def test_prefix(self):
        eid = generate_evidence_id("prop_1")
        assert eid.startswith("ev_")

    def test_unique(self):
        ids = {generate_evidence_id("prop_1") for _ in range(20)}
        assert len(ids) == 20


class TestReviewDecisionId:
    def test_prefix(self):
        rid = generate_review_decision_id("prop_1")
        assert rid.startswith("rev_")

    def test_unique(self):
        ids = {generate_review_decision_id("prop_1") for _ in range(20)}
        assert len(ids) == 20
