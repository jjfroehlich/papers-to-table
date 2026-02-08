from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
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
    header_footer_stats: dict[str, Any] = field(default_factory=dict)


def compute_sha1(path: Path) -> str:
    sha1 = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            sha1.update(chunk)
    return sha1.hexdigest()


def parse_pdf(path: Path) -> ParsedPdf:
    doc = fitz.open(path)
    page_text = [_build_page_text(page) for page in doc]
    page_text, header_footer_stats = _strip_repeated_headers(page_text)
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
    return ParsedPdf(
        pdf_id="",
        path=path,
        n_pages=n_pages,
        page_text=page_text,
        tokens=tokens,
        header_footer_stats=header_footer_stats,
    )


def _build_page_text(page: fitz.Page) -> str:
    words = page.get_text("words")
    if not words:
        return page.get_text("text")
    lines: dict[tuple[int, int], list[tuple[float, str]]] = {}
    line_order: dict[tuple[int, int], float] = {}
    for word in words:
        x0, y0, _x1, _y1, text, block_no, line_no, _word_no = word
        if not text:
            continue
        key = (int(block_no), int(line_no))
        lines.setdefault(key, []).append((float(x0), str(text)))
        line_order.setdefault(key, float(y0))
    ordered_keys = sorted(lines.keys(), key=lambda key: (key[0], key[1], line_order.get(key, 0.0)))
    rendered_lines = []
    for key in ordered_keys:
        entries = sorted(lines[key], key=lambda item: item[0])
        rendered_lines.append(" ".join(word for _, word in entries).strip())
    rendered_lines = _merge_hyphenated_lines(rendered_lines)
    return "\n".join(line for line in rendered_lines if line)


def _merge_hyphenated_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in lines:
        if not merged:
            merged.append(line)
            continue
        if re.search(r"[A-Za-z]-$", merged[-1]) and line and line[0].islower():
            merged[-1] = merged[-1][:-1] + line
        else:
            merged.append(line)
    return merged


def _strip_repeated_headers(page_text: list[str]) -> tuple[list[str], dict[str, Any]]:
    if len(page_text) < 2:
        return page_text, {"removed_lines": [], "removed_count": 0}
    top_lines: list[list[str]] = []
    bottom_lines: list[list[str]] = []
    for text in page_text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        top_lines.append(lines[:2])
        bottom_lines.append(lines[-2:] if len(lines) > 2 else [])
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    for lines in top_lines + bottom_lines:
        for line in lines:
            normalized = _normalize_header_line(line)
            if not normalized:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
            originals.setdefault(normalized, line)
    min_count = max(2, int(len(page_text) * 0.4))
    repeated = {
        key
        for key, count in counts.items()
        if count >= min_count and _is_headerish_line(originals.get(key, ""))
    }
    if not repeated:
        return page_text, {"removed_lines": [], "removed_count": 0}
    cleaned_pages: list[str] = []
    removed_lines: list[str] = []
    for text in page_text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        kept: list[str] = []
        for line in lines:
            normalized = _normalize_header_line(line)
            if normalized in repeated:
                removed_lines.append(line)
                continue
            kept.append(line)
        cleaned_pages.append("\n".join(kept))
    return cleaned_pages, {"removed_lines": sorted(set(removed_lines)), "removed_count": len(removed_lines)}


def _normalize_header_line(line: str) -> str:
    normalized = re.sub(r"\s+", " ", line.strip().lower())
    normalized = re.sub(r"\d+", "0", normalized)
    normalized = re.sub(r"[^a-z0-9\s:/.-]", "", normalized)
    return normalized[:140].strip()


def _is_headerish_line(line: str) -> bool:
    if not line:
        return False
    if len(line) > 160:
        return False
    tokens = (
        "doi",
        "journal",
        "volume",
        "vol.",
        "issue",
        "pages",
        "page ",
        "copyright",
        "preprint",
        "arxiv",
        "biorxiv",
        "medrxiv",
        "issn",
        "www.",
        "http",
    )
    lowered = line.lower()
    if any(token in lowered for token in tokens):
        return True
    if re.match(r"(?i)^page\s*\d+\s*(of\s*\d+)?", line.strip()):
        return True
    return len(lowered.split()) <= 6


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
