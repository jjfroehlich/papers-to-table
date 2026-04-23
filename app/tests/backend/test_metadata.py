from __future__ import annotations

from backend.app.metadata import extract_matching_metadata, extract_matching_metadata_debug, resolve_metadata_field


def test_resolve_metadata_field_prefers_parser_metadata_for_doi() -> None:
    resolution = resolve_metadata_field(
        "DOI",
        "Digital object identifier",
        {
            "metadata": {"doi": "10.1000/xyz123"},
            "blocks": [
                {
                    "page_number": 1,
                    "text": "DOI: 10.1000/xyz123",
                    "block_type": "paragraph",
                }
            ],
            "full_text": "DOI: 10.1000/xyz123",
            "parser_used": "docling",
        },
    )

    assert resolution is not None
    assert resolution.extraction_lane == "metadata_front_matter"
    assert resolution.state == "found"
    assert resolution.proposed_value == "10.1000/xyz123"
    assert resolution.source == "parser_metadata"
    assert resolution.failure_attribution is None


def test_resolve_metadata_field_marks_ambiguous_front_matter_candidates() -> None:
    resolution = resolve_metadata_field(
        "Journal",
        "Publication venue",
        {
            "blocks": [
                {"page_number": 1, "text": "Nature Medicine", "block_type": "paragraph"},
                {"page_number": 1, "text": "Science", "block_type": "paragraph"},
            ],
            "full_text": "Nature Medicine\nScience",
            "parser_used": "docling",
        },
    )

    assert resolution is not None
    assert resolution.state == "unclear"
    assert resolution.source == "front_matter_conflict"
    assert resolution.failure_attribution == "evidence_ambiguity"
    assert resolution.fallback_reasons == ["multiple_front_matter_candidates"]


def test_resolve_metadata_field_reports_front_matter_source_for_title_fallback() -> None:
    resolution = resolve_metadata_field(
        "Title",
        "Paper title",
        {
            "blocks": [
                {"page_number": 1, "text": "A durable title from the front matter", "block_type": "heading"},
            ],
            "full_text": "A durable title from the front matter",
            "parser_used": "docling",
        },
    )

    assert resolution is not None
    assert resolution.state == "found"
    assert resolution.source == "front_matter_block"
    assert resolution.proposed_value == "A durable title from the front matter"


def test_extract_matching_metadata_prefers_front_matter_year_before_full_text_fallback() -> None:
    resolved = extract_matching_metadata(
        {
            "blocks": [
                {"page_number": 1, "text": "Published in 2021 by the journal.", "block_type": "paragraph"},
            ],
            "full_text": "Published in 2021 by the journal. The cohort was enrolled in 2024.",
        }
    )

    assert resolved.year == 2021


def test_extract_matching_metadata_debug_surfaces_front_matter_and_field_diagnostics() -> None:
    debug = extract_matching_metadata_debug(
        {
            "metadata": {"title": "Parser Title", "doi": "10.1000/xyz123"},
            "blocks": [
                {"page_number": 1, "text": "Parser Title", "block_type": "heading"},
                {"page_number": 1, "text": "DOI: 10.1000/xyz123", "block_type": "paragraph"},
            ],
            "full_text": "Parser Title\nDOI: 10.1000/xyz123",
            "parser_used": "docling",
        }
    )

    assert debug.metadata.title == "Parser Title"
    assert debug.front_matter_diagnostics["front_matter_detected"] is True
    assert debug.field_diagnostics["title"].state == "found"
    assert debug.field_diagnostics["doi"].diagnostics["candidate_count"] >= 1
