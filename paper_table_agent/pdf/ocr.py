from __future__ import annotations

import json
from pathlib import Path
import re

from paper_table_agent.config import OcrConfig


def should_trigger_ocr(page_text: list[str], config: OcrConfig) -> bool:
    if not page_text:
        return True
    total_chars = sum(len(text.strip()) for text in page_text)
    avg = total_chars / max(len(page_text), 1)
    whitespace_ratio, avg_token_length = _text_quality_metrics(page_text)
    if avg < config.ocr_trigger_min_chars_per_page:
        return True
    if whitespace_ratio < config.whitespace_ratio_min:
        return True
    if avg_token_length > config.avg_token_length_max:
        return True
    return False


def _text_quality_metrics(page_text: list[str]) -> tuple[float, float]:
    total_chars = 0
    whitespace = 0
    tokens = 0
    nonspace = 0
    for text in page_text:
        total_chars += len(text)
        whitespace += sum(1 for char in text if char.isspace())
        parts = re.findall(r"\\S+", text)
        tokens += len(parts)
        nonspace += sum(len(part) for part in parts)
    whitespace_ratio = whitespace / max(total_chars, 1)
    avg_token_length = nonspace / max(tokens, 1)
    return whitespace_ratio, avg_token_length


def run_ocr(path: Path, output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError:
        raise RuntimeError("OCR requires unstructured[local-inference] optional dependency")

    elements = partition_pdf(str(path), strategy="hi_res", infer_table_structure=True)
    pages: dict[int, list[str]] = {}
    for element in elements:
        page = element.metadata.page_number or 1
        pages.setdefault(page, []).append(element.text)
    page_text = ["\n".join(pages.get(idx + 1, [])) for idx in range(max(pages.keys(), default=0))]
    (output_dir / f"{path.stem}_ocr.txt").write_text("\n\n".join(page_text), encoding="utf-8")
    meta = {"source": "unstructured", "page_count": len(page_text)}
    (output_dir / f"{path.stem}_ocr_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return page_text
