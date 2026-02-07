from __future__ import annotations

from pathlib import Path

import fitz


def build_fixture_pdf(output_dir: Path, filename: str = "synthetic_fixture.pdf") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    doc = fitz.open()
    _add_page(
        doc,
        "\n".join(
            [
                "Synthetic MPRA Study",
                "Authors: Jane Doe; John Smith",
                "Year: 2024",
                "",
                "Page 1 - Methods",
                "We tested 48,391 variants.",
                "We used plasmid-based MPRA.",
                "UMIs were not used.",
                "Predictive feature: chromatin accessibility correlates with activity in MPRA.",
            ]
        ),
    )
    _add_page(
        doc,
        "\n".join(
            [
                "Page 2 - Results",
                "Variant count confirms 48,391 total.",
                "Assay type remained plasmid-based MPRA.",
                "No UMIs were used in this experiment.",
            ]
        ),
    )
    doc.save(path)
    doc.close()
    return path


def _add_page(doc: fitz.Document, text: str) -> None:
    page = doc.new_page()
    rect = fitz.Rect(36, 36, 560, 780)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv", align=0)
