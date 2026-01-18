from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
import pdfplumber


@dataclass
class ParsedPdf:
    pdf_id: str
    path: Path
    n_pages: int
    page_text: list[str]
    tokens: list[dict[str, Any]]


def compute_sha1(path: Path) -> str:
    sha1 = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            sha1.update(chunk)
    return sha1.hexdigest()


def parse_pdf(path: Path) -> ParsedPdf:
    doc = fitz.open(path)
    page_text = [page.get_text("text") for page in doc]
    n_pages = doc.page_count
    tokens: list[dict[str, Any]] = []
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            for word in page.extract_words():
                tokens.append(
                    {
                        "text": word.get("text"),
                        "page": page_index + 1,
                        "bbox": [word.get("x0"), word.get("top"), word.get("x1"), word.get("bottom")],
                    }
                )
    return ParsedPdf(pdf_id="", path=path, n_pages=n_pages, page_text=page_text, tokens=tokens)


def save_parsed(parsed: ParsedPdf, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pdf_id": parsed.pdf_id,
        "path": str(parsed.path),
        "n_pages": parsed.n_pages,
        "page_text": parsed.page_text,
    }
    (output_dir / f"{parsed.pdf_id}_pymupdf.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tokens_path = output_dir / f"{parsed.pdf_id}_tokens.jsonl"
    with tokens_path.open("w", encoding="utf-8") as handle:
        for token in parsed.tokens:
            handle.write(json.dumps(token) + "\n")
