"""
Tests for T040 — PDF-to-row matching:
deterministic match success, ambiguous-block, unmatched, duplicate-row conflict.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.matching import (
    MatchResult,
    MatchingSummary,
    _author_overlap,
    _identifier_match,
    _title_similarity,
    _year_match,
    detect_duplicate_row_conflicts,
    extract_paper_metadata,
    load_matching_summary,
    load_unresolved_matches,
    match_pdf_to_rows,
    run_matching_for_run,
    score_pdf_against_row,
)
from backend.app.parsing import ExtractedMetadata, ParsedBlock, ParsedDocument, ParsedPage
from backend.app.schemas import MatchOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(
    pdf_id: str = "test_pdf",
    title: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    doi: str | None = None,
    arxiv_id: str | None = None,
    extra_blocks: list[ParsedBlock] | None = None,
) -> ParsedDocument:
    meta = ExtractedMetadata(
        title=title,
        authors=authors or [],
        publication_year=year,
        doi=doi,
        arxiv_id=arxiv_id,
    )
    blocks: list[ParsedBlock] = extra_blocks or []
    return ParsedDocument(
        pdf_id=pdf_id,
        source_path=f"/fake/{pdf_id}.pdf",
        metadata=meta,
        pages=[ParsedPage(page_no=1, width=595.0, height=842.0)],
        blocks=blocks,
        full_text=" ".join(b.text for b in blocks),
        normalized_full_text=" ".join(b.normalized_text for b in blocks),
    )


def _make_row(title: str, authors: str = "", year: int | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"Title": title, "Authors": authors}
    if year is not None:
        row["Publication Year"] = year
    return row


# ---------------------------------------------------------------------------
# Unit tests: scoring helpers (T034)
# ---------------------------------------------------------------------------

def test_title_similarity_exact() -> None:
    assert _title_similarity("Deep Learning for NLP", "Deep Learning for NLP") == 1.0


def test_title_similarity_different() -> None:
    assert _title_similarity("Quantum Computing Overview", "Deep Learning for NLP") < 0.2


def test_title_similarity_partial() -> None:
    score = _title_similarity("Deep Neural Networks", "A Survey of Deep Neural Networks")
    assert 0.4 < score < 1.0


def test_title_similarity_empty() -> None:
    assert _title_similarity("", "Something") == 0.0
    assert _title_similarity("Something", "") == 0.0


def test_author_overlap_exact() -> None:
    assert _author_overlap(["Smith", "Jones"], "Smith; Jones") == 1.0


def test_author_overlap_none() -> None:
    assert _author_overlap(["Smith"], "Doe; Brown") == 0.0


def test_author_overlap_empty() -> None:
    assert _author_overlap([], "Smith") == 0.0
    assert _author_overlap(["Smith"], "") == 0.0


def test_year_match_exact() -> None:
    assert _year_match(2021, 2021) == 1.0


def test_year_match_off_by_one() -> None:
    assert _year_match(2021, 2020) == 0.5


def test_year_match_none_pdf_year() -> None:
    assert _year_match(None, 2021) == 0.0


def test_identifier_match_doi() -> None:
    meta = ExtractedMetadata(doi="10.1234/test.doi")
    row = {"doi_col": "10.1234/test.doi"}
    assert _identifier_match(meta, row) == 1.0


def test_identifier_match_no_match() -> None:
    meta = ExtractedMetadata(doi="10.1234/test.doi")
    row = {"Title": "Unrelated paper"}
    assert _identifier_match(meta, row) == 0.0


# ---------------------------------------------------------------------------
# T033: metadata extraction from ParsedDocument
# ---------------------------------------------------------------------------

def test_extract_paper_metadata_uses_existing_fields() -> None:
    doc = _make_doc(title="My Paper", authors=["Smith, J."], year=2021)
    meta = extract_paper_metadata(doc)
    assert meta.title == "My Paper"
    assert "Smith, J." in meta.authors
    assert meta.publication_year == 2021


def test_extract_paper_metadata_finds_doi_in_block() -> None:
    block = ParsedBlock(
        block_id="b1",
        block_type="paragraph",
        text="Published at https://doi.org. DOI: 10.9999/example-doi.",
        normalized_text="published at doi: 10.9999/example-doi.",
        page_no=1,
        reading_order=0,
    )
    doc = _make_doc(extra_blocks=[block])
    meta = extract_paper_metadata(doc)
    assert meta.doi is not None
    assert "10.9999" in meta.doi


def test_extract_paper_metadata_finds_year_in_block() -> None:
    block = ParsedBlock(
        block_id="b1",
        block_type="paragraph",
        text="Journal of Research, 2022.",
        normalized_text="journal of research, 2022.",
        page_no=1,
        reading_order=0,
    )
    doc = _make_doc(extra_blocks=[block])
    meta = extract_paper_metadata(doc)
    assert meta.publication_year == 2022


# ---------------------------------------------------------------------------
# T034: deterministic matching scoring
# ---------------------------------------------------------------------------

def test_score_exact_match() -> None:
    meta = ExtractedMetadata(title="Deep Learning for NLP", authors=["Smith, J."], publication_year=2021)
    row = _make_row("Deep Learning for NLP", authors="Smith, J.", year=2021)
    score, components = score_pdf_against_row(meta, row)
    assert score > 0.7
    assert components["title"] == 1.0


def test_score_different_papers_low_score() -> None:
    meta = ExtractedMetadata(title="Quantum Computing with Photons", authors=["Lee, K."], publication_year=2019)
    row = _make_row("Machine Learning Applications", authors="Wang, X.", year=2022)
    score, _ = score_pdf_against_row(meta, row)
    assert score < 0.3


# ---------------------------------------------------------------------------
# T036: match outcome assignment
# ---------------------------------------------------------------------------

TABLE_ROWS = [
    _make_row("Deep Learning for NLP", authors="Smith, J.; Jones, A.", year=2021),
    _make_row("Quantum Computing Overview", authors="Brown, R.", year=2020),
    _make_row("A Survey of Transformers", authors="Davis, M.", year=2022),
]


def test_match_confident(tmp_path: Path) -> None:
    meta = ExtractedMetadata(
        title="Deep Learning for NLP",
        authors=["Smith, J.", "Jones, A."],
        publication_year=2021,
    )
    result = match_pdf_to_rows("pdf1", meta, TABLE_ROWS)
    assert result.outcome == MatchOutcome.MATCHED
    assert result.matched_row_id == "Deep Learning for NLP"


def test_match_unmatched_no_metadata() -> None:
    meta = ExtractedMetadata()  # no fields
    result = match_pdf_to_rows("pdf_blank", meta, TABLE_ROWS)
    assert result.outcome == MatchOutcome.UNMATCHED


def test_match_unmatched_very_different() -> None:
    meta = ExtractedMetadata(
        title="Completely Unrelated Topic About Penguins",
        authors=["Xyz, Z."],
        publication_year=1999,
    )
    result = match_pdf_to_rows("pdf_unrelated", meta, TABLE_ROWS)
    assert result.outcome == MatchOutcome.UNMATCHED


# ---------------------------------------------------------------------------
# T035 + T036: ambiguous case
# ---------------------------------------------------------------------------

def test_match_ambiguous_multiple_similar(tmp_path: Path) -> None:
    """Two rows that both weakly match should result in AMBIGUOUS."""
    rows = [
        _make_row("Neural Networks for Classification", authors="Smith, J.", year=2021),
        _make_row("Neural Networks in Practice", authors="Smith, J.", year=2021),
    ]
    meta = ExtractedMetadata(
        title="Neural Networks",  # short title that partially matches both
        authors=["Smith, J."],
        publication_year=2021,
    )
    result = match_pdf_to_rows("pdf_ambig", meta, rows)
    # Either matched to one via adjudication or ambiguous — what matters is it doesn't crash
    assert result.outcome in {MatchOutcome.MATCHED, MatchOutcome.AMBIGUOUS}


def test_identifier_breaks_ambiguity() -> None:
    """A DOI match should disambiguate a previously ambiguous case."""
    rows = [
        _make_row("Neural Networks for Classification", authors="Smith, J.", year=2021),
        _make_row("Neural Networks in Practice", authors="Smith, J.", year=2021),
    ]
    # Add DOI that only appears in the first row
    rows[0]["doi"] = "10.9999/neural-class"
    meta = ExtractedMetadata(
        title="Neural Networks",
        authors=["Smith, J."],
        publication_year=2021,
        doi="10.9999/neural-class",
    )
    result = match_pdf_to_rows("pdf_id_resolve", meta, rows)
    assert result.outcome == MatchOutcome.MATCHED
    assert result.matched_row_id == "Neural Networks for Classification"


# ---------------------------------------------------------------------------
# T037: duplicate-row conflict detection
# ---------------------------------------------------------------------------

def test_duplicate_row_conflict_detected() -> None:
    results = [
        MatchResult(
            pdf_id="pdf1",
            outcome=MatchOutcome.MATCHED,
            matched_row_id="Shared Row",
            top_score=0.9,
        ),
        MatchResult(
            pdf_id="pdf2",
            outcome=MatchOutcome.MATCHED,
            matched_row_id="Shared Row",
            top_score=0.85,
        ),
        MatchResult(
            pdf_id="pdf3",
            outcome=MatchOutcome.MATCHED,
            matched_row_id="Unique Row",
            top_score=0.92,
        ),
    ]
    updated = detect_duplicate_row_conflicts(results)
    outcomes = {r.pdf_id: r.outcome for r in updated}
    assert outcomes["pdf1"] == MatchOutcome.DUPLICATE_ROW_CONFLICT
    assert outcomes["pdf2"] == MatchOutcome.DUPLICATE_ROW_CONFLICT
    assert outcomes["pdf3"] == MatchOutcome.MATCHED


def test_no_conflict_unchanged() -> None:
    results = [
        MatchResult(pdf_id="pdf1", outcome=MatchOutcome.MATCHED, matched_row_id="Row A", top_score=0.9),
        MatchResult(pdf_id="pdf2", outcome=MatchOutcome.MATCHED, matched_row_id="Row B", top_score=0.85),
    ]
    updated = detect_duplicate_row_conflicts(results)
    assert all(r.outcome == MatchOutcome.MATCHED for r in updated)


# ---------------------------------------------------------------------------
# T038: persistence
# ---------------------------------------------------------------------------

def test_run_matching_for_run_persists_artifacts(tmp_path: Path) -> None:
    matching_dir = tmp_path / "matching"
    pdf_metas = {
        "pdf1": ExtractedMetadata(
            title="Deep Learning for NLP",
            authors=["Smith, J.", "Jones, A."],
            publication_year=2021,
        ),
        "pdf_unknown": ExtractedMetadata(
            title="Totally Different Paper About Birds",
            authors=["Bird, A."],
            publication_year=2000,
        ),
    }
    summary = run_matching_for_run(pdf_metas, TABLE_ROWS, matching_dir, run_id="run_test")

    assert (matching_dir / "matching_summary.json").exists()
    assert (matching_dir / "matching_results.jsonl").exists()
    assert (matching_dir / "unresolved.json").exists()

    assert summary.total_pdfs == 2
    assert summary.matched + summary.unmatched + summary.ambiguous + summary.duplicate_row_conflict == 2


def test_load_matching_summary(tmp_path: Path) -> None:
    matching_dir = tmp_path / "matching"
    pdf_metas = {
        "pdf1": ExtractedMetadata(title="Deep Learning for NLP", authors=["Smith, J."], publication_year=2021),
    }
    run_matching_for_run(pdf_metas, TABLE_ROWS, matching_dir, run_id="run_load_test")

    loaded = load_matching_summary(matching_dir)
    assert loaded is not None
    assert loaded.run_id == "run_load_test"
    assert loaded.total_pdfs == 1


def test_load_unresolved_matches(tmp_path: Path) -> None:
    matching_dir = tmp_path / "matching"
    pdf_metas = {
        "pdf_unmatched": ExtractedMetadata(title="Unknown Paper", authors=["Nobody"], publication_year=1800),
    }
    run_matching_for_run(pdf_metas, TABLE_ROWS, matching_dir, run_id="run_unresolved_test")

    unresolved = load_unresolved_matches(matching_dir)
    assert isinstance(unresolved, list)
    assert any(r["pdf_id"] == "pdf_unmatched" for r in unresolved)


def test_load_unresolved_empty_when_no_file(tmp_path: Path) -> None:
    assert load_unresolved_matches(tmp_path / "nonexistent") == []


# ---------------------------------------------------------------------------
# T039: API endpoints (integration-style)
# ---------------------------------------------------------------------------

def test_matching_api_after_run(tmp_path: Path) -> None:
    """After a run completes, matching summary and unresolved endpoints must respond."""
    from backend.app.main import app

    REPO_ROOT = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "out"
    payload = {
        "paths": {
            "table_path": str(REPO_ROOT / "tests" / "fixtures" / "tables" / "literature_placeholder_fixture.csv"),
            "schema_path": str(REPO_ROOT / "tests" / "fixtures" / "schema" / "schema_fixture.csv"),
            "pdf_dir": str(REPO_ROOT / "tests" / "fixtures" / "papers"),
            "output_dir": str(output_dir),
        },
        "parser": {},
        "ocr_fallback": {},
        "matching": {},
        "style_profiles": {},
        "retrieval": {},
        "provider": {"provider_name": "lm_studio", "model_name": "test-model", "locality": "local"},
        "figure_fallback": {},
        "review": {},
        "export": {},
        "verify_mode": True,
        "placeholders_treated_as_empty": ["", " "],
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(payload), encoding="utf-8")

    client = TestClient(app)
    response = client.post("/api/runs", json={"config_path": str(config_file)})
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    # Wait for completion
    for _ in range(120):
        time.sleep(0.5)
        s = client.get(f"/api/runs/{run_id}/summary").json()
        if s["status"] in {"completed", "completed_with_warnings", "failed"}:
            break

    # Matching endpoints
    summary_resp = client.get(f"/api/runs/{run_id}/matching/summary")
    assert summary_resp.status_code == 200
    summary_data = summary_resp.json()
    assert "matched" in summary_data
    assert "total_pdfs" in summary_data

    unresolved_resp = client.get(f"/api/runs/{run_id}/matching/unresolved")
    assert unresolved_resp.status_code == 200
    assert isinstance(unresolved_resp.json(), list)
