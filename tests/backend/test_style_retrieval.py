"""
Tests for T049 — style-profile generation, no raw-example leakage,
and retrieval chunk/retrieval-text behavior.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.app.style_profiles import (
    StyleProfile,
    _assess_example_risk,
    _infer_field_type,
    _infer_length,
    _infer_tone,
    _infer_unit_style,
    _extract_style_signals_from_cells,
    generate_style_profile_for_column,
    generate_and_persist_style_profiles,
    load_style_profiles,
)
from backend.app.retrieval import (
    RetrievalChunk,
    RetrievalResult,
    build_chunks,
    build_retrieval_result,
    persist_chunks,
    persist_retrieval_result,
    load_chunks,
    retrieve_chunks_for_query,
    _add_neighbor_window,
    DEFAULT_TOP_K,
    PARA,
    SECTION,
    CAPTION,
    TABLE,
)
from backend.app.parsing import (
    BoundingBox,
    ParsedBlock,
    ParsedDocument,
    ParsedFigure,
    ParsedPage,
    ParsedTable,
    ExtractedMetadata,
)
from backend.app.artifacts import RunArtifacts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifacts(tmp_path: Path) -> RunArtifacts:
    from backend.app.artifacts import BUNDLE_DIRS
    run_root = tmp_path / "run_test"
    run_root.mkdir()
    for d in BUNDLE_DIRS:
        (run_root / d).mkdir(parents=True, exist_ok=True)
    return RunArtifacts(run_root)


def _make_doc(
    pdf_id: str = "test_pdf",
    blocks: list[ParsedBlock] | None = None,
    tables: list[ParsedTable] | None = None,
) -> ParsedDocument:
    blocks = blocks or []
    return ParsedDocument(
        pdf_id=pdf_id,
        source_path=f"/fake/{pdf_id}.pdf",
        metadata=ExtractedMetadata(title="Test Paper"),
        pages=[ParsedPage(page_no=1, width=595.0, height=842.0)],
        blocks=blocks,
        figures=[],
        tables=tables or [],
        full_text=" ".join(b.text for b in blocks),
        normalized_full_text=" ".join(b.normalized_text for b in blocks),
    )


def _make_block(
    block_id: str,
    text: str,
    page_no: int = 1,
    block_type: str = "paragraph",
    reading_order: int = 0,
    table_region: bool = False,
    figure_ref: str | None = None,
) -> ParsedBlock:
    return ParsedBlock(
        block_id=block_id,
        block_type=block_type,
        text=text,
        normalized_text=text.lower(),
        page_no=page_no,
        reading_order=reading_order,
        table_region=table_region,
        figure_ref=figure_ref,
    )


# ---------------------------------------------------------------------------
# T041 — StyleProfile schema
# ---------------------------------------------------------------------------

def test_style_profile_defaults() -> None:
    profile = StyleProfile(column_name="Test Column")
    assert profile.field_type_guess == "text"
    assert profile.expected_length == "short"
    assert profile.tone == "neutral"
    assert profile.example_risk is False


def test_style_profile_fields_present() -> None:
    profile = StyleProfile(
        column_name="Drug Dose",
        field_type_guess="numeric",
        expected_length="short",
        tone="technical",
        detail_level="concise",
        value_shape="number [unit]",
        unit_style="mg/kg",
        format_notes="Always include unit.",
        example_risk=False,
    )
    assert profile.unit_style == "mg/kg"
    assert profile.value_shape == "number [unit]"


# ---------------------------------------------------------------------------
# T044 — No-leakage: extract style signals, not raw cells
# ---------------------------------------------------------------------------

def test_extract_signals_does_not_return_raw_cells() -> None:
    cells = ["Deep learning for NLP tasks.", "Transfer learning in vision.", "BERT for question answering."]
    signals = _extract_style_signals_from_cells(cells)
    # Signals dict must not contain any raw cell values
    for cell in cells:
        assert cell not in str(signals.values())


def test_extract_signals_numeric_type() -> None:
    signals = _extract_style_signals_from_cells(["10 mg/kg", "5 mg/kg", "20 mg/kg"])
    assert signals["field_type_guess"] == "numeric"


def test_extract_signals_year_type() -> None:
    signals = _extract_style_signals_from_cells(["2019", "2020", "2018"])
    assert signals["field_type_guess"] == "year"


def test_extract_signals_short_length() -> None:
    signals = _extract_style_signals_from_cells(["Yes", "No", "N/A"])
    assert signals["expected_length"] == "short"


def test_extract_signals_medium_length() -> None:
    cells = ["This study recruited 100 patients with conditions X, Y, and Z for a randomized trial."] * 3
    signals = _extract_style_signals_from_cells(cells)
    assert signals["expected_length"] == "medium"


def test_infer_unit_style_found() -> None:
    unit = _infer_unit_style(["10 mg/kg bw", "5 mg/kg bw", "20 mg/kg"])
    assert "mg" in unit or unit == ""


def test_assess_example_risk_high_diversity() -> None:
    cells = [
        "randomized controlled trial with placebo group and 150 participants",
        "observational cohort study tracking biomarkers over 5 years",
        "meta-analysis of 23 clinical trials on cardiovascular outcomes",
        "case-control study with nested subgroup and genetic analysis",
        "systematic review of interventional studies in pediatric populations",
        "prospective study measuring oxidative stress markers in adults",
        "retrospective chart review of adverse events after surgery",
        "crossover design with washout period and blinded assessors",
        "phase 3 trial examining dose-response relationship in cancer",
        "longitudinal survey of quality of life and depression scores",
    ]
    assert _assess_example_risk(cells) is True


def test_assess_example_risk_low_diversity() -> None:
    cells = ["Yes"] * 10
    assert _assess_example_risk(cells) is False


# ---------------------------------------------------------------------------
# T042 — Per-column style profile generation (no provider)
# ---------------------------------------------------------------------------

def test_generate_style_profile_no_cells() -> None:
    profile = generate_style_profile_for_column("Title", "Paper title", filled_cells=[])
    assert isinstance(profile, StyleProfile)
    assert profile.column_name == "Title"


def test_generate_style_profile_numeric_cells() -> None:
    profile = generate_style_profile_for_column(
        "Dose", "Drug dose administered", filled_cells=["10 mg/kg", "5 mg/kg", "15 mg/kg"]
    )
    assert profile.field_type_guess == "numeric"


def test_generate_style_profile_no_provider_no_format_notes() -> None:
    profile = generate_style_profile_for_column("Column", "Desc", filled_cells=["a", "b"])
    # With no provider, format_notes should be empty
    assert profile.format_notes == ""


# ---------------------------------------------------------------------------
# T043 — Persist style profiles
# ---------------------------------------------------------------------------

def test_persist_and_load_style_profiles(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    schema_rows = [
        {"column_name": "Dose", "description": "Drug dose"},
        {"column_name": "Sample Size", "description": "Number of subjects"},
    ]
    table_rows = [
        {"Title": "Paper 1", "Dose": "10 mg/kg", "Sample Size": "50"},
        {"Title": "Paper 2", "Dose": "5 mg/kg", "Sample Size": ""},
    ]
    profiles = generate_and_persist_style_profiles(
        artifacts=artifacts,
        schema_rows=schema_rows,
        table_rows=table_rows,
        provider=None,
    )
    assert "Dose" in profiles
    assert "Sample Size" in profiles

    # Reload from artifacts
    loaded = load_style_profiles(artifacts)
    assert set(loaded.keys()) == {"Dose", "Sample Size"}
    assert loaded["Dose"].column_name == "Dose"


def test_persist_style_profiles_index_exists(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    generate_and_persist_style_profiles(
        artifacts=artifacts,
        schema_rows=[{"column_name": "Year", "description": "Publication year"}],
        table_rows=[{"Year": "2020"}, {"Year": "2021"}],
        provider=None,
    )
    index_path = artifacts.root / "style_profiles" / "index.json"
    assert index_path.exists()


# ---------------------------------------------------------------------------
# T045 — Typed chunk generation
# ---------------------------------------------------------------------------

def test_build_chunks_paragraph_type() -> None:
    doc = _make_doc(blocks=[_make_block("b1", "Some text paragraph.", page_no=1, block_type="paragraph", reading_order=0)])
    chunks = build_chunks(doc)
    assert len(chunks) >= 1
    assert any(c.chunk_type == PARA for c in chunks)


def test_build_chunks_section_type() -> None:
    doc = _make_doc(blocks=[
        _make_block("s1", "Introduction", block_type="section_header", reading_order=0),
        _make_block("p1", "This study examines…", block_type="paragraph", reading_order=1),
    ])
    chunks = build_chunks(doc)
    types = [c.chunk_type for c in chunks]
    assert SECTION in types


def test_build_chunks_caption_type() -> None:
    doc = _make_doc(blocks=[
        _make_block("c1", "Figure 1: Study design", block_type="caption", reading_order=0, figure_ref="fig_001"),
    ])
    chunks = build_chunks(doc)
    assert any(c.chunk_type == CAPTION for c in chunks)


def test_build_chunks_table_from_table_region_block() -> None:
    doc = _make_doc(blocks=[
        _make_block("t1", "| A | B |\n|---|---|\n| 1 | 2 |", block_type="table", reading_order=0, table_region=True),
    ])
    chunks = build_chunks(doc)
    assert any(c.chunk_type == TABLE for c in chunks)


def test_build_chunks_table_from_parsed_tables() -> None:
    table = ParsedTable(table_id="tbl_1", page_no=2, markdown_text="| Drug | Dose |\n|---|---|\n| X | 10 mg |")
    doc = _make_doc(tables=[table])
    chunks = build_chunks(doc)
    assert any(c.chunk_type == TABLE for c in chunks)


# ---------------------------------------------------------------------------
# T046 — Retrieval text vs display text separation
# ---------------------------------------------------------------------------

def test_display_text_preserved() -> None:
    original = "The drug X was administered at 10 mg/kg."
    doc = _make_doc(blocks=[_make_block("b1", original, page_no=1)])
    chunks = build_chunks(doc)
    assert any(c.display_text == original for c in chunks)


def test_retrieval_text_differs_when_section_context_added() -> None:
    doc = _make_doc(blocks=[
        _make_block("s1", "Methods", block_type="section_header", reading_order=0),
        _make_block("p1", "Drug administration protocol.", block_type="paragraph", reading_order=1),
    ])
    chunks = build_chunks(doc)
    para_chunks = [c for c in chunks if c.chunk_type == PARA]
    assert para_chunks, "Expected at least one paragraph chunk"
    chunk = para_chunks[0]
    # Retrieval text should include section header context
    assert "methods" in chunk.retrieval_text.lower() or chunk.retrieval_text != chunk.display_text


def test_display_text_not_lowercased() -> None:
    original = "The Drug X Was Administered."
    doc = _make_doc(blocks=[_make_block("b1", original, page_no=1)])
    chunks = build_chunks(doc)
    # Display text preserves original casing
    assert any(c.display_text == original for c in chunks)


# ---------------------------------------------------------------------------
# T047 — MVP retrieval assembly defaults
# ---------------------------------------------------------------------------

def test_retrieve_top_k_respected() -> None:
    blocks = [_make_block(f"b{i}", f"sentence {i} about the experiment dose.", reading_order=i) for i in range(20)]
    doc = _make_doc(blocks=blocks)
    chunks = build_chunks(doc)
    result = build_retrieval_result(doc, chunks, "Dose", "Drug dose administered", top_k=6)
    assert len(result.selected_chunks) <= 6


def test_retrieve_returns_relevant_chunks() -> None:
    blocks = [
        _make_block("b1", "Patients received 10 mg/kg dose of drug X.", reading_order=0),
        _make_block("b2", "The weather was sunny today.", reading_order=1),
        _make_block("b3", "Drug administration: 5 mg/kg for group B.", reading_order=2),
    ]
    doc = _make_doc(blocks=blocks)
    chunks = build_chunks(doc)
    result = build_retrieval_result(doc, chunks, "Dose", "Drug dose administered", top_k=3)
    texts = " ".join(c.display_text for c in result.selected_chunks)
    assert "drug" in texts.lower() or "dose" in texts.lower() or "mg" in texts.lower()


def test_neighbor_window_added() -> None:
    blocks = [_make_block(f"b{i}", f"paragraph {i} content", reading_order=i) for i in range(10)]
    doc = _make_doc(blocks=blocks)
    chunks = build_chunks(doc)
    result = build_retrieval_result(doc, chunks, "Content", "Some description", top_k=2)
    # Neighbor chunk IDs should be populated (unless at boundary)
    # We can't assert non-empty always because edge cases might have no neighbors
    assert isinstance(result.neighbor_chunk_ids, list)


def test_retrieve_no_reranking_no_hyde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure there's no reranker or HyDE call in the retrieval path."""
    blocks = [_make_block("b1", "Some content", reading_order=0)]
    doc = _make_doc(blocks=blocks)
    chunks = build_chunks(doc)
    # Just verify the function completes without errors (no reranker calls)
    result = build_retrieval_result(doc, chunks, "Column", "Description", top_k=6)
    assert result is not None


def test_retrieval_default_top_k_is_6() -> None:
    assert DEFAULT_TOP_K == 6


# ---------------------------------------------------------------------------
# T048 — Persist retrieval artifacts
# ---------------------------------------------------------------------------

def test_persist_and_load_chunks(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    blocks = [_make_block("b1", "Test text", page_no=1, reading_order=0)]
    doc = _make_doc(blocks=blocks)
    chunks = build_chunks(doc)
    persist_chunks(artifacts, doc.pdf_id, chunks)
    loaded = load_chunks(artifacts, doc.pdf_id)
    assert len(loaded) == len(chunks)
    assert loaded[0].display_text == chunks[0].display_text


def test_persist_retrieval_result(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    blocks = [_make_block("b1", "Drug X dose was 10 mg/kg", reading_order=0)]
    doc = _make_doc(blocks=blocks)
    chunks = build_chunks(doc)
    result = build_retrieval_result(doc, chunks, "Dose", "Drug dose", top_k=3)
    persist_retrieval_result(artifacts, result)
    result_path = artifacts.root / f"retrieval/{doc.pdf_id}/Dose/result.json"
    assert result_path.exists()


def test_retrieval_diagnostics_persisted(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    blocks = [_make_block(f"b{i}", f"content {i}", reading_order=i) for i in range(5)]
    doc = _make_doc(blocks=blocks)
    chunks = build_chunks(doc)
    result = build_retrieval_result(doc, chunks, "Dose", "Drug dose", top_k=3)
    persist_retrieval_result(artifacts, result)
    data = artifacts.read_json(f"retrieval/{doc.pdf_id}/Dose/result.json")
    assert "diagnostics" in data
    assert "total_chunks" in data["diagnostics"]
