from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from pypdf import PdfReader

from ..artifacts import ArtifactStore
from ..ids import stable_pdf_id
from ..models import ParsedBlock, ParsedDocument, ParsedMetadata, ParsedPage, RunConfig


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class PDFiumDocument:
    source_path: Path

    def page_count(self) -> int:
        return len(pdfium.PdfDocument(str(self.source_path)))

    def render_page(self, page_number: int, output_path: Path, scale: float = 1.0) -> None:
        document = pdfium.PdfDocument(str(self.source_path))
        page = document[page_number]
        bitmap = page.render(scale=scale)
        pil_image = bitmap.to_pil()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pil_image.save(output_path)

    def crop_from_render(
        self,
        page_number: int,
        bbox: tuple[int, int, int, int],
        output_path: Path,
        scale: float = 1.5,
    ) -> None:
        document = pdfium.PdfDocument(str(self.source_path))
        page = document[page_number]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.crop(bbox).save(output_path)


class ParserAdapter:
    name = "base"

    def parse(self, run_id: str, pdf_id: str, pdf_path: Path, rendered_pages_dir: Path) -> ParsedDocument:
        raise NotImplementedError


class DoclingParserAdapter(ParserAdapter):
    name = "docling"
    max_pages = 8

    def parse(self, run_id: str, pdf_id: str, pdf_path: Path, rendered_pages_dir: Path) -> ParsedDocument:
        try:
            reader = PdfReader(str(pdf_path))
            metadata = reader.metadata or {}
            pages: list[ParsedPage] = []
            blocks: list[ParsedBlock] = []
            source_parts: list[str] = []
            page_renderer = PDFiumDocument(pdf_path)

            total_pages = len(reader.pages)
            parse_pages = min(total_pages, self.max_pages)
            for idx in range(parse_pages):
                page = reader.pages[idx]
                raw_text = page.extract_text() or ""
                normalized = _normalize_text(raw_text)
                source_parts.append(raw_text)
                render_path = rendered_pages_dir / f"page_{idx + 1:04d}.png"
                # Keep page-render artifacts lightweight for faster local lifecycle transitions.
                page_renderer.render_page(idx, render_path, scale=0.8)
                pages.append(
                    ParsedPage(
                        page_number=idx + 1,
                        width=float(page.mediabox.width),
                        height=float(page.mediabox.height),
                        full_page_path=str(render_path),
                        text_length=len(normalized),
                        has_text=bool(normalized),
                    )
                )
                blocks.append(
                    ParsedBlock(
                        block_id=f"{pdf_id}_page_{idx + 1}",
                        block_type="paragraph",
                        page=idx + 1,
                        text=raw_text,
                        normalized_text=normalized,
                        reading_order=idx + 1,
                    )
                )

            title = str(metadata.get("/Title")) if metadata.get("/Title") else None
            author_str = str(metadata.get("/Author")) if metadata.get("/Author") else ""
            authors = [value.strip() for value in re.split(r";|,| and ", author_str) if value.strip()]
            year_match = re.search(r"(19|20)\d{2}", " ".join([str(metadata.get("/CreationDate", "")), str(metadata.get("/ModDate", ""))]))
            publication_year = int(year_match.group(0)) if year_match else None

            return ParsedDocument(
                run_id=run_id,
                pdf_id=pdf_id,
                source_pdf_path=str(pdf_path),
                parser_name=self.name,
                metadata=ParsedMetadata(
                    title=title,
                    authors=authors,
                    publication_year=publication_year,
                    identifiers={},
                ),
                pages=pages,
                blocks=blocks,
                source_text="\n".join(source_parts).strip(),
                normalized_text=_normalize_text("\n".join(source_parts)),
                diagnostics={"truncated_pages": max(total_pages - parse_pages, 0)},
            )
        except Exception as exc:
            return ParsedDocument(
                run_id=run_id,
                pdf_id=pdf_id,
                source_pdf_path=str(pdf_path),
                parser_name=self.name,
                metadata=ParsedMetadata(),
                diagnostics={"parse_error": str(exc)},
            )


class ParseService:
    def __init__(self, artifact_store: ArtifactStore, adapter: ParserAdapter | None = None) -> None:
        self.store = artifact_store
        self.adapter = adapter or DoclingParserAdapter()

    def _should_ocr(self, parsed: ParsedDocument) -> bool:
        return len(parsed.normalized_text) < 40

    def _run_ocr(self, source_pdf: Path, ocr_pdf: Path) -> tuple[bool, str]:
        if shutil.which("ocrmypdf") is None:
            return False, "ocrmypdf_not_installed"
        command = ["ocrmypdf", "--skip-text", str(source_pdf), str(ocr_pdf)]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
        except subprocess.TimeoutExpired:
            return False, "ocr_timeout"
        if proc.returncode != 0:
            return False, f"ocr_failed:{proc.stderr.strip()[:120]}"
        return True, "ocr_success"

    def parse_run(self, run_id: str, run_dir: Path, config: RunConfig) -> dict[str, Any]:
        pdf_paths = sorted(Path(config.paths.pdf_dir).glob("*.pdf"))
        parsed_docs: list[ParsedDocument] = []
        parser_diags: list[dict[str, Any]] = []

        for index, pdf_path in enumerate(pdf_paths):
            pdf_id = stable_pdf_id(run_id, pdf_path.name, index)
            page_dir = run_dir / "parsed" / "pages" / pdf_id
            if pdf_path.stat().st_size > 1_000_000:
                parsed = ParsedDocument(
                    run_id=run_id,
                    pdf_id=pdf_id,
                    source_pdf_path=str(pdf_path),
                    parser_name=self.adapter.name,
                    metadata=ParsedMetadata(title=pdf_path.stem.replace("_", " ")),
                    diagnostics={"skipped_large_pdf_parse": True},
                )
            else:
                parsed = self.adapter.parse(run_id, pdf_id, pdf_path, page_dir)
            ocr_reason = "not_needed"
            if config.ocr.enabled and self._should_ocr(parsed):
                ocr_pdf = run_dir / "parsed" / "ocr" / f"{pdf_id}.pdf"
                ocr_pdf.parent.mkdir(parents=True, exist_ok=True)
                ocr_ok, ocr_reason = self._run_ocr(pdf_path, ocr_pdf)
                if ocr_ok:
                    parsed = self.adapter.parse(run_id, pdf_id, ocr_pdf, page_dir)
                    parsed.ocr_used = True
            self.store.write_json(run_dir / "parsed" / "native" / f"{pdf_id}.json", parsed.model_dump())
            parsed_docs.append(parsed)
            parser_diags.append(
                {
                    "pdf_id": pdf_id,
                    "pdf_path": str(pdf_path),
                    "parser_name": self.adapter.name,
                    "ocr_used": parsed.ocr_used,
                    "ocr_reason": ocr_reason,
                    "page_count": len(parsed.pages),
                    "text_chars": len(parsed.normalized_text),
                    "major_extraction_gap": len(parsed.normalized_text) < 20,
                }
            )

        self.store.atomic_write(
            run_dir / "parsed" / "documents.jsonl",
            "\n".join([doc.model_dump_json() for doc in parsed_docs]) + ("\n" if parsed_docs else ""),
        )
        self.store.write_json(run_dir / "parsed" / "diagnostics.json", {"documents": parser_diags})
        return {"documents": [doc.model_dump() for doc in parsed_docs], "diagnostics": parser_diags}
