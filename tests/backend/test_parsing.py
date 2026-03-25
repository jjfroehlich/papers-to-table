"""
Tests for T032 — parsing: clean parse, OCR fallback gate, normalized output,
stored page artifacts, diagnostics.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.app.parsing import (
    BoundingBox,
    BasicTextParser,
    ExtractedMetadata,
    OCR_CHARS_PER_PAGE_THRESHOLD,
    PDFiumBackend,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
    ParserDiagnostics,
    _annotate_diagnostics,
    _map_docling_label,
    needs_ocr,
    parse_pdf_for_run,
    render_crop_artifact,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_PAPERS = REPO_ROOT / "tests" / "fixtures" / "papers"
SAMPLE_PDF = FIXTURES_PAPERS / "paper_1.pdf"


# ---------------------------------------------------------------------------
# Unit tests for pure helpers
# ---------------------------------------------------------------------------

def test_map_docling_label_known() -> None:
    assert _map_docling_label("title") == "title"
    assert _map_docling_label("paragraph") == "paragraph"
    assert _map_docling_label("caption") == "caption"
    assert _map_docling_label("table") == "table"


def test_map_docling_label_unknown_falls_back_to_paragraph() -> None:
    assert _map_docling_label("something_new") == "paragraph"


def test_annotate_diagnostics_empty_doc() -> None:
    doc = ParsedDocument(
        pdf_id="test",
        source_path="/fake.pdf",
        pages=[ParsedPage(page_no=1, width=595.0, height=842.0)],
        blocks=[],
        diagnostics=ParserDiagnostics(
            pdf_id="test",
            parser_used="docling",
            ocr_used=False,
            page_count=1,
            text_block_count=0,
            figure_count=0,
            table_count=0,
            empty_page_count=0,
        ),
    )
    _annotate_diagnostics(doc)
    assert doc.diagnostics is not None
    assert doc.diagnostics.empty_page_count == 1
    assert any("No text blocks" in gap for gap in doc.diagnostics.major_gaps)


def test_annotate_diagnostics_has_text() -> None:
    block = ParsedBlock(
        block_id="b1",
        block_type="paragraph",
        text="Some content",
        normalized_text="some content",
        page_no=1,
        reading_order=0,
    )
    doc = ParsedDocument(
        pdf_id="test",
        source_path="/fake.pdf",
        pages=[ParsedPage(page_no=1, width=595.0, height=842.0)],
        blocks=[block],
        diagnostics=ParserDiagnostics(
            pdf_id="test",
            parser_used="docling",
            ocr_used=False,
            page_count=1,
            text_block_count=1,
            figure_count=0,
            table_count=0,
            empty_page_count=0,
        ),
    )
    _annotate_diagnostics(doc)
    assert doc.diagnostics.empty_page_count == 0
    assert not doc.diagnostics.major_gaps


# ---------------------------------------------------------------------------
# PDFium backend tests (T027)
# ---------------------------------------------------------------------------

def test_pdfium_backend_page_count() -> None:
    with PDFiumBackend(SAMPLE_PDF) as backend:
        assert backend.page_count >= 1


def test_pdfium_backend_page_size() -> None:
    with PDFiumBackend(SAMPLE_PDF) as backend:
        w, h = backend.get_page_size(0)
        assert w > 0
        assert h > 0


def test_pdfium_render_page_returns_png() -> None:
    with PDFiumBackend(SAMPLE_PDF) as backend:
        png_bytes = backend.render_page(0, scale=1.0)
    assert png_bytes[:4] == b"\x89PNG"


def test_pdfium_text_density_born_digital() -> None:
    """Born-digital fixture PDFs should have text density above the OCR threshold."""
    with PDFiumBackend(SAMPLE_PDF) as backend:
        density = backend.text_density()
    assert density >= OCR_CHARS_PER_PAGE_THRESHOLD


# ---------------------------------------------------------------------------
# OCR fallback gate (T028)
# ---------------------------------------------------------------------------

def test_needs_ocr_born_digital_returns_false() -> None:
    """Born-digital PDFs should not need OCR."""
    assert needs_ocr(SAMPLE_PDF) is False


def test_needs_ocr_low_density_triggers(tmp_path: Path) -> None:
    """When text density is below threshold, needs_ocr should return True."""
    low_density_pdf = tmp_path / "blank.pdf"

    with patch("backend.app.parsing.PDFiumBackend") as MockBackend:
        instance = MagicMock()
        instance.__enter__ = MagicMock(return_value=instance)
        instance.__exit__ = MagicMock(return_value=False)
        instance.text_density.return_value = 5.0
        instance.page_count = 3
        MockBackend.return_value = instance

        low_density_pdf.write_bytes(b"fake")
        result = needs_ocr(low_density_pdf)

    assert result is True


def test_ocr_fallback_unavailable_raises(tmp_path: Path) -> None:
    """When Tesseract is not installed, run_ocr_fallback must raise RuntimeError."""
    from backend.app.parsing import run_ocr_fallback

    with patch("backend.app.parsing._ocr_available", return_value=False):
        with pytest.raises(RuntimeError, match="OCRmyPDF or Tesseract"):
            run_ocr_fallback(SAMPLE_PDF, tmp_path)


# ---------------------------------------------------------------------------
# T026: BasicTextParser (pypdfium2 fallback)
# ---------------------------------------------------------------------------

def test_basic_text_parser_produces_valid_doc() -> None:
    """BasicTextParser must produce a valid ParsedDocument from a born-digital PDF."""
    parser = BasicTextParser()
    doc = parser.parse(SAMPLE_PDF, pdf_id="paper_1")

    assert doc.pdf_id == "paper_1"
    assert doc.source_path == str(SAMPLE_PDF)
    assert len(doc.pages) >= 1
    assert len(doc.blocks) >= 1
    assert doc.full_text
    assert doc.diagnostics is not None
    assert doc.diagnostics.parser_used == "pypdfium2_basic"
    assert doc.diagnostics.page_count >= 1


def test_basic_text_parser_reading_order_sorted() -> None:
    """reading_order_blocks must be sorted by (page_no, reading_order)."""
    parser = BasicTextParser()
    doc = parser.parse(SAMPLE_PDF, pdf_id="paper_1")
    ordered = doc.reading_order_blocks
    for a, b in zip(ordered, ordered[1:]):
        assert (a.page_no, a.reading_order) <= (b.page_no, b.reading_order)


# ---------------------------------------------------------------------------
# T026: DoclingParserAdapter falls back on model unavailability
# ---------------------------------------------------------------------------

def test_docling_adapter_falls_back_when_models_unavailable(tmp_path: Path) -> None:
    """DoclingParserAdapter must fall back to BasicTextParser when HF models are absent."""
    from backend.app.parsing import DoclingParserAdapter
    from huggingface_hub.errors import LocalEntryNotFoundError

    adapter = DoclingParserAdapter()
    with patch.object(adapter, "_parse_with_docling", side_effect=LocalEntryNotFoundError("no models")):
        doc = adapter.parse(SAMPLE_PDF, pdf_id="paper_1")

    assert doc.pdf_id == "paper_1"
    assert doc.diagnostics is not None
    assert doc.diagnostics.parser_used == "pypdfium2_basic"
    assert any("Docling models unavailable" in w for w in doc.diagnostics.warnings)


# ---------------------------------------------------------------------------
# T029: Parse-stage persistence
# ---------------------------------------------------------------------------

def test_parse_pdf_for_run_persists_artifacts(tmp_path: Path) -> None:
    """parse_pdf_for_run must persist normalized JSON, manifest, and diagnostics."""
    parsed_dir = tmp_path / "parsed"
    doc, ocr_used = parse_pdf_for_run(
        pdf_path=SAMPLE_PDF,
        pdf_id="paper_1",
        parsed_dir=parsed_dir,
        render_pages=False,
    )

    assert not ocr_used
    assert (parsed_dir / "paper_1" / "parsed_document.json").exists()
    assert (parsed_dir / "paper_1" / "parse_manifest.json").exists()
    assert (parsed_dir / "paper_1" / "diagnostics.json").exists()
    assert doc.pdf_id == "paper_1"
    assert len(doc.blocks) >= 1


# ---------------------------------------------------------------------------
# T030: Page-render artifacts
# ---------------------------------------------------------------------------

def test_parse_pdf_for_run_renders_pages(tmp_path: Path) -> None:
    """parse_pdf_for_run must create at least one PNG page artifact when render_pages=True."""
    parsed_dir = tmp_path / "parsed"
    parse_pdf_for_run(
        pdf_path=SAMPLE_PDF,
        pdf_id="paper_1",
        parsed_dir=parsed_dir,
        render_pages=True,
        page_render_scale=1.0,
    )
    pages_dir = parsed_dir / "paper_1" / "pages"
    pngs = sorted(pages_dir.glob("*.png"))
    assert len(pngs) >= 1
    for png in pngs:
        assert png.stat().st_size > 0


def test_render_crop_artifact(tmp_path: Path) -> None:
    """render_crop_artifact must write a valid PNG crop file."""
    with PDFiumBackend(SAMPLE_PDF) as backend:
        w, h = backend.get_page_size(0)

    crop_path = tmp_path / "crop.png"
    render_crop_artifact(
        pdf_path=SAMPLE_PDF,
        page_no=0,
        bbox_l=0.0,
        bbox_t=h * 0.5,
        bbox_r=w,
        bbox_b=h,
        output_path=crop_path,
        scale=1.0,
    )
    assert crop_path.exists()
    assert crop_path.read_bytes()[:4] == b"\x89PNG"


# ---------------------------------------------------------------------------
# T031: Parser diagnostics
# ---------------------------------------------------------------------------

def test_parser_diagnostics_populated(tmp_path: Path) -> None:
    """Diagnostics must include parser_used, page_count, and gap annotations."""
    parser = BasicTextParser()
    doc = parser.parse(SAMPLE_PDF, pdf_id="paper_1")
    _annotate_diagnostics(doc)

    diag = doc.diagnostics
    assert diag is not None
    assert diag.page_count >= 1
    assert diag.text_block_count >= 1


def test_parser_diagnostics_ocr_flag(tmp_path: Path) -> None:
    """When OCR is not used, ocr_used must be False and ocr_tool must be None."""
    parser = BasicTextParser()
    doc = parser.parse(SAMPLE_PDF, pdf_id="paper_1")

    assert doc.diagnostics is not None
    assert doc.diagnostics.ocr_used is False
    assert doc.diagnostics.ocr_tool is None

