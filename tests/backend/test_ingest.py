from pathlib import Path

import pytest

from backend.app.config import RunConfig
from backend.app.ingest import IngestError, build_input_summary


REPO_ROOT = Path(__file__).resolve().parents[2]


def _base_config(table_name: str, verify_mode: bool = True) -> RunConfig:
    return RunConfig.model_validate(
        {
            "paths": {
                "table_path": str(REPO_ROOT / "tests" / "fixtures" / "tables" / table_name),
                "schema_path": str(REPO_ROOT / "tests" / "fixtures" / "schema" / "schema_fixture.csv"),
                "pdf_dir": str(REPO_ROOT / "tests" / "fixtures" / "papers"),
                "output_dir": str(REPO_ROOT / "runs"),
            },
            "parser": {},
            "ocr_fallback": {},
            "matching": {},
            "style_profiles": {},
            "retrieval": {},
            "provider": {},
            "figure_fallback": {},
            "review": {},
            "export": {},
            "verify_mode": verify_mode,
            "placeholders_treated_as_empty": ["", " "],
        }
    )


def test_missing_metadata_columns_rejected() -> None:
    config = _base_config("literature_missing_metadata.csv")
    with pytest.raises(IngestError):
        build_input_summary(config)


def test_placeholder_and_verify_mode_behavior() -> None:
    config_verify_on = _base_config("literature_placeholder_fixture.csv", verify_mode=True)
    summary_on, _ = build_input_summary(config_verify_on)
    assert summary_on.eligible_missing_cells > 0
    assert summary_on.eligible_filled_cells > 0

    config_verify_off = _base_config("literature_placeholder_fixture.csv", verify_mode=False)
    summary_off, _ = build_input_summary(config_verify_off)
    assert summary_off.eligible_filled_cells == 0
    assert summary_off.ineligible_cells > 0
