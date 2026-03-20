from __future__ import annotations

from .models import SchemaColumn, StyleProfile


def build_style_profiles(rows: list[dict], schema: list[SchemaColumn]) -> list[StyleProfile]:
    profiles: list[StyleProfile] = []
    for column in schema:
        examples = [str(row.get(column.column_name, "")).strip() for row in rows if str(row.get(column.column_name, "")).strip()][:5]
        avg_length = int(sum(len(example) for example in examples) / len(examples)) if examples else 0
        shape = "numeric" if column.data_type in {"number", "integer", "float"} else "free_text"
        if examples and all(example.replace(".", "", 1).isdigit() for example in examples):
            shape = "numeric"
        profiles.append(
            StyleProfile(
                column_name=column.column_name,
                field_type_guess=column.data_type,
                expected_length="short" if avg_length < 25 else "medium" if avg_length < 120 else "long",
                tone="neutral",
                detail_level="concise" if avg_length < 120 else "detailed",
                value_shape=shape,
                unit_style="preserve_explicit_units",
                format_notes=f"Based on aggregate characteristics of up to {len(examples)} existing values; no raw examples injected.",
                example_risk="low",
            )
        )
    return profiles
