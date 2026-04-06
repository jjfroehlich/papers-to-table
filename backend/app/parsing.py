"""Batch 2: PDF parsing, normalized ParsedDocument contract, parser adapters, and artifact persistence.

T025 – ParsedDocument schema/contract
T026 – Parser adapter interface + Docling registration
T026a – Explicit parser-selection and fallback-policy handling
T027 – PDFiumBackend (pypdfium2)
T028 – OCR fallback (ocrmypdf)
T029 – Parse-stage artifact persistence
T030 – Page-render and crop-helper artifacts
T031 – Parser diagnostics per PDF
"""

from __future__ import annotations

import abc
import io
import pathlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from .artifacts import write_json

# ---------------------------------------------------------------------------
# Shared regex constants (avoids duplication across metadata extraction points)
# ---------------------------------------------------------------------------

#: Pattern for extracting publication years in the range 1990–2039
_YEAR_PATTERN = re.compile(r"\b(19[9]\d|20[0-3]\d)\b")

#: Pattern for extracting DOIs (permissive, handles common variants)
_DOI_PATTERN = re.compile(r"(10\.\d{4,}[\w./\-;()+<>:]+)")


def _normalize_linebreaks(text: str) -> str:
    """Normalize Windows (CRLF) and old Mac (CR) line endings to Unix (LF)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _unwrap_docling_item(item_entry: object) -> object:
    """Normalize Docling iterate_items() payload shape across supported versions."""
    return item_entry[0] if isinstance(item_entry, tuple) else item_entry


# ---------------------------------------------------------------------------
# ParsedDocument contract (T025)
# ---------------------------------------------------------------------------

class DocumentMetadata(BaseModel):
    """Extracted paper-level metadata."""
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None


class TextBlock(BaseModel):
    """A single typed text block extracted from the PDF."""
    block_id: str
    block_type: str  # "paragraph", "heading", "section_heading", "caption",
                     # "table_region", "list_item", "abstract", "reference", "unknown"
    page_number: int   # 1-based
    text: str          # source-preserving text
    normalized_text: str  # lowercased, whitespace-normalized
    reading_order: int
    bbox: Optional[list[float]] = None   # [x0, y0, x1, y1] in PDF points
    provenance: str = "unknown"          # "docling", "pypdfium2", "ocr"


class PageInfo(BaseModel):
    """Per-page metadata."""
    page_number: int   # 1-based
    width: float
    height: float
    text_accessible: bool
    block_count: int


class FigureCaptionPair(BaseModel):
    """A figure/image with its associated caption when available."""
    figure_id: str
    page_number: int
    caption_block_id: Optional[str] = None
    caption_text: Optional[str] = None
    bbox: Optional[list[float]] = None  # figure region in PDF points
    crop_path: Optional[str] = None
    full_page_path: Optional[str] = None


class ParsedDocument(BaseModel):
    """Normalized parsed-document contract for one PDF (T025).

    Preserves:
    - document identity (pdf_id, pdf_path)
    - extracted metadata (title, authors, year, doi, abstract)
    - per-page info with text-accessibility flags
    - typed blocks with source-preserving + normalized text
    - reading order
    - figure/caption relationships
    - table regions as blocks (block_type="table_region")
    - provenance links (which parser produced each block)
    - optional geometry/bounding boxes
    - parser truth (configured_parser, parser_used, fallback_used, ocr_used)
    - diagnostics (parse_warnings)
    """
    pdf_id: str
    pdf_path: str
    metadata: DocumentMetadata
    pages: list[PageInfo]
    blocks: list[TextBlock]
    figures: list[FigureCaptionPair]
    full_text: str       # source-preserving, all blocks joined with newlines
    normalized_text: str  # normalized full text for search/matching
    configured_parser: str   # from config.parser.backend
    parser_used: str         # actual parser that ran ("docling", "pypdfium2", "pypdfium2_ocr")
    fallback_used: bool      # True if a lower-quality fallback path was activated
    fallback_reason: Optional[str] = None
    ocr_used: bool           # True if OCR was applied
    ocr_reason: Optional[str] = None
    parse_warnings: list[str]
    parsed_at: str


class ParserDiagnostics(BaseModel):
    """Per-PDF diagnostics written to the artifact bundle (T031)."""
    pdf_id: str
    pdf_path: str
    configured_parser: str
    actual_parser_used: str
    fallback_used: bool
    fallback_reason: Optional[str]
    ocr_used: bool
    ocr_reason: Optional[str]
    page_count: int
    text_char_count: int
    total_blocks: int
    major_extraction_gaps: list[str]
    parse_warnings: list[str]
    parsed_at: str


# ---------------------------------------------------------------------------
# Parser adapter interface (T026)
# ---------------------------------------------------------------------------

class ParserAdapter(abc.ABC):
    """Abstract base class for parser adapters."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Adapter name (e.g. 'docling', 'pypdfium2')."""
        ...

    @abc.abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Check whether this adapter can be used.

        Returns:
            (available, reason_if_not_available)
        """
        ...

    @abc.abstractmethod
    def parse(self, pdf_path: str, pdf_id: str) -> ParsedDocument:
        """Parse the PDF and return a normalized ParsedDocument."""
        ...


# ---------------------------------------------------------------------------
# Low-level PDF layer: PDFiumBackend (T027)
# ---------------------------------------------------------------------------

class PDFiumBackend:
    """Low-level PDF operations via pypdfium2 / PDFium.

    Provides:
    - page rendering to PNG bytes
    - text extraction per page
    - geometry/bounding-box support
    - crop extraction for evidence regions
    """

    def __init__(self, pdf_path: str) -> None:
        import pypdfium2 as pdfium
        self._pdfium = pdfium
        self._doc = pdfium.PdfDocument(pdf_path)
        self._pdf_path = pdf_path

    def __len__(self) -> int:
        return len(self._doc)

    def page_size(self, page_index: int) -> tuple[float, float]:
        """Return (width, height) in PDF points for the given 0-based page index."""
        page = self._doc[page_index]
        return page.get_width(), page.get_height()

    def get_page_text(self, page_index: int) -> str:
        """Extract text from a page (0-based index)."""
        page = self._doc[page_index]
        textpage = page.get_textpage()
        return textpage.get_text_range()

    def get_full_text(self) -> str:
        """Extract all text from the document."""
        parts = []
        for i in range(len(self._doc)):
            parts.append(self.get_page_text(i))
        return "\n".join(parts)

    def get_page_text_accessible(self, page_index: int) -> bool:
        """Return True if the page has usable extractable text (>= 20 chars)."""
        text = self.get_page_text(page_index)
        return len(text.strip()) >= 20

    def render_page(
        self,
        page_index: int,
        scale: float = 1.5,
        grayscale: bool = False,
    ) -> bytes:
        """Render a page to PNG bytes.

        Args:
            page_index: 0-based page index.
            scale: Rendering scale factor (1.0 = 72 DPI, 1.5 = 108 DPI).
            grayscale: Render in grayscale to reduce file size.

        Returns:
            PNG image bytes.
        """
        page = self._doc[page_index]
        bitmap = page.render(
            scale=scale,
            rotation=0,
            may_draw_forms=False,
        )
        pil_image = bitmap.to_pil()
        if grayscale:
            pil_image = pil_image.convert("L")
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def render_crop(
        self,
        page_index: int,
        bbox: list[float],
        scale: float = 2.0,
        padding: float = 5.0,
    ) -> bytes:
        """Render a cropped region of a page to PNG bytes.

        Args:
            page_index: 0-based page index.
            bbox: [x0, y0, x1, y1] in PDF points.
            scale: Rendering scale.
            padding: Extra padding in PDF points.

        Returns:
            PNG image bytes.
        """
        page = self._doc[page_index]
        width = page.get_width()
        height = page.get_height()

        x0_raw, x1_raw = sorted((bbox[0], bbox[2]))
        y0_raw, y1_raw = sorted((bbox[1], bbox[3]))

        x0 = max(0.0, x0_raw - padding)
        y0 = max(0.0, y0_raw - padding)
        x1 = min(width, x1_raw + padding)
        y1 = min(height, y1_raw + padding)

        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"Invalid crop bbox: {bbox}")

        bitmap = page.render(
            scale=scale,
            rotation=0,
            may_draw_forms=False,
        )
        pil_image = bitmap.to_pil()
        crop_box = (
            int(round(x0 * scale)),
            int(round(y0 * scale)),
            int(round(x1 * scale)),
            int(round(y1 * scale)),
        )
        pil_image = pil_image.crop(crop_box)
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def close(self) -> None:
        self._doc.close()


# ---------------------------------------------------------------------------
# OCR availability check (T028)
# ---------------------------------------------------------------------------

def _ocrmypdf_available() -> tuple[bool, str]:
    """Check whether ocrmypdf is importable."""
    try:
        import ocrmypdf  # noqa: F401
        return True, ""
    except ImportError as e:
        return False, str(e)


def apply_ocr_to_pdf(pdf_path: str, output_path: str, language: str = "en") -> None:
    """Apply OCR to a PDF using ocrmypdf, writing result to output_path.

    Raises:
        ImportError: if ocrmypdf is not installed
        RuntimeError: if OCR fails
    """
    import ocrmypdf

    result = ocrmypdf.ocr(
        pdf_path,
        output_path,
        language=language,
        skip_text=True,  # skip pages that already have text
        progress_bar=False,
        quiet=True,
    )
    if result and result != 0:
        raise RuntimeError(f"ocrmypdf returned exit code {result}")


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """Normalize text for search/matching: lowercase, strip diacritics, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# BasicTextParserAdapter: pypdfium2-based fallback (T026a)
# ---------------------------------------------------------------------------

class BasicTextParserAdapter(ParserAdapter):
    """Parser adapter using pypdfium2 text extraction only.

    Used as an explicit lower-quality fallback when Docling is unavailable
    and the config's allow_basic_fallback flag is set.
    """

    @property
    def name(self) -> str:
        return "pypdfium2"

    def is_available(self) -> tuple[bool, str]:
        try:
            import pypdfium2  # noqa: F401
            return True, ""
        except ImportError as e:
            return False, str(e)

    def parse(self, pdf_path: str, pdf_id: str) -> ParsedDocument:
        """Parse using pypdfium2 text extraction."""
        backend = PDFiumBackend(pdf_path)
        try:
            return _parse_with_pdfium(backend, pdf_path, pdf_id, configured_parser="pypdfium2")
        finally:
            backend.close()


def _parse_with_pdfium(
    backend: PDFiumBackend,
    pdf_path: str,
    pdf_id: str,
    configured_parser: str = "pypdfium2",
) -> ParsedDocument:
    """Build a ParsedDocument from pypdfium2 text extraction."""
    now = datetime.now(timezone.utc).isoformat()
    n_pages = len(backend)
    warnings: list[str] = []

    pages: list[PageInfo] = []
    blocks: list[TextBlock] = []
    reading_order = 0

    for page_idx in range(n_pages):
        page_number = page_idx + 1
        w, h = backend.page_size(page_idx)
        raw_text = backend.get_page_text(page_idx)
        text = _normalize_linebreaks(raw_text)
        accessible = len(text.strip()) >= 20

        pages.append(PageInfo(
            page_number=page_number,
            width=w,
            height=h,
            text_accessible=accessible,
            block_count=1 if accessible else 0,
        ))

        if accessible:
            # Split into rough paragraphs by double-newline
            paragraphs = re.split(r"\n{2,}", text.strip())
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                block_type = _infer_block_type_from_text(para)
                blocks.append(TextBlock(
                    block_id=f"{pdf_id}_p{page_number}_{reading_order}",
                    block_type=block_type,
                    page_number=page_number,
                    text=para,
                    normalized_text=normalize_text(para),
                    reading_order=reading_order,
                    bbox=None,
                    provenance="pypdfium2",
                ))
                reading_order += 1
        else:
            warnings.append(f"Page {page_number} has no extractable text")

    # Update block counts per page
    page_block_counts: dict[int, int] = {}
    for b in blocks:
        page_block_counts[b.page_number] = page_block_counts.get(b.page_number, 0) + 1
    for p in pages:
        p.block_count = page_block_counts.get(p.page_number, 0)

    full_text = "\n\n".join(b.text for b in blocks)
    normalized_text = normalize_text(full_text)

    # Extract metadata from raw page texts (before paragraph merging) for better title extraction
    all_page_texts = []
    for page_idx in range(n_pages):
        raw = backend.get_page_text(page_idx)
        all_page_texts.append(_normalize_linebreaks(raw))
    first_pages_text = "\n".join(all_page_texts[:3])

    metadata = _extract_metadata_from_text(blocks, first_pages_text, full_text)

    return ParsedDocument(
        pdf_id=pdf_id,
        pdf_path=pdf_path,
        metadata=metadata,
        pages=pages,
        blocks=blocks,
        figures=[],  # pypdfium2 doesn't extract figures/captions
        full_text=full_text,
        normalized_text=normalized_text,
        configured_parser=configured_parser,
        parser_used="pypdfium2",
        fallback_used=(configured_parser != "pypdfium2"),
        fallback_reason=None,
        ocr_used=False,
        ocr_reason=None,
        parse_warnings=warnings,
        parsed_at=now,
    )


def _infer_block_type_from_text(text: str) -> str:
    """Heuristically guess block type from text content."""
    stripped = text.strip()
    # Short capitalized lines are likely headings
    if len(stripped) < 80 and stripped == stripped.upper() and stripped.isalpha():
        return "heading"
    # Section headings: short lines followed by a number or short word
    if len(stripped) < 120 and re.match(r"^(\d+\.?\s+)?[A-Z][a-zA-Z\s]+$", stripped):
        return "section_heading"
    # Abstract prefix
    if stripped.lower().startswith("abstract"):
        return "abstract"
    # References section
    if stripped.lower().startswith("references") and len(stripped) < 30:
        return "heading"
    # Caption-like
    if re.match(r"^(fig(ure)?\.?\s*\d|table\s*\d)", stripped, re.IGNORECASE):
        return "caption"
    return "paragraph"


def _extract_metadata_from_text(
    blocks: list[TextBlock],
    first_pages_text: str,
    full_text: str,
) -> DocumentMetadata:
    """Extract title, authors, year, doi from text blocks using heuristics."""
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None

    # DOI extraction
    doi_match = _DOI_PATTERN.search(full_text)
    if doi_match:
        doi = doi_match.group(1).rstrip(".")

    # Year: prefer 4-digit year in the expected publication range
    year_matches = _YEAR_PATTERN.findall(full_text)
    if year_matches:
        from collections import Counter
        year_counts = Counter(year_matches)
        year = int(year_counts.most_common(1)[0][0])

    # Title: line-based extraction from raw first-pages text works better than
    # block-level extraction because pypdfium2 blocks may merge title + abstract
    title = _extract_title_from_lines(first_pages_text)
    if not title:
        # Fall back to blocks-based extraction
        for block in blocks[:10]:
            if block.page_number > 2:
                break
            text = block.text.strip()
            if len(text) > 15 and block.block_type in ("heading", "section_heading", "paragraph"):
                if not re.search(r"vol\.|issue\.|doi:|nature|science|journal", text, re.IGNORECASE):
                    title = re.sub(r"\s+", " ", text[:200])
                    break

    # Authors: extract from first-page style lines immediately after title.
    authors = _extract_authors_from_lines(first_pages_text, title=title)

    # Abstract: look for abstract block
    for block in blocks:
        if block.block_type == "abstract" or "abstract" in block.text[:50].lower():
            abstract = block.text
            break

    return DocumentMetadata(title=title, authors=authors, year=year, doi=doi, abstract=abstract)


def _extract_title_from_lines(text: str) -> Optional[str]:
    """Extract the paper title using line-by-line heuristics on raw page text.

    Strategy:
    1. Skip common journal/article-type header lines
    2. Collect consecutive lines that form the title (wrap detection)
    3. Stop at known section headers or author-list lines
    """
    # Common non-title lines to skip before finding the title (match at start)
    skip_start = re.compile(
        r"^(article|letter|research\s+(article|paper)|report|review|news|"
        r"comment|correspondence|perspective|editorial|short\s+report|"
        r"vol\.|issue\s*\d|©|copyright|\d{4}\s*\||\(\d{4}\)|"
        r"nature\s|science\s|cell\s|published|received|accepted|open\s+access|"
        r"graphical\s+abstract|highlights?$|authors?\s*$|correspondence$|"
        r"in\s+brief$|\d+\s*of\s*\d+$|\d{1,3}\s*\|)",
        re.IGNORECASE,
    )
    # Lines containing these patterns anywhere → skip (journal reference headers, DOI lines)
    skip_anywhere = re.compile(
        r"(doi:\s*https?://|et\s+al\.\s+\w+\s+20\d{2}|\bpreprint\b|"
        r"\d+\s+of\s+\d+$)",
        re.IGNORECASE,
    )
    # Stop collecting when we hit these section markers
    stop_at = re.compile(
        r"^(abstract|introduction|keywords?|background|summary|graphical\s+abstract|"
        r"highlights?|authors?\s*$|correspondence|in\s+brief|d\s+\w)",
        re.IGNORECASE,
    )
    # Author line: a capitalized word followed immediately by affiliation digit(s)
    # e.g., "Drew T. Bergman1,2,9, Thouis R. Jones1"
    # e.g., "Miguel Martinez-Ara1,2, Federico Comoglio1†"
    author_line = re.compile(r"\b[A-Z][a-zA-Z\-]+\d+[,†‡*]?")

    lines = text.split("\n")
    title_lines: list[str] = []
    found_start = False

    for line in lines[:80]:
        stripped = line.strip()
        if not stripped:
            if title_lines:
                # blank line after we've started → end of title block
                break
            continue

        # Stop at section markers
        if stop_at.match(stripped):
            break

        if not found_start:
            if skip_start.match(stripped) or skip_anywhere.search(stripped):
                continue
            if len(stripped) < 10:
                continue
            found_start = True

        if found_start:
            if skip_start.match(stripped) or stop_at.match(stripped):
                break
            if skip_anywhere.search(stripped):
                break
            if title_lines and len(stripped) < 10:
                break
            # Author-line detection: if we already have title content and this line
            # looks like an author list, stop here (don't include author names in title)
            if title_lines and author_line.search(stripped):
                break
            # Remove trailing affiliation superscripts if any
            cleaned = re.sub(r"\s*\d+(,\d+)*[†‡*]?\s*$", "", stripped).strip()
            if cleaned:
                title_lines.append(cleaned)
            combined = " ".join(title_lines)
            if len(combined) > 250:
                break

    if title_lines:
        combined = " ".join(title_lines)
        combined = re.sub(r"\s+", " ", combined).strip()
        return combined[:300] if combined else None
    return None


def _extract_authors_from_lines(text: str, title: Optional[str] = None) -> Optional[list[str]]:
    """Extract author names from front-matter lines.

    The goal is to recover common author-list layouts found directly under titles.
    """
    if not text.strip():
        return None

    stop_at = re.compile(
        r"^(abstract|introduction|keywords?|background|summary|correspondence|"
        r"received|accepted|published|copyright|doi\s*:|"
        r"supplementary|materials?\s+and\s+methods?)",
        re.IGNORECASE,
    )
    disqualify_anywhere = re.compile(
        r"(doi\s*:|@|http[s]?://|www\.|university|department|institute|"
        r"hospital|school|faculty|address|affiliation)",
        re.IGNORECASE,
    )
    name_pattern = re.compile(
        r"\b"
        r"(?:[A-Z][a-zA-Z'`-]+|[A-Z]\.)"
        r"(?:\s+(?:[A-Z][a-zA-Z'`-]+|[A-Z]\.)){1,4}"
        r"\b"
    )

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return None

    start_idx = 0
    if title:
        title_norm = re.sub(r"\s+", " ", title).strip().lower()
        for i, line in enumerate(lines[:40]):
            if title_norm and title_norm in line.lower():
                start_idx = i + 1
                break

    authors: list[str] = []
    seen: set[str] = set()

    for line in lines[start_idx:start_idx + 12]:
        if stop_at.match(line):
            break
        if len(line) > 220:
            continue
        if disqualify_anywhere.search(line):
            continue

        # Strip common affiliation markers and note symbols.
        cleaned = line
        cleaned = re.sub(r"[\u00B9\u00B2\u00B3\u2070-\u2079]", "", cleaned)
        cleaned = re.sub(r"(?<=\w)[\d†‡*]+", "", cleaned)
        cleaned = re.sub(r"\([^)]*\)", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:")
        if not cleaned:
            continue

        matches = name_pattern.findall(cleaned)
        if len(matches) < 2:
            # Most author lines include at least two names.
            continue

        for name in matches:
            normalized = re.sub(r"\s+", " ", name).strip(" ,;:")
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            authors.append(normalized)

        # Once we have a plausible author line, stop at the first strong hit.
        if len(authors) >= 2:
            break

    return authors or None


# ---------------------------------------------------------------------------
# DoclingParserAdapter (T026)
# ---------------------------------------------------------------------------

class DoclingParserAdapter(ParserAdapter):
    """Parser adapter wrapping Docling for rich structured PDF parsing."""

    @property
    def name(self) -> str:
        return "docling"

    def is_available(self) -> tuple[bool, str]:
        """Check whether docling can be imported."""
        try:
            import docling  # noqa: F401
            return True, ""
        except ImportError as e:
            return False, f"docling not importable: {e}"

    def parse(self, pdf_path: str, pdf_id: str) -> ParsedDocument:
        """Parse using Docling.

        Raises:
            RuntimeError: if Docling is not importable or model loading fails.
        """
        available, reason = self.is_available()
        if not available:
            raise RuntimeError(f"Docling not available: {reason}")

        try:
            return self._run_docling(pdf_path, pdf_id)
        except Exception as e:
            raise RuntimeError(f"Docling parse failed for {pdf_path}: {e}") from e

    def _run_docling(self, pdf_path: str, pdf_id: str) -> ParsedDocument:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        opts = PdfPipelineOptions()
        opts.do_ocr = False  # we handle OCR separately
        opts.do_table_structure = True
        opts.do_picture_classification = False
        opts.generate_page_images = False
        opts.generate_picture_images = False

        converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
            },
        )

        result = converter.convert(pdf_path)
        doc = result.document

        now = datetime.now(timezone.utc).isoformat()
        warnings: list[str] = []

        # --- Pages ---
        pages: list[PageInfo] = []
        page_text_accessible: dict[int, bool] = {}

        if doc.pages:
            for page_no, page_obj in doc.pages.items():
                pn = int(page_no)
                # Get page size from pdfium for accuracy
                try:
                    import pypdfium2 as pdfium
                    _tmp_doc = pdfium.PdfDocument(pdf_path)
                    _page = _tmp_doc[pn - 1]
                    w, h = _page.get_width(), _page.get_height()
                    _tmp_doc.close()
                except Exception:
                    w, h = 595.0, 842.0  # A4 fallback

                pages.append(PageInfo(
                    page_number=pn,
                    width=w,
                    height=h,
                    text_accessible=True,  # updated below
                    block_count=0,  # updated below
                ))
                page_text_accessible[pn] = False

        # --- Blocks ---
        blocks: list[TextBlock] = []
        figures: list[FigureCaptionPair] = []
        reading_order = 0
        figure_counter = 0

        for item_entry in doc.iterate_items():
            item = _unwrap_docling_item(item_entry)

            from docling_core.types.doc import (
                DocItemLabel,
                SectionHeaderItem,
                TextItem,
                TableItem,
                PictureItem,
                ListItem,
            )

            if not hasattr(item, "text") and not isinstance(
                item, (TableItem, PictureItem)
            ):
                continue

            # Determine page number
            prov = getattr(item, "prov", None)
            if prov and len(prov) > 0:
                page_number = int(prov[0].page_no)
                bbox_raw = prov[0].bbox
                if bbox_raw is not None:
                    # Docling bbox: l, t, r, b in points (origin top-left)
                    bbox = [
                        float(bbox_raw.l),
                        float(bbox_raw.t),
                        float(bbox_raw.r),
                        float(bbox_raw.b),
                    ]
                else:
                    bbox = None
            else:
                page_number = 1
                bbox = None

            page_text_accessible[page_number] = True

            if isinstance(item, TableItem):
                # Export table as text
                try:
                    table_text = item.export_to_markdown()
                except Exception:
                    table_text = getattr(item, "text", "") or ""
                if table_text.strip():
                    blocks.append(TextBlock(
                        block_id=f"{pdf_id}_p{page_number}_{reading_order}",
                        block_type="table_region",
                        page_number=page_number,
                        text=table_text,
                        normalized_text=normalize_text(table_text),
                        reading_order=reading_order,
                        bbox=bbox,
                        provenance="docling",
                    ))
                    reading_order += 1
                continue

            if isinstance(item, PictureItem):
                figure_counter += 1
                figures.append(FigureCaptionPair(
                    figure_id=f"{pdf_id}_fig{figure_counter}",
                    page_number=page_number,
                    caption_block_id=None,
                    caption_text=None,
                    bbox=bbox,
                ))
                continue

            text = getattr(item, "text", "") or ""
            if not text.strip():
                continue

            # Determine block type
            label = getattr(item, "label", None)
            if label is not None:
                block_type = _docling_label_to_block_type(str(label))
            elif isinstance(item, SectionHeaderItem):
                block_type = "section_heading"
            elif isinstance(item, ListItem):
                block_type = "list_item"
            else:
                block_type = "paragraph"

            # Associate caption with preceding figure
            if block_type == "caption" and figures:
                last_fig = figures[-1]
                if last_fig.caption_block_id is None:
                    last_fig.caption_block_id = f"{pdf_id}_p{page_number}_{reading_order}"
                    last_fig.caption_text = text

            blocks.append(TextBlock(
                block_id=f"{pdf_id}_p{page_number}_{reading_order}",
                block_type=block_type,
                page_number=page_number,
                text=text,
                normalized_text=normalize_text(text),
                reading_order=reading_order,
                bbox=bbox,
                provenance="docling",
            ))
            reading_order += 1

        # Update page text accessibility and block counts
        page_block_counts: dict[int, int] = {}
        for b in blocks:
            page_block_counts[b.page_number] = page_block_counts.get(b.page_number, 0) + 1
        for p in pages:
            p.text_accessible = page_text_accessible.get(p.page_number, False)
            p.block_count = page_block_counts.get(p.page_number, 0)

        if not pages:
            # Fallback: add pages from pypdfium2
            import pypdfium2 as pdfium
            _tmp = pdfium.PdfDocument(pdf_path)
            for i in range(len(_tmp)):
                pg = _tmp[i]
                pages.append(PageInfo(
                    page_number=i + 1,
                    width=pg.get_width(),
                    height=pg.get_height(),
                    text_accessible=bool(page_text_accessible.get(i + 1, False)),
                    block_count=page_block_counts.get(i + 1, 0),
                ))
            _tmp.close()

        full_text = "\n\n".join(b.text for b in blocks)
        normalized_text = normalize_text(full_text)

        # Extract metadata
        meta = _extract_docling_metadata(doc)

        # Check for low extraction
        if not full_text.strip():
            warnings.append("Docling produced no text; consider enabling OCR fallback")

        return ParsedDocument(
            pdf_id=pdf_id,
            pdf_path=pdf_path,
            metadata=meta,
            pages=pages,
            blocks=blocks,
            figures=figures,
            full_text=full_text,
            normalized_text=normalized_text,
            configured_parser="docling",
            parser_used="docling",
            fallback_used=False,
            fallback_reason=None,
            ocr_used=False,
            ocr_reason=None,
            parse_warnings=warnings,
            parsed_at=now,
        )


def _docling_label_to_block_type(label: str) -> str:
    """Map a Docling DocItemLabel string to our block_type vocabulary."""
    label_lower = label.lower()
    mapping = {
        "section_header": "section_heading",
        "title": "heading",
        "abstract": "abstract",
        "caption": "caption",
        "list_item": "list_item",
        "table": "table_region",
        "picture": "figure",
        "reference": "reference",
        "footnote": "footnote",
        "page_header": "page_header",
        "page_footer": "page_footer",
    }
    for key, val in mapping.items():
        if key in label_lower:
            return val
    return "paragraph"


def _extract_docling_metadata(doc: object) -> DocumentMetadata:
    """Extract structured metadata from a Docling document object."""
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None

    # Try metadata from docling's document model
    meta = getattr(doc, "metadata", None)
    if meta is not None:
        title = getattr(meta, "title", None) or title
        _authors = getattr(meta, "authors", None)
        if _authors:
            authors = [
                getattr(a, "name", None) or str(a)
                for a in _authors
                if a
            ]
        _year = getattr(meta, "year", None)
        if _year:
            try:
                year = int(str(_year)[:4])
            except (ValueError, TypeError):
                pass
        doi = getattr(meta, "doi", None) or doi

    # Fall back to text-based extraction from the full-text export
    try:
        full_text = doc.export_to_text()  # type: ignore[attr-defined]
    except Exception:
        full_text = ""

    if not title and full_text:
        # First substantial line often contains the title
        for line in full_text.split("\n"):
            line = line.strip()
            if len(line) > 20 and not re.search(
                r"vol\.|doi:|journal|article|©|copyright", line, re.IGNORECASE
            ):
                title = re.sub(r"\s+", " ", line)
                break

    if not year and full_text:
        year_matches = _YEAR_PATTERN.findall(full_text)
        if year_matches:
            from collections import Counter
            year = int(Counter(year_matches).most_common(1)[0][0])

    if not doi and full_text:
        doi_match = _DOI_PATTERN.search(full_text)
        if doi_match:
            doi = doi_match.group(1).rstrip(".")

    if not abstract and full_text:
        abs_match = re.search(
            r"abstract[:\s]+(.{100,1500}?)(\n{2,}|introduction|keywords)",
            full_text, re.IGNORECASE | re.DOTALL,
        )
        if abs_match:
            abstract = re.sub(r"\s+", " ", abs_match.group(1)).strip()

    if not authors and full_text:
        authors = _extract_authors_from_lines(full_text, title=title)

    return DocumentMetadata(title=title, authors=authors, year=year, doi=doi, abstract=abstract)


# ---------------------------------------------------------------------------
# Parser registry (T026)
# ---------------------------------------------------------------------------

_REGISTERED_ADAPTERS: dict[str, ParserAdapter] = {
    "docling": DoclingParserAdapter(),
    "pypdfium2": BasicTextParserAdapter(),
}


def get_adapter(name: str) -> ParserAdapter:
    """Get a registered parser adapter by name.

    Raises:
        KeyError: if the adapter name is not registered.
    """
    if name not in _REGISTERED_ADAPTERS:
        raise KeyError(
            f"Unknown parser backend '{name}'. "
            f"Registered adapters: {sorted(_REGISTERED_ADAPTERS)}"
        )
    return _REGISTERED_ADAPTERS[name]


# ---------------------------------------------------------------------------
# OCR fallback orchestration (T028)
# ---------------------------------------------------------------------------

def _needs_ocr(doc: ParsedDocument, threshold: int = 100) -> tuple[bool, str]:
    """Decide whether OCR is needed.

    A document needs OCR if its total extractable text is below the threshold
    (threshold chars), indicating a scanned or text-inaccessible PDF.
    """
    total_chars = len(doc.full_text.strip())
    if total_chars < threshold:
        return True, f"extracted text too short ({total_chars} chars < {threshold} threshold)"
    return False, ""


def _apply_ocr_fallback(
    pdf_path: str,
    pdf_id: str,
    original_doc: ParsedDocument,
    language: str,
    tmp_dir: pathlib.Path,
) -> ParsedDocument:
    """Apply OCR to the PDF and re-parse with pypdfium2.

    Writes OCR'd PDF to tmp_dir / {pdf_id}_ocr.pdf, then re-parses.
    """
    ocr_pdf_path = str(tmp_dir / f"{pdf_id}_ocr.pdf")
    apply_ocr_to_pdf(pdf_path, ocr_pdf_path, language=language)

    backend = PDFiumBackend(ocr_pdf_path)
    try:
        ocr_doc = _parse_with_pdfium(backend, pdf_path, pdf_id, configured_parser=original_doc.configured_parser)
    finally:
        backend.close()

    # Stamp with OCR provenance
    ocr_blocks = []
    for b in ocr_doc.blocks:
        ocr_blocks.append(b.model_copy(update={"provenance": "ocr"}))

    return ocr_doc.model_copy(update={
        "blocks": ocr_blocks,
        "parser_used": "pypdfium2_ocr",
        "ocr_used": True,
        "ocr_reason": original_doc.ocr_reason or "text extraction insufficient",
        "fallback_used": original_doc.configured_parser != "pypdfium2",
        "fallback_reason": original_doc.fallback_reason,
        "parse_warnings": original_doc.parse_warnings + [
            f"OCR applied via ocrmypdf (language={language})"
        ],
    })


# ---------------------------------------------------------------------------
# Artifact persistence helpers (T029, T030, T031)
# ---------------------------------------------------------------------------

def get_parsed_dir(run_dir: pathlib.Path, pdf_id: str) -> pathlib.Path:
    """Return the artifact directory for a single parsed PDF."""
    return run_dir / "parsed" / pdf_id


def persist_parse_artifacts(
    run_dir: pathlib.Path,
    doc: ParsedDocument,
    diagnostics: ParserDiagnostics,
) -> None:
    """Store normalized ParsedDocument and diagnostics under run_dir/parsed/{pdf_id}/ (T029, T031)."""
    artifact_dir = get_parsed_dir(run_dir, doc.pdf_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    write_json(artifact_dir / "parsed_document.json", doc.model_dump())
    write_json(artifact_dir / "diagnostics.json", diagnostics.model_dump())


def generate_page_artifacts(
    run_dir: pathlib.Path,
    pdf_path: str,
    pdf_id: str,
    scale: float = 1.0,
) -> list[str]:
    """Render each page of the PDF to PNG and write to run_dir/parsed/{pdf_id}/pages/.

    Returns list of relative artifact paths (relative to run_dir).

    T030: page-render artifacts needed for evidence review.
    """
    pages_dir = get_parsed_dir(run_dir, pdf_id) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    backend = PDFiumBackend(pdf_path)
    artifact_paths: list[str] = []
    try:
        for i in range(len(backend)):
            png_bytes = backend.render_page(i, scale=scale)
            out_path = pages_dir / f"page_{i + 1:04d}.png"
            out_path.write_bytes(png_bytes)
            artifact_paths.append(str(out_path.relative_to(run_dir)))
    finally:
        backend.close()

    return artifact_paths


def generate_figure_artifacts(
    run_dir: pathlib.Path,
    pdf_path: str,
    doc: ParsedDocument,
    page_artifact_paths: Optional[list[str]] = None,
    scale: float = 2.0,
) -> ParsedDocument:
    """Render detected figures to crop artifacts and attach artifact paths."""
    if not doc.figures:
        return doc

    figures_dir = get_parsed_dir(run_dir, doc.pdf_id) / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    page_path_by_number: dict[int, str] = {}
    for rel_path in page_artifact_paths or []:
        match = re.search(r"page_(\d+)\.png$", rel_path)
        if match:
            page_path_by_number[int(match.group(1))] = rel_path.replace("\\", "/")

    backend = PDFiumBackend(pdf_path)
    updated_figures: list[FigureCaptionPair] = []
    try:
        for figure in doc.figures:
            crop_path = figure.crop_path
            full_page_path = figure.full_page_path or page_path_by_number.get(figure.page_number)

            if figure.bbox is not None and 1 <= figure.page_number <= len(backend):
                try:
                    png_bytes = backend.render_crop(
                        figure.page_number - 1,
                        figure.bbox,
                        scale=scale,
                    )
                    out_path = figures_dir / f"{figure.figure_id}.png"
                    out_path.write_bytes(png_bytes)
                    crop_path = str(out_path.relative_to(run_dir)).replace("\\", "/")
                except Exception:
                    pass

            updated_figures.append(
                figure.model_copy(
                    update={
                        "crop_path": crop_path,
                        "full_page_path": full_page_path,
                    }
                )
            )
    finally:
        backend.close()

    return doc.model_copy(update={"figures": updated_figures})


def generate_crop_artifact(
    run_dir: pathlib.Path,
    pdf_path: str,
    pdf_id: str,
    page_number: int,
    bbox: list[float],
    crop_id: str,
    scale: float = 2.0,
) -> str:
    """Render a crop region to PNG.

    Returns the relative artifact path.

    T030: crop helpers for text evidence and figure evidence.
    """
    crops_dir = get_parsed_dir(run_dir, pdf_id) / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    backend = PDFiumBackend(pdf_path)
    try:
        png_bytes = backend.render_crop(page_number - 1, bbox, scale=scale)
    finally:
        backend.close()

    out_path = crops_dir / f"{crop_id}.png"
    out_path.write_bytes(png_bytes)
    return str(out_path.relative_to(run_dir))


def build_diagnostics(
    doc: ParsedDocument,
    page_artifact_paths: list[str],
) -> ParserDiagnostics:
    """Build ParserDiagnostics from a ParsedDocument (T031)."""
    gaps: list[str] = []
    if not doc.metadata.title:
        gaps.append("title_not_extracted")
    if not doc.metadata.authors:
        gaps.append("authors_not_extracted")
    if not doc.metadata.year:
        gaps.append("year_not_extracted")
    if not doc.full_text.strip():
        gaps.append("no_text_extracted")
    inaccessible = sum(1 for p in doc.pages if not p.text_accessible)
    if inaccessible > 0:
        gaps.append(f"{inaccessible}_pages_text_inaccessible")

    return ParserDiagnostics(
        pdf_id=doc.pdf_id,
        pdf_path=doc.pdf_path,
        configured_parser=doc.configured_parser,
        actual_parser_used=doc.parser_used,
        fallback_used=doc.fallback_used,
        fallback_reason=doc.fallback_reason,
        ocr_used=doc.ocr_used,
        ocr_reason=doc.ocr_reason,
        page_count=len(doc.pages),
        text_char_count=len(doc.full_text),
        total_blocks=len(doc.blocks),
        major_extraction_gaps=gaps,
        parse_warnings=doc.parse_warnings,
        parsed_at=doc.parsed_at,
    )


# ---------------------------------------------------------------------------
# Main parse entry point (T026a: parser-selection + fallback-policy)
# ---------------------------------------------------------------------------

def parse_pdf(
    pdf_path: str,
    pdf_id: str,
    configured_parser: str,
    allow_basic_fallback: bool,
    ocr_enabled: bool,
    ocr_language: str,
    run_dir: pathlib.Path,
    generate_pages: bool = True,
    page_render_scale: float = 1.0,
) -> tuple[ParsedDocument, ParserDiagnostics, list[str]]:
    """Parse a single PDF.

    Implements T026a: explicit parser-selection and fallback-policy handling.

    - configured_parser is recorded separately from actual parser_used.
    - If the configured parser fails and allow_basic_fallback=False, raises RuntimeError.
    - If allow_basic_fallback=True, uses BasicTextParser and records the fallback.
    - OCR is applied only when text is insufficient AND ocr_enabled=True.
    - Page render artifacts are generated if generate_pages=True.

    Returns:
        (parsed_doc, diagnostics, page_artifact_paths)

    Raises:
        RuntimeError: if the configured parser is unavailable and fallback is disabled.
    """
    adapter = get_adapter(configured_parser)

    doc: Optional[ParsedDocument] = None
    fallback_reason: Optional[str] = None

    available, unavailable_reason = adapter.is_available()
    if not available:
        if not allow_basic_fallback:
            raise RuntimeError(
                f"Configured parser '{configured_parser}' is not available: {unavailable_reason}. "
                f"Set parser.allow_basic_fallback=true in config to use basic text extraction as fallback."
            )
        fallback_reason = f"{configured_parser} unavailable: {unavailable_reason}"
    else:
        try:
            doc = adapter.parse(pdf_path, pdf_id)
        except Exception as e:
            if not allow_basic_fallback:
                raise RuntimeError(
                    f"Parser '{configured_parser}' failed for {pdf_path}: {e}. "
                    f"Set parser.allow_basic_fallback=true to use basic text extraction as fallback."
                ) from e
            fallback_reason = f"{configured_parser} parse error: {e}"

    # Use basic fallback if needed
    if doc is None:
        basic_adapter = get_adapter("pypdfium2")
        doc = basic_adapter.parse(pdf_path, pdf_id)
        doc = doc.model_copy(update={
            "configured_parser": configured_parser,
            "fallback_used": True,
            "fallback_reason": fallback_reason,
        })

    # OCR fallback (T028): apply only if text is insufficient and OCR is enabled
    needs_ocr, ocr_reason = _needs_ocr(doc)
    if needs_ocr:
        if ocr_enabled:
            ocr_available, ocr_unavail_reason = _ocrmypdf_available()
            if not ocr_available:
                doc.parse_warnings.append(
                    f"OCR needed ({ocr_reason}) but ocrmypdf not available: {ocr_unavail_reason}"
                )
            else:
                tmp_dir = run_dir / "parsed" / pdf_id
                tmp_dir.mkdir(parents=True, exist_ok=True)
                doc = doc.model_copy(update={"ocr_reason": ocr_reason})
                doc = _apply_ocr_fallback(pdf_path, pdf_id, doc, ocr_language, tmp_dir)
        else:
            doc.parse_warnings.append(
                f"Low text extraction ({ocr_reason}); OCR disabled. "
                f"Enable parser.ocr_enabled=true to apply OCR fallback."
            )

    # Persist artifacts (T029)
    page_artifact_paths: list[str] = []
    if generate_pages:
        page_artifact_paths = generate_page_artifacts(
            run_dir, pdf_path, pdf_id, scale=page_render_scale
        )

    doc = generate_figure_artifacts(
        run_dir,
        pdf_path,
        doc,
        page_artifact_paths=page_artifact_paths,
    )

    diagnostics = build_diagnostics(doc, page_artifact_paths)
    persist_parse_artifacts(run_dir, doc, diagnostics)

    return doc, diagnostics, page_artifact_paths


# ---------------------------------------------------------------------------
# Dependency readiness checks (used by config.check_readiness)
# ---------------------------------------------------------------------------

def check_parser_readiness(configured_parser: str, allow_basic_fallback: bool) -> list[str]:
    """Return a list of error strings if parser dependencies are not met."""
    errors: list[str] = []

    # pypdfium2 is always required (used by BasicTextParser and rendering)
    basic_adapter = get_adapter("pypdfium2")
    ok, reason = basic_adapter.is_available()
    if not ok:
        errors.append(f"pypdfium2 not available: {reason}")

    # Configured parser
    if configured_parser not in _REGISTERED_ADAPTERS:
        errors.append(
            f"Unknown parser backend '{configured_parser}'. "
            f"Supported: {sorted(_REGISTERED_ADAPTERS)}"
        )
    elif configured_parser != "pypdfium2":
        adapter = get_adapter(configured_parser)
        ok, reason = adapter.is_available()
        if not ok:
            if not allow_basic_fallback:
                errors.append(
                    f"Configured parser '{configured_parser}' is not available: {reason}. "
                    f"Either install it or set parser.allow_basic_fallback=true."
                )
            # If fallback is allowed, this is a warning not an error (recorded in diagnostics)

    return errors


def check_ocr_readiness(ocr_enabled: bool) -> list[str]:
    """Return error strings if OCR dependencies are not met."""
    if not ocr_enabled:
        return []
    ok, reason = _ocrmypdf_available()
    if not ok:
        return [f"parser.ocr_enabled=true but ocrmypdf not available: {reason}"]
    return []
