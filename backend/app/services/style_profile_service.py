from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..artifacts import ArtifactStore


class StyleProfileService:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    @staticmethod
    def _infer_type(series: pd.Series) -> str:
        values = [str(v).strip() for v in series.dropna().tolist() if str(v).strip()]
        if not values:
            return "free_text"
        lowered = [v.lower() for v in values]
        if all(v in {"true", "false", "yes", "no"} for v in lowered):
            return "boolean"
        numeric_like = 0
        for value in values:
            try:
                float(value.replace(",", ""))
                numeric_like += 1
            except ValueError:
                pass
        if numeric_like / len(values) >= 0.8:
            return "numeric"
        if len(set(values)) <= max(8, int(len(values) * 0.4)):
            return "categorical"
        return "free_text"

    def build_profiles(self, run_dir: Path, table_df: pd.DataFrame, schema_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
        profiles: dict[str, dict[str, Any]] = {}
        diagnostics: list[dict[str, Any]] = []
        for _, schema_row in schema_df.iterrows():
            column_name = str(schema_row["column_name"])
            description = str(schema_row.get("description", "")).strip()
            col_series = table_df[column_name] if column_name in table_df.columns else pd.Series(dtype="object")
            values = [str(v).strip() for v in col_series.dropna().tolist() if str(v).strip()]
            output_type = self._infer_type(col_series)
            avg_len = int(sum(len(v) for v in values) / len(values)) if values else 0
            profiles[column_name] = {
                "column_name": column_name,
                "description": description,
                "expected_output_type": output_type,
                "expected_length": "short" if avg_len and avg_len < 24 else "medium" if avg_len < 80 else "long",
                "unit_conventions": "unknown",
                "source_value_count": len(values),
                "semantic_examples_included": False,
            }
            diagnostics.append(
                {
                    "column_name": column_name,
                    "source_value_count": len(values),
                    "semantic_examples_included": False,
                    "leakage_risk": "none",
                }
            )

        self.store.write_json(run_dir / "style_profiles" / "profiles.json", {"profiles": profiles})
        self.store.write_json(run_dir / "style_profiles" / "diagnostics.json", {"columns": diagnostics})
        return profiles
