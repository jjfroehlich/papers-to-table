from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfReader
import pypdfium2 as pdfium

from .artifacts import ArtifactStore
from .ids import make_chunk_id, make_pdf_id, stable_hash
from .models import (
    BlockType,
    FigureRef,
    HighlightBox,
    OCRSettings,
    ParsedBlock,
    ParsedDocument,
    ParsedDocumentMetadata,
    ParsedPage,
    ParserSettings,
)


def _load_fixture_sidecar(pdf_path: Path) -> dict | None:
    sidecar = pdf_path.with_suffix(".fixture.json")
    if sidecar.exists():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    return None


class DoclingParserAdapter:
    name = "docling"

    def __init__(self, parser_settings: ParserSettings, ocr_settings: OCRSettings):
        self.parser_settings = parser_settings
        self.ocr_settings = ocr_settings

    def parse(self, run_id: str, pdf_path: Path, store: ArtifactStore) -> ParsedDocument:
        pdf_id = make_pdf_id(run_id, pdf_path)
        sidecar = _load_fixture_sidecar(pdf_path) if self.parser_settings.sidecar_fixture_overrides else None
        if sidecar:
            return self._parse_sidecar(pdf_id, pdf_path, sidecar, store)
        return self._parse_pdf(pdf_id, pdf_path, store)

    def _parse_sidecar(self, pdf_id: str, pdf_path: Path, sidecar: dict, store: ArtifactStore) -> ParsedDocument:
        pages: list[ParsedPage] = []
        blocks: list[ParsedBlock] = []
        figures: list[FigureRef] = []
        parsed_dir = store.path("parsed", pdf_id)
        parsed_dir.mkdir(parents=True, exist_ok=True)
        for page_data in sidecar.get("pages", []):
            page_number = page_data["page_number"]
            image_path = self._render_placeholder_page(parsed_dir / f"page-{page_number}.png", page_number, page_data.get("text", ""))
            pages.append(ParsedPage(page_number=page_number, width=612, height=792, image_path=str(image_path.relative_to(store.root)), text=page_data.get("text", "")))
            for ordinal, block_data in enumerate(page_data.get("blocks", []), start=1):
                blocks.append(
                    ParsedBlock(
                        block_id=make_chunk_id(pdf_id, page_number, block_data.get("block_type", "paragraph"), ordinal),
                        page=page_number,
                        block_type=block_data.get("block_type", BlockType.PARAGRAPH),
                        text=block_data.get("text", ""),
                        source_text=block_data.get("text", ""),
                        retrieval_text=block_data.get("retrieval_text", block_data.get("text", "")),
                        bbox=HighlightBox(**block_data["bbox"]) if block_data.get("bbox") else None,
                        metadata=block_data.get("metadata", {}),
                    )
                )
            for figure_data in page_data.get("figures", []):
                crop_path = self._render_placeholder_crop(parsed_dir / f"figure-{figure_data['figure_id']}.png", figure_data.get("caption", "Figure"))
                figures.append(
                    FigureRef(
                        figure_id=figure_data["figure_id"],
                        page=page_number,
                        caption=figure_data.get("caption", ""),
                        crop_path=str(crop_path.relative_to(store.root)),
                        full_page_path=str(image_path.relative_to(store.root)),
                        nearby_text=figure_data.get("nearby_text", ""),
                    )
                )
        metadata = ParsedDocumentMetadata.model_validate(sidecar.get("metadata", {}))
        diagnostics = {"fixture_override": True, "requires_ocr": sidecar.get("requires_ocr", False)}
        if sidecar.get("requires_ocr"):
            diagnostics["ocr_attempted"] = True
            diagnostics["ocr_used"] = True
        return ParsedDocument(
            pdf_id=pdf_id,
            pdf_name=pdf_path.name,
            parser_name=self.name,
            parser_path="docling-sidecar",
            ocr_used=bool(sidecar.get("requires_ocr")),
            metadata=metadata,
            pages=pages,
            blocks=blocks,
            figures=figures,
            diagnostics=diagnostics,
        )

    def _parse_pdf(self, pdf_id: str, pdf_path: Path, store: ArtifactStore) -> ParsedDocument:
        reader = PdfReader(str(pdf_path))
        text_pages: list[str] = []
        for page in reader.pages:
            text_pages.append(page.extract_text() or "")
        extracted_text = "\n".join(text_pages).strip()
        ocr_used = False
        diagnostics = {"fixture_override": False, "ocr_attempted": False}
        if len(extracted_text) < self.ocr_settings.min_text_chars and self.ocr_settings.enabled:
            diagnostics["ocr_attempted"] = True
            ocr_output = self._attempt_ocr(pdf_path, store.path("parsed", pdf_id))
            if ocr_output:
                reader = PdfReader(str(ocr_output))
                text_pages = [page.extract_text() or "" for page in reader.pages]
                extracted_text = "\n".join(text_pages).strip()
                ocr_used = True
            else:
                diagnostics["ocr_unavailable"] = True
        parsed_dir = store.path("parsed", pdf_id)
        parsed_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, parsed_dir / pdf_path.name)
        pages: list[ParsedPage] = []
        blocks: list[ParsedBlock] = []
        for index, text in enumerate(text_pages, start=1):
            image_path = self._render_pdfium_page(pdf_path, parsed_dir / f"page-{index}.png", index)
            pages.append(ParsedPage(page_number=index, width=612, height=792, image_path=str(image_path.relative_to(store.root)), text=text))
            paragraph_text = " ".join(text.split())
            blocks.append(
                ParsedBlock(
                    block_id=make_chunk_id(pdf_id, index, "paragraph", 1),
                    page=index,
                    block_type=BlockType.PARAGRAPH,
                    text=paragraph_text,
                    source_text=paragraph_text,
                    retrieval_text=paragraph_text,
                    bbox=HighlightBox(x=40, y=80, width=520, height=110),
                )
            )
        metadata = self._metadata_from_text(pdf_path.name, extracted_text)
        return ParsedDocument(
            pdf_id=pdf_id,
            pdf_name=pdf_path.name,
            parser_name=self.name,
            parser_path="docling-fallback-pypdf",
            ocr_used=ocr_used,
            metadata=metadata,
            pages=pages,
            blocks=blocks,
            figures=[],
            diagnostics=diagnostics,
        )

    def _attempt_ocr(self, pdf_path: Path, target_dir: Path) -> Path | None:
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / f"ocr-{pdf_path.name}"
        command = [self.ocr_settings.command, str(pdf_path), str(output_path), "--skip-text"]
        try:
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return output_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _metadata_from_text(self, pdf_name: str, text: str) -> ParsedDocumentMetadata:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = lines[0] if lines else pdf_name.replace(".pdf", "")
        authors_line = lines[1] if len(lines) > 1 else ""
        year = ""
        for token in lines[:10]:
            for piece in token.split():
                if piece.isdigit() and len(piece) == 4 and piece.startswith(("19", "20")):
                    year = piece
                    break
            if year:
                break
        authors = [segment.strip() for segment in authors_line.split(",") if segment.strip()]
        return ParsedDocumentMetadata(title=title, authors=authors, publication_year=year, identifiers={})


    def _render_pdfium_page(self, pdf_path: Path, output_path: Path, page_number: int) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            document = pdfium.PdfDocument(str(pdf_path))
            page = document[page_number - 1]
            bitmap = page.render(scale=1.0)
            pil_image = bitmap.to_pil()
            pil_image.save(output_path)
            page.close()
            document.close()
            return output_path
        except Exception:  # noqa: BLE001
            return self._render_placeholder_page(output_path, page_number, f'Fallback render for {pdf_path.name}')

    def _render_placeholder_page(self, output_path: Path, page_number: int, text: str) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (612, 792), color="white")
        drawer = ImageDraw.Draw(image)
        drawer.text((40, 40), f"Page {page_number}", fill="black")
        drawer.text((40, 80), (text or "No extracted text")[:600], fill="black")
        image.save(output_path)
        return output_path

    def _render_placeholder_crop(self, output_path: Path, text: str) -> Path:
        image = Image.new("RGB", (320, 220), color="#f2f2f2")
        drawer = ImageDraw.Draw(image)
        drawer.rectangle((10, 10, 310, 210), outline="black")
        drawer.text((20, 20), text[:200], fill="black")
        image.save(output_path)
        return output_path
