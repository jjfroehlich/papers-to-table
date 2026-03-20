from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import load_config
from backend.app.main import create_app
from backend.app.models import ReviewDecisionType
from backend.app.runner import Runner
from backend.app.table_io import classify_cells, load_schema, load_table, validate_metadata_columns

FIXTURE_CONFIG = 'tests/fixtures/configs/test-config.json'


def test_table_validation_and_verify_mode():
    rows, headers, _ = load_table('tests/fixtures/tables/literature_fixture.csv')
    validate_metadata_columns(headers)
    schema = load_schema('tests/fixtures/tables/literature_fixture.csv', 'tests/fixtures/schema/literature_schema.csv')
    normalized_rows, eligibility = classify_cells(rows[:5], schema, ['', ' ', 'NA'], True)
    assert normalized_rows[0]['row_id'].startswith('row-')
    filled_targets = [item for item in eligibility if item.current_value.strip() and item.verify_target]
    assert filled_targets, 'verify mode should include already-filled cells'
    placeholder_targets = [item for item in eligibility if item.reason == 'placeholder_treated_as_empty']
    assert placeholder_targets, 'single-space placeholders should be treated as empty when configured'


def test_runner_creates_artifacts(tmp_path: Path):
    config = load_config(FIXTURE_CONFIG)
    config.paths.output_dir = str(tmp_path / 'artifacts')
    runner = Runner(Path(config.paths.output_dir))
    run = runner.execute(config)
    run_dir = Path(config.paths.output_dir) / run.run_id
    assert run_dir.exists()
    assert (run_dir / 'config.snapshot.json').exists()
    assert (run_dir / 'parsed').exists()
    assert (run_dir / 'matching' / 'matches.jsonl').exists()
    assert (run_dir / 'summaries' / 'run_summary.json').exists()
    proposals = (run_dir / 'proposals' / 'proposals.jsonl').read_text(encoding='utf-8')
    assert 'proposal_state' in proposals


def test_api_review_and_bulk_accept_flow(tmp_path: Path):
    app = create_app(tmp_path / 'artifacts')
    client = TestClient(app)
    config = load_config(FIXTURE_CONFIG)
    config.paths.output_dir = str(tmp_path / 'artifacts')
    response = client.post('/api/runs', json={'config': config.model_dump(mode='json')})
    assert response.status_code == 200
    run_id = response.json()['run_id']

    proposals = client.get(f'/api/runs/{run_id}/proposals').json()['proposals']
    assert proposals
    detail = client.get(f"/api/runs/{run_id}/proposals/{proposals[0]['proposal_id']}")
    assert detail.status_code == 200
    assert 'row_context' in detail.json()

    review = client.post(f'/api/runs/{run_id}/reviews', json={'proposal_id': proposals[0]['proposal_id'], 'decision': ReviewDecisionType.ACCEPT.value})
    assert review.status_code == 200
    refreshed = client.get(f'/api/runs/{run_id}/summary').json()
    assert refreshed['reviewed_proposals'] >= 1

    pending_ids = [proposal['proposal_id'] for proposal in proposals[1:3]]
    bulk = client.post(f'/api/runs/{run_id}/bulk-accept', json={'proposal_ids': pending_ids})
    assert bulk.status_code == 200
    workbook = client.get(f'/api/runs/{run_id}/downloads/workbook')
    assert workbook.status_code == 200


def test_match_outcomes_cover_unmatched_ambiguous_and_duplicate(tmp_path: Path):
    app = create_app(tmp_path / 'artifacts')
    client = TestClient(app)
    config = load_config(FIXTURE_CONFIG)
    config.paths.output_dir = str(tmp_path / 'artifacts')
    run_id = client.post('/api/runs', json={'config': config.model_dump(mode='json')}).json()['run_id']
    matches = client.get(f'/api/runs/{run_id}/matches').json()['matches']
    outcomes = {item['outcome'] for item in matches}
    assert 'unmatched' in outcomes
    assert 'duplicate_row_conflict' in outcomes
    assert 'ambiguous' in outcomes or any('Top candidate' in item['rationale'] for item in matches)


def test_invalid_metadata_rejected(tmp_path: Path):
    invalid = tmp_path / 'invalid.csv'
    invalid.write_text('Title,Authors\nOnly title,Someone\n', encoding='utf-8')
    config = load_config(FIXTURE_CONFIG)
    config.paths.table_path = str(invalid)
    config.paths.output_dir = str(tmp_path / 'artifacts')
    runner = Runner(Path(config.paths.output_dir))
    with pytest.raises(ValueError):
        runner.execute(config)
