from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app import parsing
from backend.app.review import get_figure_crop_path


def _scratch_dir() -> Path:
    path = Path.cwd() / "tmp_pathsafe_artifacts" / uuid4().hex
    path.mkdir(parents=True)
    return path


@pytest.mark.skipif(parsing.os.name != "nt", reason="Windows path budget guard")
def test_safe_artifact_file_stem_respects_windows_budget():
    scratch = _scratch_dir()
    try:
        figures_dir = scratch / ("a" * 120) / "figures"
        figures_dir.mkdir(parents=True)

        stem = "MPRA04_cornwall_scoones_2025_signal_dependent_cres_fig100"
        safe_stem = parsing._safe_artifact_file_stem(figures_dir, stem, suffix=".png")
        path = figures_dir / f"{safe_stem}.png"

        assert len(str(path.resolve())) <= parsing._WINDOWS_PATH_BUDGET
        assert safe_stem != stem
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_get_figure_crop_path_uses_parsed_document_crop_path():
    scratch = _scratch_dir()
    try:
        run_dir = scratch / "run"
        parsed_dir = parsing.get_parsed_dir(run_dir, "paper")
        figures_dir = parsed_dir / "figures"
        figures_dir.mkdir(parents=True)
        crop = figures_dir / "short_fig.png"
        crop.write_bytes(b"png")
        (parsed_dir / "parsed_document.json").write_text(
            json.dumps(
                {
                    "figures": [
                        {
                            "figure_id": "very_long_original_figure_id",
                            "crop_path": str(crop.relative_to(run_dir)),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        assert get_figure_crop_path(run_dir, "paper", "very_long_original_figure_id") == crop
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
