from __future__ import annotations

from .models import ProposalState, SchemaColumn, StyleProfile


def build_style_guidance(profile: StyleProfile) -> dict:
    return {
        "field_type_guess": profile.field_type_guess,
        "expected_length": profile.expected_length,
        "tone": profile.tone,
        "detail_level": profile.detail_level,
        "value_shape": profile.value_shape,
        "unit_style": profile.unit_style,
        "format_notes": profile.format_notes,
    }


def build_text_request(row: dict, column: SchemaColumn, style_profile: StyleProfile, retrieval_context: list[dict], current_value: str, verify_mode: bool) -> dict:
    return {
        "task": "extract_cell_proposal",
        "column_name": column.column_name,
        "column_description": column.description,
        "row_context": {
            "row_id": row["row_id"],
            "title": row.get("Title", ""),
            "authors": row.get("Authors", ""),
            "publication_year": row.get("Publication Year", ""),
        },
        "current_value": current_value,
        "verify_mode": verify_mode,
        "style_guidance": build_style_guidance(style_profile),
        "retrieval_context": retrieval_context,
        "response_schema": {
            "proposal_state": [state.value for state in ProposalState],
            "proposed_value": "string|null",
            "rationale": "string",
            "calculation": "string",
            "evidence_quote": "string",
            "page": "integer",
            "support": "direct|inferred|weak",
        },
    }


def build_vision_request(base_request: dict, figure_package: dict) -> dict:
    payload = dict(base_request)
    payload["task"] = "extract_cell_proposal_from_figure"
    payload["figure_package"] = figure_package
    return payload
