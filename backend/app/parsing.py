"""
Batch 2 — Parsing baseline.

This module implements:
- T025: ParsedDocument schema / contract
- T026: ParserAdapter interface + DoclingParserAdapter as main parser
- T027: PDFiumBackend low-level abstraction (rendering, crops, page access)
- T028: OCR fallback via OCRmyPDF when text is insufficient
- T029: Parse-stage persistence (parser-native + normalized artifacts)
- T030: Page-render artifacts and crop helpers
- T031: Parser diagnostics per PDF
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ParsedDocument contract (T025)
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    """Bounding box in page coordinates (left, top, right, bottom)."""
    l: float
    t: float
    r: float
    b: float
    page_no: int


class ParsedBlock(BaseModel):
    """One typed block/element from the parsed document."""
    block_id: str
    block_type: str  # paragraph, section_header, title, caption, table, figure, footnote, etc.
    text: str  # source-preserving text
    normalized_text: str  # lowercased / whitespace-normalized for downstream use
    page_no: int
    bbox: BoundingBox | None = None
    reading_order: int = 0
    figure_ref: str | None = None  # for captions: reference to the figure block_id
    table_region: bool = False  # True if this block comes from a table region


class ParsedFigure(BaseModel):
    """A figure or picture element with its caption if available."""
    figure_id: str
    page_no: int
    bbox: BoundingBox | None = None
    caption_text: str | None = None
    caption_block_id: str | None = None


class ParsedTable(BaseModel):
    """A table region in the parsed document."""
    table_id: str
    page_no: int
    bbox: BoundingBox | None = None
    markdown_text: str | None = None  # table rendered as markdown when available


class ParsedPage(BaseModel):
    """Minimal page-level record. Page images/renders are stored as artifacts."""
    page_no: int
    width: float
    height: float


class ExtractedMetadata(BaseModel):
    """Paper-level metadata extracted from the parsed document."""
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None


class ParserDiagnostics(BaseModel):
    """Parser diagnostics for one PDF (T031)."""
    pdf_id: str
    parser_used: str
    ocr_used: bool
    ocr_tool: str | None = None
    page_count: int
    text_block_count: int
    figure_count: int
    table_count: int
    empty_page_count: int
    major_gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    """Normalized parsed-document contract (T025).

    All parser adapters produce this representation. Downstream systems
    (matching, retrieval, extraction, evidence) depend only on this contract,
    not on parser-native types.
    """
    # Identity
    pdf_id: str
    source_path: str

    # Metadata
    metadata: ExtractedMetadata = Field(default_factory=ExtractedMetadata)

    # Content
    pages: list[ParsedPage] = Field(default_factory=list)
    blocks: list[ParsedBlock] = Field(default_factory=list)
    figures: list[ParsedFigure] = Field(default_factory=list)
    tables: list[ParsedTable] = Field(default_factory=list)

    # Derived text views
    full_text: str = ""  # concatenated source-preserving text (for search)
    normalized_full_text: str = ""  # concatenated normalized text

    # Diagnostics
    diagnostics: ParserDiagnostics | None = None

    @property
    def reading_order_blocks(self) -> list[ParsedBlock]:
        """Return blocks sorted by page and reading_order."""
        return sorted(self.blocks, key=lambda b: (b.page_no, b.reading_order))


# ---------------------------------------------------------------------------
# Parser adapter interface (T026)
# ---------------------------------------------------------------------------

class ParserAdapter(ABC):
    """Abstract interface for all PDF parser adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short name of the parser backend."""

    @abstractmethod
    def parse(self, pdf_path: Path, pdf_id: str) -> ParsedDocument:
        """Parse a PDF and return a normalized ParsedDocument."""


# ---------------------------------------------------------------------------
# PDFium low-level backend (T027)
# ---------------------------------------------------------------------------

class PDFiumBackend:
    """
    Low-level PDF abstraction using pypdfium2 / PDFium (T027).

    Responsible for:
    - page rendering to PNG
    - crop extraction from a bounding box
    - quick text density check (used for OCR fallback gating)
    """

    def __init__(self, pdf_path: Path) -> None:
        import pypdfium2 as pdfium  # late import so tests can mock

        self._path = pdf_path
        self._pdfium = pdfium
        self._doc = pdfium.PdfDocument(str(pdf_path))

    def __enter__(self) -> "PDFiumBackend":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._doc.close()
        except Exception:
            pass

    @property
    def page_count(self) -> int:
        return len(self._doc)

    def get_page_size(self, page_no: int) -> tuple[float, float]:
        """Return (width, height) in PDF units for page_no (0-indexed)."""
        page = self._doc.get_page(page_no)
        w, h = page.get_size()
        page.close()
        return float(w), float(h)

    def render_page(self, page_no: int, scale: float = 2.0) -> bytes:
        """Render page_no (0-indexed) to PNG bytes at the given scale."""
        page = self._doc.get_page(page_no)
        bitmap = page.render(scale=scale, rotation=0)
        pil_image = bitmap.to_pil()
        import io
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        page.close()
        return buf.getvalue()

    def render_crop(
        self,
        page_no: int,
        bbox_l: float,
        bbox_t: float,
        bbox_r: float,
        bbox_b: float,
        scale: float = 2.0,
    ) -> bytes:
        """
        Render a cropped region from page_no (0-indexed).

        Bounding box coordinates are in PDF units (origin bottom-left).
        Returns PNG bytes.
        """
        page = self._doc.get_page(page_no)
        _, page_height = page.get_size()

        # PDFium uses bottom-left origin; PIL uses top-left origin
        # Convert to pixel coordinates
        bitmap = page.render(scale=scale, rotation=0)
        pil_image = bitmap.to_pil()
        w_px, h_px = pil_image.size

        # Map from PDF units to pixel space
        pdf_w, pdf_h = page.get_size()
        x0 = int(bbox_l / pdf_w * w_px)
        y0 = int((pdf_h - bbox_t) / pdf_h * h_px)
        x1 = int(bbox_r / pdf_w * w_px)
        y1 = int((pdf_h - bbox_b) / pdf_h * h_px)

        # Clamp
        x0, x1 = max(0, min(x0, w_px)), max(0, min(x1, w_px))
        y0, y1 = max(0, min(y0, h_px)), max(0, min(y1, h_px))
        if x0 >= x1 or y0 >= y1:
            import io
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            page.close()
            return buf.getvalue()

        cropped = pil_image.crop((x0, y0, x1, y1))
        import io
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        page.close()
        return buf.getvalue()

    def text_density(self) -> float:
        """
        Return a rough text-character density ratio across all pages.

        Used as a fast heuristic to decide whether OCR fallback is needed.
        """
        total_chars = 0
        for page in self._doc:
            textpage = page.get_textpage()
            total_chars += len(textpage.get_text_range())
            textpage.close()
            page.close()
        return total_chars / max(self.page_count, 1)


# ---------------------------------------------------------------------------
# OCR fallback gate (T028)
# ---------------------------------------------------------------------------

OCR_CHARS_PER_PAGE_THRESHOLD = 50  # fewer than this triggers OCR


def _ocr_available() -> bool:
    """Return True if OCRmyPDF and Tesseract are both available."""
    try:
        import ocrmypdf  # noqa: F401
        return shutil.which("tesseract") is not None
    except ImportError:
        return False


def needs_ocr(pdf_path: Path) -> bool:
    """
    Return True when the PDF is scanned or has insufficient extractable text.

    Uses pypdfium2 for a fast text-density check before invoking OCR.
    """
    try:
        with PDFiumBackend(pdf_path) as backend:
            density = backend.text_density()
        return density < OCR_CHARS_PER_PAGE_THRESHOLD
    except Exception as exc:
        logger.warning("text-density check failed for %s: %s", pdf_path.name, exc)
        return False


def run_ocr_fallback(pdf_path: Path, output_dir: Path) -> Path:
    """
    Run OCRmyPDF on the source PDF and return the path to the searchable output PDF.

    Raises RuntimeError if OCR is unavailable or fails.
    """
    if not _ocr_available():
        raise RuntimeError(
            "OCR fallback requested but OCRmyPDF or Tesseract is not available. "
            "Install OCRmyPDF and Tesseract to enable OCR support."
        )

    import ocrmypdf

    output_path = output_dir / f"{pdf_path.stem}_ocr.pdf"
    logger.info("Running OCR fallback on %s → %s", pdf_path.name, output_path.name)
    result = ocrmypdf.ocr(
        input_file=str(pdf_path),
        output_file=str(output_path),
        language="eng",
        skip_text=False,
        force_ocr=False,
        progress_bar=False,
        jobs=1,
    )
    if result and int(result) not in (0, 6):  # 0=ok, 6=already-done
        raise RuntimeError(f"OCRmyPDF returned exit code {result} for {pdf_path.name}")

    return output_path


# ---------------------------------------------------------------------------
# BasicTextParser — pypdfium2-based fallback (T026)
# ---------------------------------------------------------------------------

class BasicTextParser(ParserAdapter):
    """
    Fallback parser that uses pypdfium2 text extraction.

    This parser does not require any model downloads and produces a valid
    ParsedDocument when Docling models are unavailable. It provides coarser
    layout analysis but is always available.
    """

    @property
    def name(self) -> str:
        return "pypdfium2_basic"

    def parse(self, pdf_path: Path, pdf_id: str) -> ParsedDocument:
        with PDFiumBackend(pdf_path) as backend:
            pages: list[ParsedPage] = []
            blocks: list[ParsedBlock] = []
            reading_order = 0

            for page_no_idx in range(backend.page_count):
                w, h = backend.get_page_size(page_no_idx)
                page_no = page_no_idx + 1  # 1-indexed
                pages.append(ParsedPage(page_no=page_no, width=w, height=h))

                page = backend._doc.get_page(page_no_idx)
                textpage = page.get_textpage()
                text = textpage.get_text_range()
                textpage.close()
                page.close()

                if not text.strip():
                    continue

                # Split into paragraphs by double-newline
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                for para in paragraphs:
                    blocks.append(
                        ParsedBlock(
                            block_id=f"p{page_no}_{reading_order}",
                            block_type="paragraph",
                            text=para,
                            normalized_text=para.lower().strip(),
                            page_no=page_no,
                            reading_order=reading_order,
                        )
                    )
                    reading_order += 1

        full_text = "\n".join(b.text for b in blocks)
        normalized_full_text = "\n".join(b.normalized_text for b in blocks)

        diag = ParserDiagnostics(
            pdf_id=pdf_id,
            parser_used=self.name,
            ocr_used=False,
            page_count=len(pages),
            text_block_count=len(blocks),
            figure_count=0,
            table_count=0,
            empty_page_count=0,
            warnings=["BasicTextParser used: Docling models unavailable; layout/figure/table analysis skipped"],
        )

        return ParsedDocument(
            pdf_id=pdf_id,
            source_path=str(pdf_path),
            pages=pages,
            blocks=blocks,
            full_text=full_text,
            normalized_full_text=normalized_full_text,
            diagnostics=diag,
        )


# ---------------------------------------------------------------------------
# Docling parser adapter (T026)
# ---------------------------------------------------------------------------

class DoclingParserAdapter(ParserAdapter):
    """
    Main parser adapter backed by Docling (T026).

    Docling provides layout-aware scientific PDF parsing including
    figure detection, table extraction, and reading-order analysis.

    Falls back to BasicTextParser when Docling's models are not available
    (e.g., first run before model download or air-gapped environments).
    """

    @property
    def name(self) -> str:
        return "docling"

    def parse(self, pdf_path: Path, pdf_id: str) -> ParsedDocument:
        try:
            return self._parse_with_docling(pdf_path, pdf_id)
        except Exception as exc:
            # Docling model download or initialization failure — fall back gracefully
            if "LocalEntryNotFoundError" in type(exc).__name__ or "OfflineModeIsEnabled" in type(exc).__name__:
                logger.warning(
                    "Docling models not available (%s); falling back to BasicTextParser for %s",
                    exc,
                    pdf_path.name,
                )
                doc = BasicTextParser().parse(pdf_path, pdf_id)
                if doc.diagnostics:
                    doc.diagnostics.warnings.insert(
                        0, f"Docling models unavailable: {exc}"
                    )
                return doc
            raise

    def _parse_with_docling(self, pdf_path: Path, pdf_id: str) -> ParsedDocument:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False  # We manage OCR ourselves

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

        result = converter.convert(str(pdf_path))
        docling_doc = result.document

        return _normalize_docling_document(docling_doc, pdf_id, str(pdf_path))


def _normalize_docling_document(docling_doc: Any, pdf_id: str, source_path: str) -> ParsedDocument:
    """Convert a Docling DoclingDocument into our normalized ParsedDocument."""
    from docling_core.types.doc.document import (
        DocItemLabel,
        PictureItem,
        TableItem,
        TextItem,
        SectionHeaderItem,
        TitleItem,
    )

    blocks: list[ParsedBlock] = []
    figures: list[ParsedFigure] = []
    tables: list[ParsedTable] = []
    pages: list[ParsedPage] = []
    metadata = ExtractedMetadata()

    # Pages
    for page_no, page_item in docling_doc.pages.items():
        pages.append(
            ParsedPage(
                page_no=int(page_no),
                width=float(page_item.size.width),
                height=float(page_item.size.height),
            )
        )
    pages.sort(key=lambda p: p.page_no)

    # Walk the document in reading order
    reading_order = 0
    first_title: str | None = None
    all_author_candidates: list[str] = []

    for item, _level in docling_doc.iterate_items():
        if isinstance(item, (TextItem, SectionHeaderItem, TitleItem)):
            text = item.text or ""
            prov = item.prov[0] if item.prov else None
            bbox: BoundingBox | None = None
            page_no = prov.page_no if prov else 1
            if prov and prov.bbox:
                b = prov.bbox
                bbox = BoundingBox(l=b.l, t=b.t, r=b.r, b=b.b, page_no=page_no)

            label = str(item.label)
            block_type = _map_docling_label(label)
            normalized = text.lower().strip()

            # Metadata: capture title from first title-like block
            if block_type in ("title", "section_header") and first_title is None and len(text) > 5:
                first_title = text.strip()

            blocks.append(
                ParsedBlock(
                    block_id=item.self_ref,
                    block_type=block_type,
                    text=text,
                    normalized_text=normalized,
                    page_no=page_no,
                    bbox=bbox,
                    reading_order=reading_order,
                )
            )
            reading_order += 1

        elif isinstance(item, PictureItem):
            prov = item.prov[0] if item.prov else None
            bbox = None
            page_no = prov.page_no if prov else 1
            if prov and prov.bbox:
                b = prov.bbox
                bbox = BoundingBox(l=b.l, t=b.t, r=b.r, b=b.b, page_no=page_no)

            # Look for caption in children or near-neighbours (best-effort)
            caption_text: str | None = None
            caption_block_id: str | None = None
            if hasattr(item, "captions") and item.captions:
                cap = item.captions[0]
                if hasattr(cap, "text"):
                    caption_text = cap.text
                    caption_block_id = getattr(cap, "self_ref", None)

            figures.append(
                ParsedFigure(
                    figure_id=item.self_ref,
                    page_no=page_no,
                    bbox=bbox,
                    caption_text=caption_text,
                    caption_block_id=caption_block_id,
                )
            )

        elif isinstance(item, TableItem):
            prov = item.prov[0] if item.prov else None
            bbox = None
            page_no = prov.page_no if prov else 1
            if prov and prov.bbox:
                b = prov.bbox
                bbox = BoundingBox(l=b.l, t=b.t, r=b.r, b=b.b, page_no=page_no)

            md_text: str | None = None
            try:
                md_text = item.export_to_markdown()
            except Exception:
                pass

            # Also add table text as a block for retrieval
            if md_text:
                blocks.append(
                    ParsedBlock(
                        block_id=f"{item.self_ref}_text",
                        block_type="table",
                        text=md_text,
                        normalized_text=md_text.lower().strip(),
                        page_no=page_no,
                        bbox=bbox,
                        reading_order=reading_order,
                        table_region=True,
                    )
                )
                reading_order += 1

            tables.append(
                ParsedTable(
                    table_id=item.self_ref,
                    page_no=page_no,
                    bbox=bbox,
                    markdown_text=md_text,
                )
            )

    # Derive metadata from extracted title and document origin
    if first_title:
        metadata.title = first_title

    # Try to populate metadata from docling's document origin if available
    if docling_doc.origin:
        origin = docling_doc.origin
        if hasattr(origin, "filename"):
            pass  # filename is not title

    full_text = "\n".join(b.text for b in blocks if b.text)
    normalized_full_text = "\n".join(b.normalized_text for b in blocks if b.normalized_text)

    diag = ParserDiagnostics(
        pdf_id=pdf_id,
        parser_used="docling",
        ocr_used=False,
        page_count=len(pages),
        text_block_count=len([b for b in blocks if b.block_type not in ("table", "figure")]),
        figure_count=len(figures),
        table_count=len(tables),
        empty_page_count=0,
        major_gaps=[],
        warnings=[],
    )

    return ParsedDocument(
        pdf_id=pdf_id,
        source_path=source_path,
        metadata=metadata,
        pages=pages,
        blocks=blocks,
        figures=figures,
        tables=tables,
        full_text=full_text,
        normalized_full_text=normalized_full_text,
        diagnostics=diag,
    )


def _map_docling_label(label: str) -> str:
    """Map a Docling DocItemLabel string to our internal block_type."""
    mapping = {
        "title": "title",
        "section_header": "section_header",
        "paragraph": "paragraph",
        "text": "paragraph",
        "caption": "caption",
        "footnote": "footnote",
        "page_header": "page_header",
        "page_footer": "page_footer",
        "list_item": "list_item",
        "code": "code",
        "formula": "formula",
        "reference": "reference",
        "table": "table",
        "picture": "figure",
    }
    return mapping.get(label, "paragraph")


# ---------------------------------------------------------------------------
# Parse + persist orchestration (T029, T030, T031)
# ---------------------------------------------------------------------------

_DEFAULT_ADAPTER = DoclingParserAdapter()


def get_parser_adapter() -> ParserAdapter:
    """Return the registered main parser adapter."""
    return _DEFAULT_ADAPTER


def parse_pdf_for_run(
    pdf_path: Path,
    pdf_id: str,
    parsed_dir: Path,
    render_pages: bool = True,
    page_render_scale: float = 2.0,
) -> tuple[ParsedDocument, bool]:
    """
    Parse a single PDF for a run, handling OCR fallback when needed.

    Steps:
    1. Quick text-density check via PDFium
    2. Run OCR fallback if needed and OCR is available
    3. Parse with Docling adapter
    4. Persist parser-native JSON and normalized contract
    5. Render page images if requested (T030)
    6. Persist parser diagnostics (T031)

    Returns (ParsedDocument, ocr_was_used).
    """
    pdf_dir = parsed_dir / pdf_id
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # 1. OCR gate
    ocr_used = False
    parse_source = pdf_path
    ocr_warnings: list[str] = []

    ocr_needed = needs_ocr(pdf_path)
    if ocr_needed:
        if _ocr_available():
            try:
                ocr_out_dir = parsed_dir / pdf_id / "ocr"
                ocr_out_dir.mkdir(parents=True, exist_ok=True)
                parse_source = run_ocr_fallback(pdf_path, ocr_out_dir)
                ocr_used = True
                logger.info("OCR complete for %s", pdf_id)
            except Exception as exc:
                msg = f"OCR fallback failed: {exc}; continuing with original PDF"
                logger.warning(msg)
                ocr_warnings.append(msg)
        else:
            msg = "OCR needed but not available (install OCRmyPDF + Tesseract); parsing original PDF"
            logger.warning(msg)
            ocr_warnings.append(msg)

    # 2. Parse with Docling
    adapter = get_parser_adapter()
    doc = adapter.parse(parse_source, pdf_id)

    # Propagate OCR status into diagnostics
    if doc.diagnostics:
        doc.diagnostics.ocr_used = ocr_used
        doc.diagnostics.ocr_tool = "ocrmypdf" if ocr_used else None
        doc.diagnostics.warnings.extend(ocr_warnings)
        _annotate_diagnostics(doc)

    # 3. Persist parser-native output (T029)
    _persist_native_output(parsed_dir, pdf_id, parse_source, adapter.name)

    # 4. Persist normalized ParsedDocument (T029)
    normalized_path = pdf_dir / "parsed_document.json"
    import json
    with normalized_path.open("w", encoding="utf-8") as fh:
        json.dump(doc.model_dump(mode="json"), fh, ensure_ascii=False, indent=2)

    # 5. Render page artifacts (T030)
    if render_pages:
        _render_page_artifacts(parse_source, pdf_id, pdf_dir, scale=page_render_scale)

    # 6. Persist diagnostics (T031)
    if doc.diagnostics:
        diag_path = pdf_dir / "diagnostics.json"
        with diag_path.open("w", encoding="utf-8") as fh:
            json.dump(doc.diagnostics.model_dump(mode="json"), fh, ensure_ascii=False, indent=2)

    return doc, ocr_used


def _annotate_diagnostics(doc: ParsedDocument) -> None:
    """Populate empty_page_count and major_gaps in diagnostics from the document."""
    if not doc.diagnostics:
        return
    diag = doc.diagnostics

    # Count pages with no text blocks
    pages_with_text: set[int] = {b.page_no for b in doc.blocks if b.text.strip()}
    all_page_nos: set[int] = {p.page_no for p in doc.pages}
    diag.empty_page_count = len(all_page_nos - pages_with_text)

    if diag.empty_page_count > 0:
        diag.major_gaps.append(
            f"{diag.empty_page_count} page(s) with no extracted text blocks"
        )
    if diag.text_block_count == 0:
        diag.major_gaps.append("No text blocks extracted — PDF may be image-only")


def _persist_native_output(parsed_dir: Path, pdf_id: str, parse_source: Path, parser_name: str) -> None:
    """
    Store the path reference to the parser's source file.

    Docling does not emit a separate native JSON by default in this pipeline;
    we record the source path and parser name in a manifest instead.
    """
    import json
    manifest = {
        "parser": parser_name,
        "source_file": str(parse_source),
    }
    manifest_path = parsed_dir / pdf_id / "parse_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)


def _render_page_artifacts(
    pdf_path: Path,
    pdf_id: str,
    output_dir: Path,
    scale: float = 2.0,
) -> None:
    """
    Render each page of the PDF to a PNG file in output_dir/pages/ (T030).
    """
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    try:
        with PDFiumBackend(pdf_path) as backend:
            for page_no in range(backend.page_count):
                page_png = pages_dir / f"page_{page_no + 1:04d}.png"
                if page_png.exists():
                    continue  # idempotent
                png_bytes = backend.render_page(page_no, scale=scale)
                page_png.write_bytes(png_bytes)
        logger.debug("Rendered %d pages for %s", backend.page_count, pdf_id)
    except Exception as exc:
        logger.warning("Page rendering failed for %s: %s", pdf_id, exc)


def render_crop_artifact(
    pdf_path: Path,
    page_no: int,
    bbox_l: float,
    bbox_t: float,
    bbox_r: float,
    bbox_b: float,
    output_path: Path,
    scale: float = 2.0,
) -> Path:
    """
    Render a bounding-box crop from the given page and write it to output_path.

    page_no is 0-indexed; bounding box coordinates are in PDF units (bottom-left origin).
    Returns the output_path.
    """
    with PDFiumBackend(pdf_path) as backend:
        png_bytes = backend.render_crop(page_no, bbox_l, bbox_t, bbox_r, bbox_b, scale=scale)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_bytes)
    return output_path
