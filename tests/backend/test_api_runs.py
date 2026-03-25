import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


REPO_ROOT = Path(__file__).resolve().parents[2]


def _config_path(tmp_path: Path, missing_path: bool = False) -> Path:
    output_dir = tmp_path / "out"
    payload = {
        "paths": {
            "table_path": str(REPO_ROOT / "tests" / "fixtures" / "tables" / "literature_placeholder_fixture.csv"),
            "schema_path": str(REPO_ROOT / "tests" / "fixtures" / "schema" / "schema_fixture.csv"),
            "pdf_dir": str(REPO_ROOT / "tests" / "fixtures" / "papers"),
            "output_dir": str(output_dir),
        },
        "parser": {},
        "ocr_fallback": {},
        "matching": {},
        "style_profiles": {},
        "retrieval": {},
        "provider": {"provider_name": "lm_studio", "model_name": "test-model", "locality": "local"},
        "figure_fallback": {},
        "review": {},
        "export": {},
        "verify_mode": True,
        "placeholders_treated_as_empty": ["", " "],
    }
    if missing_path:
        payload["paths"]["table_path"] = str(REPO_ROOT / "tests" / "fixtures" / "tables" / "does_not_exist.csv")
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(payload), encoding="utf-8")
    return config_file


def test_create_run_and_fetch_summaries(tmp_path: Path) -> None:
    client = TestClient(app)
    config_path = _config_path(tmp_path)

    create_response = client.post("/api/runs", json={"config_path": str(config_path)})
    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]

    summary = None
    for _ in range(30):
        time.sleep(0.05)
        summary_response = client.get(f"/api/runs/{run_id}/summary")
        assert summary_response.status_code == 200
        summary = summary_response.json()
        if summary["status"] in {"completed", "completed_with_warnings", "failed"}:
            break
    assert summary is not None
    assert summary["status"] == "completed_with_warnings"

    config_snapshot = client.get(f"/api/runs/{run_id}/config-snapshot")
    assert config_snapshot.status_code == 200
    input_summary = client.get(f"/api/runs/{run_id}/input-summary")
    assert input_summary.status_code == 200


def test_create_run_with_missing_path_fails(tmp_path: Path) -> None:
    client = TestClient(app)
    config_path = _config_path(tmp_path, missing_path=True)
    response = client.post("/api/runs", json={"config_path": str(config_path)})
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]
