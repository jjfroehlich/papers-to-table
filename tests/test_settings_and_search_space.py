from __future__ import annotations

from pathlib import Path

import pytest

from paper_optimizer.search_space import load_search_space
from paper_optimizer.settings import ConfigError, load_config


def test_load_config_success(config_path: Path) -> None:
    cfg = load_config(config_path)
    assert cfg["schema_version"] == "1.0"
    assert cfg["experiment_id"] == "exp_test"


def test_load_config_missing_required(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad)


def test_load_search_space_success(base_config: dict) -> None:
    ss = load_search_space(base_config)
    assert "retrieval_top_k" in ss.numeric_knobs
    assert ss.numeric_knobs["retrieval_top_k"] == [6]
