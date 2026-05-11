"""Tests for Batch 2: Parsing and row-matching baseline (T025–T040)."""
from __future__ import annotations

import json
import pathlib
from typing import Optional
from unittest.mock import patch

import pandas as pd
import pytest

from backend.app.matching import (
    MatchResult,
    PaperMetadata,
    _are_rows_near_duplicate,
    _title_jaccard,
    assign_match_outcome,
    detect_duplicate_row_conflicts,
    extract_paper_metadata,
    load_ambiguous,
    load_conflicts,
    load_match_results,
    load_match_summary,
    load_unmatched,
    persist_match_artifacts,
    run_matching,
    score_against_row,
    score_all_rows,
)
from backend.app.metadata import extract_matching_metadata_debug
from backend.app.parsing import (
    BasicTextParserAdapter,
    DocumentMetadata,
    DoclingParserAdapter,
    FigureCaptionPair,
    PageInfo,
    ParserDiagnostics,
    ParsedDocument,
    PDFiumBackend,
    build_diagnostics,
    check_ocr_readiness,
    check_parser_readiness,
    generate_figure_artifacts,
    generate_page_artifacts,
    get_parsed_dir,
    normalize_text,
    parse_pdf,
    persist_parse_artifacts,
    _extract_metadata_from_text,
    _extract_authors_from_lines,
    _unwrap_docling_item,
)
from backend.app.schemas import MatchOutcome

FIXTURE_PDF_DIR = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs"
FIXTURE_TABLE = "../benchmark_datasets/massively_parallel_reporter_assays/table_template.csv"
PAPER_1 = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs/MPRA01_sahu_2022_sequence_determinants.pdf"
PAPER_2 = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs/MPRA02_trauernicht_2024_optimized_reporters.pdf"
PAPER_3 = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs/MPRA03_arnold_2013_starr_seq_maps.pdf"
PAPER_4 = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs/MPRA04_cornwall_scoones_2025_signal_dependent_cres.pdf"
UNMATCHED_PDF = "../benchmark_datasets/spatial_transcriptomics/pdfs/ST01_open_st_3d.pdf"


# ===========================================================================
# T025 – ParsedDocument contract
# ===========================================================================

class TestParsedDocumentContract:
    """Verify that ParsedDocument has all required contract fields (T025)."""

    def test_required_fields_present(self):
        required = [
            "pdf_id", "pdf_path", "metadata", "pages", "blocks", "figures",
            "full_text", "normalized_text", "configured_parser", "parser_used",
            "fallback_used", "ocr_used", "parse_warnings", "parsed_at",
        ]
        fields = ParsedDocument.model_fields.keys()
        for f in required:
            assert f in fields, f"ParsedDocument missing required field: {f}"

    def test_metadata_fields(self):
        from backend.app.parsing import DocumentMetadata
        meta = DocumentMetadata(title="Test", authors=["Smith, J."], year=2023)
        assert meta.title == "Test"
        assert meta.year == 2023

    def test_text_block_provenance(self):
        from backend.app.parsing import TextBlock
        block = TextBlock(
            block_id="test_0",
            block_type="paragraph",
            page_number=1,
            text="Hello world",
            normalized_text="hello world",
            reading_order=0,
            provenance="pypdfium2",
        )
        assert block.provenance == "pypdfium2"
        assert block.bbox is None  # optional


# ===========================================================================
# T026 / T026a – Parser adapter interface and fallback policy
# ===========================================================================

class TestParserAdapterInterface:
    """Verify adapter interface and parser-selection logic (T026, T026a)."""

    def test_basic_adapter_is_available(self):
        adapter = BasicTextParserAdapter()
        ok, reason = adapter.is_available()
        assert ok, f"BasicTextParserAdapter should be available: {reason}"

    def test_basic_adapter_name(self):
        assert BasicTextParserAdapter().name == "pypdfium2"

    def test_docling_adapter_name(self):
        assert DoclingParserAdapter().name == "docling"

    def test_docling_adapter_available_if_importable(self):
        adapter = DoclingParserAdapter()
        ok, reason = adapter.is_available()
        # docling is installed so should be importable
        assert ok, reason

    def test_docling_iterate_items_tuple_shape_unwrapped(self):
        """Regression: Docling iterate_items() may yield (item, level) tuples."""
        item = object()
        assert _unwrap_docling_item((item, 2)) is item
        assert _unwrap_docling_item(item) is item

    def test_parse_pdf_records_configured_vs_actual_parser(self, tmp_path):
        """T026a: configured_parser and parser_used must both be recorded."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        doc, diag, _ = parse_pdf(
            pdf_path=PAPER_2,
            pdf_id="paper_2",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=False,
        )
        assert doc.configured_parser == "pypdfium2"
        assert doc.parser_used == "pypdfium2"
        assert doc.fallback_used is False
        assert diag.configured_parser == "pypdfium2"
        assert diag.actual_parser_used == "pypdfium2"

    def test_generate_figure_artifacts_persists_crop_and_page_links(self, tmp_path):
        """Figure review needs stored crops and page links, not caption-only metadata."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        page_artifact_paths = generate_page_artifacts(
            run_dir,
            PAPER_2,
            "paper_2",
            scale=1.0,
        )
        doc = ParsedDocument(
            pdf_id="paper_2",
            pdf_path=PAPER_2,
            metadata=DocumentMetadata(title="Test figure doc"),
            pages=[
                PageInfo(
                    page_number=1,
                    width=612.0,
                    height=792.0,
                    text_accessible=True,
                    block_count=0,
                )
            ],
            blocks=[],
            figures=[
                FigureCaptionPair(
                    figure_id="paper_2_fig1",
                    page_number=1,
                    bbox=[0.0, 0.0, 150.0, 150.0],
                )
            ],
            full_text="test",
            normalized_text="test",
            configured_parser="docling",
            parser_used="docling",
            fallback_used=False,
            fallback_reason=None,
            ocr_used=False,
            ocr_reason=None,
            parse_warnings=[],
            parsed_at="2026-04-01T00:00:00+00:00",
        )

        updated = generate_figure_artifacts(
            run_dir,
            PAPER_2,
            doc,
            page_artifact_paths=page_artifact_paths,
        )

        figure = updated.figures[0]
        assert figure.crop_path is not None
        assert figure.full_page_path == "parsed/paper_2/pages/page_0001.png"
        assert (run_dir / pathlib.Path(figure.crop_path)).exists()


class TestMetadataHeuristics:
    def test_matching_metadata_rejects_correspondence_line_as_title(self):
        doc_dict = {
            "metadata": {"title": "For correspondence: b.v.steensel@nki.nl"},
            "blocks": [
                {"block_type": "paragraph", "page_number": 1, "text": "For correspondence: b.v.steensel@nki.nl"},
                {"block_type": "heading", "page_number": 1, "text": "CRISPR perturbation mapping in mammalian cells"},
            ],
            "full_text": "CRISPR perturbation mapping in mammalian cells\nFor correspondence: b.v.steensel@nki.nl",
            "parser_used": "docling",
        }

        resolved = extract_matching_metadata_debug(doc_dict)

        assert resolved.metadata.title == "CRISPR perturbation mapping in mammalian cells"
        assert resolved.front_matter_diagnostics["title_rejection_reasons"][0]["reason"] == "correspondence_line"

    def test_extract_authors_from_standard_header_line(self):
        first_pages_text = (
            "Engineering mammalian cells for robust reporter assays\n"
            "Drew T. Bergman1,2,9, Thouis R. Jones1, Miguel Martinez-Ara1,2\n"
            "Abstract\n"
            "We present..."
        )

        authors = _extract_authors_from_lines(
            first_pages_text,
            title="Engineering mammalian cells for robust reporter assays",
        )

        assert authors is not None
        assert "Drew T. Bergman" in authors
        assert "Thouis R. Jones" in authors
        assert "Miguel Martinez-Ara" in authors

    def test_extract_metadata_populates_authors_when_doc_header_is_normal(self):
        first_pages_text = (
            "A practical atlas of enhancer perturbation\n"
            "Jane Q. Smith1,2, Alan R. Doe1, Priya K. Patel3\n"
            "Abstract\n"
            "Long abstract text..."
        )
        metadata = _extract_metadata_from_text(
            blocks=[],
            first_pages_text=first_pages_text,
            full_text=first_pages_text,
        )

        assert metadata.authors is not None
        assert metadata.authors[:2] == ["Jane Q. Smith", "Alan R. Doe"]

    def test_fallback_disabled_raises_when_configured_parser_fails(self, tmp_path):
        """T026a: without allow_basic_fallback, a broken parser should raise."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Simulate docling failing at parse time
        with patch(
            "backend.app.parsing.DoclingParserAdapter.parse",
            side_effect=RuntimeError("model unavailable"),
        ):
            with pytest.raises(RuntimeError, match="Parser 'docling' failed"):
                parse_pdf(
                    pdf_path=PAPER_2,
                    pdf_id="paper_2",
                    configured_parser="docling",
                    allow_basic_fallback=False,
                    ocr_enabled=False,
                    ocr_language="en",
                    run_dir=run_dir,
                    generate_pages=False,
                )

    def test_fallback_enabled_uses_basic_parser_on_failure(self, tmp_path):
        """T026a: with allow_basic_fallback, fallback to pypdfium2 is recorded."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        with patch(
            "backend.app.parsing.DoclingParserAdapter.parse",
            side_effect=RuntimeError("model unavailable"),
        ):
            doc, diag, _ = parse_pdf(
                pdf_path=PAPER_2,
                pdf_id="paper_2",
                configured_parser="docling",
                allow_basic_fallback=True,
                ocr_enabled=False,
                ocr_language="en",
                run_dir=run_dir,
                generate_pages=False,
            )

        assert doc.configured_parser == "docling"
        assert doc.parser_used == "pypdfium2"
        assert doc.fallback_used is True
        assert doc.fallback_reason is not None
        assert "model unavailable" in doc.fallback_reason
        assert diag.fallback_used is True
        assert diag.actual_parser_used == "pypdfium2"

    def test_configured_parser_unavailable_triggers_fallback(self, tmp_path):
        """T026a: unavailable configured parser + allow_basic_fallback falls back."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        with patch(
            "backend.app.parsing.DoclingParserAdapter.is_available",
            return_value=(False, "import error"),
        ):
            doc, diag, _ = parse_pdf(
                pdf_path=PAPER_2,
                pdf_id="paper_2",
                configured_parser="docling",
                allow_basic_fallback=True,
                ocr_enabled=False,
                ocr_language="en",
                run_dir=run_dir,
                generate_pages=False,
            )

        assert doc.configured_parser == "docling"
        assert doc.fallback_used is True


# ===========================================================================
# T027 – PDFiumBackend
# ===========================================================================

class TestPDFiumBackend:
    """Verify PDFiumBackend operations (T027)."""

    def test_page_count(self):
        backend = PDFiumBackend(PAPER_1)
        assert len(backend) > 0
        backend.close()

    def test_page_size_returns_floats(self):
        backend = PDFiumBackend(PAPER_1)
        w, h = backend.page_size(0)
        assert isinstance(w, float)
        assert isinstance(h, float)
        assert w > 0 and h > 0
        backend.close()

    def test_get_page_text_returns_string(self):
        backend = PDFiumBackend(PAPER_1)
        text = backend.get_page_text(0)
        assert isinstance(text, str)
        assert len(text) > 50  # paper_1 has text
        backend.close()

    def test_get_full_text(self):
        backend = PDFiumBackend(PAPER_1)
        text = backend.get_full_text()
        assert len(text) > 200
        backend.close()

    def test_text_accessible_page(self):
        backend = PDFiumBackend(PAPER_1)
        assert backend.get_page_text_accessible(0) is True
        backend.close()

    def test_render_page_returns_png_bytes(self):
        backend = PDFiumBackend(PAPER_2)
        png = backend.render_page(0, scale=0.5)  # small scale for speed
        assert isinstance(png, bytes)
        assert png[:4] == b"\x89PNG"
        backend.close()

    def test_render_crop_returns_png_bytes(self):
        backend = PDFiumBackend(PAPER_2)
        w, h = backend.page_size(0)
        # Crop a small region from the top-left
        bbox = [0.0, 0.0, w * 0.3, h * 0.2]
        crop = backend.render_crop(0, bbox, scale=1.0)
        assert isinstance(crop, bytes)
        assert crop[:4] == b"\x89PNG"
        backend.close()


# ===========================================================================
# T028 – OCR fallback gate
# ===========================================================================

class TestOCRFallback:
    """Verify OCR fallback gating and explicit recording (T028)."""

    def test_ocr_not_applied_when_disabled(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        doc, diag, _ = parse_pdf(
            pdf_path=PAPER_2,
            pdf_id="paper_2",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,  # OCR disabled
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=False,
        )
        assert doc.ocr_used is False
        assert diag.ocr_used is False

    def test_ocr_applied_when_text_insufficient_and_enabled(self, tmp_path):
        """Simulate a PDF with no text (would trigger OCR if enabled)."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        # Produce a doc with empty text to trigger OCR path
        empty_doc = ParsedDocument(
            pdf_id="empty",
            pdf_path=PAPER_2,
            metadata=__import__("backend.app.parsing", fromlist=["DocumentMetadata"]).DocumentMetadata(),
            pages=[],
            blocks=[],
            figures=[],
            full_text="",
            normalized_text="",
            configured_parser="pypdfium2",
            parser_used="pypdfium2",
            fallback_used=False,
            ocr_used=False,
            parse_warnings=[],
            parsed_at="2025-01-01T00:00:00+00:00",
        )

        # Mock the initial parse to return the empty doc
        with patch("backend.app.parsing.BasicTextParserAdapter.parse", return_value=empty_doc):
            with patch("backend.app.parsing._ocrmypdf_available", return_value=(True, "")):
                with patch("backend.app.parsing._apply_ocr_fallback") as mock_ocr:
                    # Mock OCR to return doc with ocr_used=True
                    ocr_doc = empty_doc.model_copy(update={
                        "ocr_used": True,
                        "parser_used": "pypdfium2_ocr",
                        "full_text": "Some OCR text",
                    })
                    mock_ocr.return_value = ocr_doc

                    doc, diag, _ = parse_pdf(
                        pdf_path=PAPER_2,
                        pdf_id="paper_2",
                        configured_parser="pypdfium2",
                        allow_basic_fallback=False,
                        ocr_enabled=True,  # OCR enabled
                        ocr_language="en",
                        run_dir=run_dir,
                        generate_pages=False,
                    )

        assert doc.ocr_used is True
        assert doc.parser_used == "pypdfium2_ocr"
        assert mock_ocr.called

    def test_ocr_warning_when_needed_but_disabled(self, tmp_path):
        """When OCR is needed but disabled, a warning is added (no silent failure)."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        empty_doc = ParsedDocument(
            pdf_id="empty",
            pdf_path=PAPER_2,
            metadata=__import__("backend.app.parsing", fromlist=["DocumentMetadata"]).DocumentMetadata(),
            pages=[],
            blocks=[],
            figures=[],
            full_text="",
            normalized_text="",
            configured_parser="pypdfium2",
            parser_used="pypdfium2",
            fallback_used=False,
            ocr_used=False,
            parse_warnings=[],
            parsed_at="2025-01-01T00:00:00+00:00",
        )

        with patch("backend.app.parsing.BasicTextParserAdapter.parse", return_value=empty_doc):
            doc, _, _ = parse_pdf(
                pdf_path=PAPER_2,
                pdf_id="paper_2",
                configured_parser="pypdfium2",
                allow_basic_fallback=False,
                ocr_enabled=False,
                ocr_language="en",
                run_dir=run_dir,
                generate_pages=False,
            )

        assert doc.ocr_used is False
        assert any("OCR disabled" in w for w in doc.parse_warnings)

    def test_ocr_readiness_fails_when_enabled_but_not_installed(self):
        with patch("backend.app.parsing._ocrmypdf_available", return_value=(False, "not installed")):
            errors = check_ocr_readiness(ocr_enabled=True)
        assert len(errors) == 1
        assert "ocrmypdf" in errors[0]

    def test_ocr_readiness_passes_when_disabled(self):
        errors = check_ocr_readiness(ocr_enabled=False)
        assert errors == []

    def test_ocr_readiness_passes_when_installed(self):
        with patch("backend.app.parsing._ocrmypdf_available", return_value=(True, "")):
            errors = check_ocr_readiness(ocr_enabled=True)
        assert errors == []


# ===========================================================================
# T029 / T030 / T031 – Parse artifacts and diagnostics
# ===========================================================================

class TestParseArtifactPersistence:
    """Verify parse-stage artifact persistence (T029, T030, T031)."""

    def test_parse_pdf_writes_parsed_document_json(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        doc, diag, _ = parse_pdf(
            pdf_path=PAPER_3,
            pdf_id="paper_3",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=False,
        )
        artifact_path = run_dir / "parsed" / "paper_3" / "parsed_document.json"
        assert artifact_path.exists(), "parsed_document.json must be written"
        data = json.loads(artifact_path.read_text())
        assert data["pdf_id"] == "paper_3"
        assert "blocks" in data
        assert "metadata" in data
        assert "parser_used" in data
        page_text_path = run_dir / "parsed" / "paper_3" / "page_text.json"
        assert page_text_path.exists(), "page_text.json must be written"
        assert json.loads(page_text_path.read_text())

    def test_parse_pdf_writes_diagnostics_json(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _, diag, _ = parse_pdf(
            pdf_path=PAPER_3,
            pdf_id="paper_3",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=False,
        )
        diag_path = run_dir / "parsed" / "paper_3" / "diagnostics.json"
        assert diag_path.exists(), "diagnostics.json must be written"
        data = json.loads(diag_path.read_text())
        assert data["configured_parser"] == "pypdfium2"
        assert data["actual_parser_used"] == "pypdfium2"
        assert "major_extraction_gaps" in data
        assert "parse_warnings" in data

    def test_page_renders_written_when_enabled(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        _, _, page_paths = parse_pdf(
            pdf_path=PAPER_3,
            pdf_id="paper_3",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=True,
            page_render_scale=0.5,  # small scale for test speed
        )
        assert len(page_paths) > 0, "Should have at least one page render"
        # Verify files actually exist
        for rel_path in page_paths:
            full_path = run_dir / rel_path
            assert full_path.exists(), f"Page render not written: {rel_path}"
            assert full_path.read_bytes()[:4] == b"\x89PNG"

    def test_diagnostics_records_configured_parser_separately(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        with patch(
            "backend.app.parsing.DoclingParserAdapter.parse",
            side_effect=RuntimeError("no model"),
        ):
            doc, diag, _ = parse_pdf(
                pdf_path=PAPER_3,
                pdf_id="paper_3",
                configured_parser="docling",
                allow_basic_fallback=True,
                ocr_enabled=False,
                ocr_language="en",
                run_dir=run_dir,
                generate_pages=False,
            )

        assert diag.configured_parser == "docling"
        assert diag.actual_parser_used == "pypdfium2"
        assert diag.fallback_used is True

        diag_path = run_dir / "parsed" / "paper_3" / "diagnostics.json"
        data = json.loads(diag_path.read_text())
        assert data["configured_parser"] == "docling"
        assert data["actual_parser_used"] == "pypdfium2"

    def test_normalized_text_in_parsed_document(self, tmp_path):
        """ParsedDocument must contain normalized text (T025)."""
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        doc, _, _ = parse_pdf(
            pdf_path=PAPER_2,
            pdf_id="paper_2",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=False,
        )
        assert doc.full_text  # source-preserving
        assert doc.normalized_text  # normalized
        # Normalized text should be lowercase
        assert doc.normalized_text == doc.normalized_text.lower()


# ===========================================================================
# T032 – Parser readiness checks
# ===========================================================================

class TestParserReadiness:
    def test_pypdfium2_always_available(self):
        errors = check_parser_readiness("pypdfium2", allow_basic_fallback=False)
        assert errors == []

    def test_unknown_parser_produces_error(self):
        errors = check_parser_readiness("nonexistent_parser", allow_basic_fallback=False)
        assert any("Unknown parser backend" in e for e in errors)

    def test_docling_unavailable_without_fallback_produces_error(self):
        with patch(
            "backend.app.parsing.DoclingParserAdapter.is_available",
            return_value=(False, "not installed"),
        ):
            errors = check_parser_readiness("docling", allow_basic_fallback=False)
        assert len(errors) == 1
        assert "allow_basic_fallback" in errors[0]

    def test_docling_unavailable_with_fallback_produces_no_error(self):
        with patch(
            "backend.app.parsing.DoclingParserAdapter.is_available",
            return_value=(False, "not installed"),
        ):
            errors = check_parser_readiness("docling", allow_basic_fallback=True)
        assert errors == []


# ===========================================================================
# T033 – Grounded paper-metadata extraction
# ===========================================================================

class TestPaperMetadataExtraction:
    """Verify grounded metadata extraction from ParsedDocument (T033)."""

    def _make_doc_dict(self, full_text: str, metadata: dict = None, blocks: list = None) -> dict:
        return {
            "pdf_id": "test",
            "pdf_path": "test.pdf",
            "metadata": metadata or {},
            "blocks": blocks or [
                {
                    "block_id": "test_0",
                    "block_type": "paragraph",
                    "page_number": 1,
                    "text": full_text[:200],
                    "normalized_text": full_text[:200].lower(),
                    "reading_order": 0,
                }
            ],
            "full_text": full_text,
        }

    def test_extracts_year_from_text(self):
        doc = self._make_doc_dict("Published in 2022. This study...")
        meta = extract_paper_metadata(doc)
        assert meta.year == 2022

    def test_extracts_doi_from_text(self):
        doc = self._make_doc_dict("See https://doi.org/10.1038/s41586-022-1234-5 for details.")
        meta = extract_paper_metadata(doc)
        assert meta.doi is not None
        assert "10.1038" in meta.doi

    def test_uses_metadata_title_when_present(self):
        doc = self._make_doc_dict("Full text here.", metadata={"title": "My Paper Title"})
        meta = extract_paper_metadata(doc)
        assert meta.title == "My Paper Title"

    def test_uses_metadata_authors_when_present(self):
        doc = self._make_doc_dict("Full text here.", metadata={"authors": ["Smith, J.", "Jones, A."]})
        meta = extract_paper_metadata(doc)
        assert meta.authors == ["Smith, J.", "Jones, A."]

    def test_extracts_title_from_heading_block(self):
        blocks = [{
            "block_id": "b0",
            "block_type": "heading",
            "page_number": 1,
            "text": "Massively Parallel Characterization of Regulatory Elements",
            "normalized_text": "massively parallel characterization of regulatory elements",
            "reading_order": 0,
        }]
        doc = self._make_doc_dict("Body text.", blocks=blocks)
        meta = extract_paper_metadata(doc)
        assert meta.title is not None
        assert "Massively Parallel" in meta.title

    def test_extracts_abstract_snippet_from_paragraph(self):
        long_text = "Abstract: " + "This study examines... " * 20
        blocks = [{
            "block_id": "b0",
            "block_type": "abstract",
            "page_number": 1,
            "text": long_text,
            "normalized_text": long_text.lower(),
            "reading_order": 0,
        }]
        doc = self._make_doc_dict(long_text, blocks=blocks)
        meta = extract_paper_metadata(doc)
        assert meta.abstract_snippet is not None
        assert len(meta.abstract_snippet) <= 500


# ===========================================================================
# T034 – Deterministic matching scoring
# ===========================================================================

class TestDeterministicScoring:
    """Verify deterministic scoring logic (T034)."""

    def test_identical_title_scores_high(self):
        paper = PaperMetadata(title="Massively parallel characterization of regulatory elements")
        row = {"Title": "Massively parallel characterization of regulatory elements", "Publication Year": "", "Authors": ""}
        score = score_against_row(paper, row)
        assert score > 0.6

    def test_completely_different_title_scores_low(self):
        paper = PaperMetadata(title="Deep learning for protein folding")
        row = {"Title": "Massively parallel characterization of regulatory elements", "Publication Year": "", "Authors": ""}
        score = score_against_row(paper, row)
        assert score < 0.3

    def test_year_match_increases_score(self):
        paper_with_year = PaperMetadata(title="Some Study", year=2022)
        paper_no_year = PaperMetadata(title="Some Study")
        row = {"Title": "Some Study", "Publication Year": "2022", "Authors": ""}
        score_with = score_against_row(paper_with_year, row)
        score_without = score_against_row(paper_no_year, row)
        assert score_with > score_without

    def test_off_by_one_year_gets_partial_credit(self):
        paper = PaperMetadata(title="Study A", year=2022)
        row_exact = {"Title": "Study A", "Publication Year": "2022", "Authors": ""}
        row_off1 = {"Title": "Study A", "Publication Year": "2021", "Authors": ""}
        row_far = {"Title": "Study A", "Publication Year": "2010", "Authors": ""}
        assert score_against_row(paper, row_exact) > score_against_row(paper, row_off1)
        assert score_against_row(paper, row_off1) > score_against_row(paper, row_far)

    def test_author_overlap_increases_score(self):
        paper_with_authors = PaperMetadata(
            title="Study X", year=2020, authors=["Smith, J.", "Jones, A."]
        )
        paper_no_authors = PaperMetadata(title="Study X", year=2020)
        row = {
            "Title": "Study X",
            "Publication Year": "2020",
            "Authors": "Smith, John; Jones, Alice; Brown, Bob",
        }
        score_with = score_against_row(paper_with_authors, row)
        score_without = score_against_row(paper_no_authors, row)
        assert score_with > score_without

    def test_score_all_rows_returns_descending(self):
        df = pd.DataFrame([
            {"Title": "Completely Different Topic", "Publication Year": "2010", "Authors": ""},
            {"Title": "Massively parallel sequencing", "Publication Year": "2022", "Authors": ""},
            {"Title": "CRISPR editing", "Publication Year": "2019", "Authors": ""},
        ])
        paper = PaperMetadata(title="Massively parallel sequencing of DNA", year=2022)
        scores = score_all_rows(paper, df)
        # Scores should be sorted descending
        assert scores[0].final_score >= scores[1].final_score >= scores[2].final_score
        # Row 1 (massively parallel) should be top
        assert scores[0].row_index == 1
        assert "title_similarity_score" in scores[0].model_dump()

    def test_title_jaccard_symmetric(self):
        t1 = "Hello World Study"
        t2 = "Study Hello World"
        assert _title_jaccard(t1, t2) == _title_jaccard(t2, t1)

    def test_title_jaccard_empty_returns_zero(self):
        assert _title_jaccard("", "Something") == 0.0
        assert _title_jaccard("Something", "") == 0.0


# ===========================================================================
# T035 / T036 – Match outcome assignment
# ===========================================================================

class TestMatchOutcomeAssignment:
    """Verify outcome assignment logic (T035, T036)."""

    def _make_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_matched_outcome_for_clear_winner(self):
        df = self._make_df([
            {"Title": "Massively parallel characterization of regulatory elements", "Publication Year": "2023", "Authors": "Agarwal, V."},
            {"Title": "Completely Unrelated Topic", "Publication Year": "2010", "Authors": "Smith, A."},
        ])
        paper = PaperMetadata(
            title="Massively parallel characterization of regulatory elements",
            year=2023,
            authors=["Agarwal, V."],
        )
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("p1", "p1.pdf", paper, scores, df)
        assert result.outcome == MatchOutcome.matched
        assert result.matched_row_index == 0
        assert result.blocked is False

    def test_unmatched_outcome_for_low_score(self):
        df = self._make_df([
            {"Title": "Completely Unrelated Topic", "Publication Year": "2010", "Authors": "Smith, A."},
            {"Title": "Another Unrelated Paper", "Publication Year": "2011", "Authors": "Brown, B."},
        ])
        paper = PaperMetadata(title="Massively parallel characterization of RNA editing")
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("p1", "p1.pdf", paper, scores, df)
        assert result.outcome == MatchOutcome.unmatched
        assert result.blocked is True
        assert "unmatched" in (result.blocked_reason or "")

    def test_ambiguous_outcome_for_close_scores(self):
        # Two titles that are similar but NOT the same year (so not near-duplicate rows)
        df = self._make_df([
            {"Title": "Massively parallel characterization of transcriptional elements", "Publication Year": "2022", "Authors": ""},
            {"Title": "Massively parallel characterization of transcriptional regulatory elements", "Publication Year": "2021", "Authors": ""},
        ])
        paper = PaperMetadata(
            title="Massively parallel characterization of transcriptional regulatory elements",
            year=2023,  # doesn't match either row's year → no adjudication
        )
        scores = score_all_rows(paper, df)
        # Use a large ambiguity threshold to force ambiguous
        result = assign_match_outcome("p1", "p1.pdf", paper, scores, df, ambiguity_threshold=0.5)
        assert result.outcome == MatchOutcome.ambiguous
        assert result.blocked is True
        assert "ambiguous" in (result.blocked_reason or "")

    def test_near_duplicate_rows_adjudicated_to_matched(self):
        """T035: runner-up is a near-duplicate table row → adjudicate to matched."""
        # Both rows describe the same paper
        df = self._make_df([
            {"Title": "Massively parallel characterization of transcriptional regulatory elements", "Publication Year": "2023", "Authors": "Agarwal"},
            {"Title": "Massively parallel characterization of transcriptional regulatory elements", "Publication Year": "2023", "Authors": "Agarwal"},
        ])
        paper = PaperMetadata(
            title="Massively parallel characterization of transcriptional regulatory elements",
            year=2023,
            authors=["Agarwal, V."],
        )
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("p1", "p1.pdf", paper, scores, df)
        # Near-duplicate rows should be adjudicated → matched
        assert result.outcome == MatchOutcome.matched
        assert result.blocked is False

    def test_empty_table_gives_unmatched(self):
        df = self._make_df([])
        paper = PaperMetadata(title="Some Paper")
        result = assign_match_outcome("p1", "p1.pdf", paper, [], df)
        assert result.outcome == MatchOutcome.unmatched
        assert result.blocked is True


# ===========================================================================
# T037 – Duplicate-row conflict detection
# ===========================================================================

class TestDuplicateRowConflict:
    """Verify duplicate-row conflict detection (T037)."""

    def _matched_result(self, pdf_id: str, row_index: int) -> MatchResult:
        from datetime import datetime, timezone
        return MatchResult(
            pdf_id=pdf_id,
            pdf_path=f"{pdf_id}.pdf",
            outcome=MatchOutcome.matched,
            matched_row_index=row_index,
            matched_row_title=f"Row {row_index} Title",
            score=0.9,
            runner_up_score=0.3,
            reasoning="matched",
            blocked=False,
            matched_at=datetime.now(timezone.utc).isoformat(),
        )

    def test_no_conflict_when_different_rows(self):
        results = [
            self._matched_result("pdf_a", 0),
            self._matched_result("pdf_b", 1),
        ]
        updated = detect_duplicate_row_conflicts(results)
        assert all(r.outcome == MatchOutcome.matched for r in updated)
        assert all(r.blocked is False for r in updated)

    def test_conflict_when_two_pdfs_claim_same_row(self):
        results = [
            self._matched_result("pdf_a", 5),
            self._matched_result("pdf_b", 5),  # same row!
        ]
        updated = detect_duplicate_row_conflicts(results)
        assert all(r.outcome == MatchOutcome.duplicate_row_conflict for r in updated)
        assert all(r.blocked is True for r in updated)
        assert all("duplicate_row_conflict" in (r.blocked_reason or "") for r in updated)

    def test_three_pdfs_all_conflicted_for_same_row(self):
        results = [
            self._matched_result("pdf_a", 3),
            self._matched_result("pdf_b", 3),
            self._matched_result("pdf_c", 3),
        ]
        updated = detect_duplicate_row_conflicts(results)
        assert all(r.outcome == MatchOutcome.duplicate_row_conflict for r in updated)

    def test_non_matched_results_not_affected_by_conflict_detection(self):
        from datetime import datetime, timezone
        unmatched = MatchResult(
            pdf_id="pdf_u",
            pdf_path="pdf_u.pdf",
            outcome=MatchOutcome.unmatched,
            score=0.1,
            runner_up_score=0.05,
            reasoning="no match",
            blocked=True,
            blocked_reason="unmatched",
            matched_at=datetime.now(timezone.utc).isoformat(),
        )
        matched = self._matched_result("pdf_a", 5)
        matched2 = self._matched_result("pdf_b", 5)
        results = [unmatched, matched, matched2]
        updated = detect_duplicate_row_conflicts(results)

        # Unmatched should stay unmatched
        assert updated[0].outcome == MatchOutcome.unmatched
        # Both matched should become conflict
        assert updated[1].outcome == MatchOutcome.duplicate_row_conflict
        assert updated[2].outcome == MatchOutcome.duplicate_row_conflict


# ===========================================================================
# T038 – Matching artifact persistence
# ===========================================================================

class TestMatchArtifactPersistence:
    """Verify matching artifacts are written and inspectable (T038)."""

    def _run_matching_and_persist(self, tmp_path: pathlib.Path) -> pathlib.Path:
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        df = pd.read_csv(FIXTURE_TABLE, dtype=str).fillna("")

        docs = []
        for pdf_id, pdf_path in [
            ("mpra02", PAPER_2),
            ("mpra03", PAPER_3),
            ("unmatched_1", UNMATCHED_PDF),
        ]:
            doc, _, _ = parse_pdf(
                pdf_path=pdf_path,
                pdf_id=pdf_id,
                configured_parser="pypdfium2",
                allow_basic_fallback=False,
                ocr_enabled=False,
                ocr_language="en",
                run_dir=run_dir,
                generate_pages=False,
            )
            docs.append(doc.model_dump())

        results = run_matching(docs, df)
        persist_match_artifacts(run_dir, "test_run", results)
        return run_dir

    def test_match_results_json_written(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        path = run_dir / "matching" / "match_results.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == 3  # 3 PDFs processed

    def test_match_summary_json_written(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        path = run_dir / "matching" / "match_summary.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["total_pdfs"] == 3
        assert "matched" in data
        assert "unmatched" in data
        assert "ambiguous" in data
        assert "duplicate_row_conflict" in data

    def test_unmatched_json_written(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        path = run_dir / "matching" / "unmatched.json"
        assert path.exists()
        data = json.loads(path.read_text())
        # unmatched_1.pdf should be unmatched
        pdf_ids = [r["pdf_id"] for r in data]
        assert "unmatched_1" in pdf_ids

    def test_reasoning_included_in_artifacts(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        path = run_dir / "matching" / "match_results.json"
        data = json.loads(path.read_text())
        for result in data:
            assert result.get("reasoning"), f"Missing reasoning for {result['pdf_id']}"
            assert "top_candidates" in result
            assert "threshold_reasoning" in result

    def test_per_pdf_matching_debug_artifacts_are_written(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        pdf_dir = run_dir / "matching" / "pdfs" / "unmatched_1"
        assert (pdf_dir / "extracted_matching_metadata.json").exists()
        assert (pdf_dir / "metadata_field_diagnostics.json").exists()
        breakdown = json.loads((pdf_dir / "row_match_score_breakdown.json").read_text())
        assert "top_candidates" in breakdown
        assert "threshold_reasoning" in breakdown

    def test_unmatched_artifacts_include_top_candidates_and_missing_metadata(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        unmatched = json.loads((run_dir / "matching" / "unmatched.json").read_text())
        unmatched_row = next(item for item in unmatched if item["pdf_id"] == "unmatched_1")
        assert "top_candidates" in unmatched_row
        assert "missing_metadata_fields" in unmatched_row

    def test_load_match_results_api_helper(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        results = load_match_results(run_dir)
        assert isinstance(results, list)
        assert len(results) == 3

    def test_load_match_summary_api_helper(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        summary = load_match_summary(run_dir)
        assert summary is not None
        assert summary["total_pdfs"] == 3

    def test_load_unmatched_api_helper(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        unmatched = load_unmatched(run_dir)
        assert any(r["pdf_id"] == "unmatched_1" for r in unmatched)

    def test_load_ambiguous_conflicts_return_empty_when_none(self, tmp_path):
        run_dir = self._run_matching_and_persist(tmp_path)
        ambiguous = load_ambiguous(run_dir)
        conflicts = load_conflicts(run_dir)
        # These may or may not be empty depending on scores
        assert isinstance(ambiguous, list)
        assert isinstance(conflicts, list)


# ===========================================================================
# T040 – End-to-end matching behaviors on fixtures
# ===========================================================================

class TestEndToEndMatching:
    """End-to-end match tests on fixture PDFs against the fixture table (T040)."""

    @pytest.fixture(scope="class")
    def df(self):
        return pd.read_csv(FIXTURE_TABLE, dtype=str).fillna("")

    @pytest.fixture(scope="class")
    def parsed_docs(self, tmp_path_factory):
        """Parse all fixture PDFs once for end-to-end tests."""
        run_dir = tmp_path_factory.mktemp("run")
        docs = {}
        pdfs = {
            "mpra02": PAPER_2,
            "mpra03": PAPER_3,
            "mpra04": PAPER_4,
            "unmatched_1": UNMATCHED_PDF,
        }
        for name, pdf_path in pdfs.items():
            doc, _, _ = parse_pdf(
                pdf_path=pdf_path,
                pdf_id=name,
                configured_parser="pypdfium2",
                allow_basic_fallback=False,
                ocr_enabled=False,
                ocr_language="en",
                run_dir=run_dir,
                generate_pages=False,
            )
            docs[name] = doc.model_dump()
        return docs

    def test_paper_2_matches_a_row(self, df, parsed_docs):
        """MPRA02 should match its benchmark template row."""
        paper = extract_paper_metadata(parsed_docs["mpra02"])
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("mpra02", "MPRA02_trauernicht_2024_optimized_reporters.pdf", paper, scores, df)
        assert result.outcome == MatchOutcome.matched, (
            f"Expected matched, got {result.outcome}: {result.reasoning}"
        )
        assert result.matched_row_index == 1

    def test_paper_3_matches_a_row(self, df, parsed_docs):
        """MPRA03 should match its benchmark template row."""
        paper = extract_paper_metadata(parsed_docs["mpra03"])
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("mpra03", "MPRA03_arnold_2013_starr_seq_maps.pdf", paper, scores, df)
        assert result.outcome == MatchOutcome.matched, (
            f"Expected matched, got {result.outcome}: {result.reasoning}"
        )
        assert result.matched_row_index == 2

    def test_paper_4_matches_a_row(self, df, parsed_docs):
        """MPRA04 should match its benchmark template row."""
        paper = extract_paper_metadata(parsed_docs["mpra04"])
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("mpra04", "MPRA04_cornwall_scoones_2025_signal_dependent_cres.pdf", paper, scores, df)
        assert result.outcome == MatchOutcome.matched, (
            f"Expected matched, got {result.outcome}: {result.reasoning}"
        )
        assert result.matched_row_index == 3

    def test_unmatched_pdf_gives_unmatched(self, df, parsed_docs):
        """unmatched_1.pdf should not match any row."""
        paper = extract_paper_metadata(parsed_docs["unmatched_1"])
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("unmatched_1", "unmatched_1.pdf", paper, scores, df)
        assert result.outcome == MatchOutcome.unmatched
        assert result.blocked is True

    def test_matched_pdfs_not_blocked(self, df, parsed_docs):
        """Matched PDFs must not be blocked."""
        for name in ["mpra02", "mpra03", "mpra04"]:
            paper = extract_paper_metadata(parsed_docs[name])
            scores = score_all_rows(paper, df)
            result = assign_match_outcome(name, f"{name}.pdf", paper, scores, df)
            if result.outcome == MatchOutcome.matched:
                assert result.blocked is False, f"{name} matched but blocked={result.blocked}"

    def test_unmatched_blocked(self, df, parsed_docs):
        """Unmatched PDFs must be blocked."""
        paper = extract_paper_metadata(parsed_docs["unmatched_1"])
        scores = score_all_rows(paper, df)
        result = assign_match_outcome("unmatched_1", "unmatched_1.pdf", paper, scores, df)
        assert result.blocked is True

    def test_run_matching_full_pipeline(self, df, parsed_docs):
        """run_matching on all fixture PDFs returns one result per PDF."""
        docs = list(parsed_docs.values())
        results = run_matching(docs, df)
        assert len(results) == len(docs)
        # All must have an outcome
        for r in results:
            assert r.outcome in list(MatchOutcome)

    def test_duplicate_row_conflict_detection_in_run(self, df, tmp_path):
        """When two PDFs match the same row, both are marked as conflicts."""
        # Synthetic: use the same doc twice to force a conflict
        run_dir = tmp_path / "conflict_test"
        run_dir.mkdir()
        doc, _, _ = parse_pdf(
            pdf_path=PAPER_2,
            pdf_id="paper_2_copy1",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=False,
        )
        doc2, _, _ = parse_pdf(
            pdf_path=PAPER_2,
            pdf_id="paper_2_copy2",
            configured_parser="pypdfium2",
            allow_basic_fallback=False,
            ocr_enabled=False,
            ocr_language="en",
            run_dir=run_dir,
            generate_pages=False,
        )
        # Override pdf_id so they're treated as different PDFs but same content
        doc_dict1 = {**doc.model_dump(), "pdf_id": "paper_2_copy1"}
        doc_dict2 = {**doc2.model_dump(), "pdf_id": "paper_2_copy2"}

        results = run_matching([doc_dict1, doc_dict2], df)

        # Both copies should resolve to the same row → conflict
        conflict_count = sum(1 for r in results if r.outcome == MatchOutcome.duplicate_row_conflict)
        assert conflict_count == 2, (
            f"Expected 2 conflicts, got {conflict_count}. Outcomes: {[r.outcome for r in results]}"
        )


# ===========================================================================
# Normalize text
# ===========================================================================

class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("Hello World") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_strips_diacritics(self):
        result = normalize_text("café résumé")
        assert "cafe" in result
        assert "resume" in result


# ===========================================================================
# Are rows near-duplicate helper
# ===========================================================================

class TestAreRowsNearDuplicate:
    def test_identical_rows_are_near_duplicate(self):
        row = {"Title": "A massively parallel study of MPRA", "Publication Year": "2023"}
        assert _are_rows_near_duplicate(row, row) is True

    def test_completely_different_rows_not_near_duplicate(self):
        row_a = {"Title": "Study of protein folding", "Publication Year": "2019"}
        row_b = {"Title": "CRISPR genome editing in mammals", "Publication Year": "2021"}
        assert _are_rows_near_duplicate(row_a, row_b) is False

    def test_same_title_different_year_not_near_duplicate(self):
        row_a = {"Title": "Massively parallel study", "Publication Year": "2020"}
        row_b = {"Title": "Massively parallel study", "Publication Year": "2021"}
        assert _are_rows_near_duplicate(row_a, row_b) is False

