from __future__ import annotations

import json
from pathlib import Path


def should_trigger_ocr(page_text: list[str], min_chars_per_page: int) -> bool:
    if not page_text:
        return True
    total_chars = sum(len(text.strip()) for text in page_text)
    avg = total_chars / max(len(page_text), 1)
    return avg < min_chars_per_page


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
