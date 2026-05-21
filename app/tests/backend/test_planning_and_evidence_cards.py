from __future__ import annotations

import pathlib

from backend.app.column_planning import build_column_plan, persist_column_plan
from backend.app.evidence_cards import build_evidence_card, persist_evidence_card


def test_column_plan_handles_synthetic_schema_without_benchmark_names(tmp_path: pathlib.Path):
    schema = [
        {"column_name": "Authors", "description": "Full author list"},
        {"column_name": "Cell line", "description": "Experimental cell line used in methods"},
        {"column_name": "Main figure readout", "description": "Value shown in a plotted figure"},
    ]

    plan = build_column_plan(schema)
    by_name = {entry.column_name: entry for entry in plan.entries}
    path = persist_column_plan(tmp_path, plan)

    assert by_name["Authors"].group == "metadata"
    assert by_name["Cell line"].retrieval_profile == "methods"
    assert by_name["Main figure readout"].visual_policy == "prefer"
    assert path.exists()


def test_evidence_card_summarizes_parsed_document(tmp_path: pathlib.Path):
    doc = {
        "pdf_id": "paper_a",
        "metadata": {
            "title": "Paper A",
            "authors": ["Smith J", "Lee K"],
            "year": "2025",
            "doi": "10.1000/example",
        },
        "blocks": [
            {"block_type": "abstract", "text": "We tested a compact assay."},
            {"block_type": "paragraph", "section_context": "Methods", "text": "Cells were transfected."},
            {"block_type": "paragraph", "section_context": "Results", "text": "Accuracy reached 91%."},
            {"block_type": "table_region", "text": "Condition | Value\nA | 91%"},
        ],
        "figures": [
            {"figure_id": "fig_1", "page_number": 2, "caption_text": "Figure 1. Accuracy plot."}
        ],
        "full_text": "Accuracy reached 91% with 42 samples.",
    }

    card = build_evidence_card("run_test", doc)
    path = persist_evidence_card(tmp_path, card)

    assert card.abstract == "We tested a compact assay."
    assert card.methods_snippets
    assert card.results_snippets
    assert card.figure_catalog[0]["figure_ref"] == "fig_1"
    assert "91%" in card.detected_numbers
    assert path.exists()
