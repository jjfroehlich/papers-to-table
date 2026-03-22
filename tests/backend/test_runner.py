from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import load_config
from backend.app.extraction import ExtractionOrchestrator
from backend.app.main import create_app
from backend.app.models import (
    AppConfig,
    CellEligibility,
    CellStatus,
    MatchOutcome,
    MatchRecord,
    ParsedDocument,
    ParsedDocumentMetadata,
    ParsedPage,
    ProposalState,
    ReviewDecisionType,
    RuntimePaths,
    SchemaColumn,
    StyleProfile,
)
from backend.app.runner import Runner
from backend.app.retrieval import RetrievalChunk
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
    config = load_config(FIXTURE_CONFIG)
    config.paths.output_dir = str(tmp_path / 'artifacts')
    run = Runner(Path(config.paths.output_dir)).execute(config)
    app = create_app(tmp_path / 'artifacts')
    client = TestClient(app)
    run_id = run.run_id

    proposals = client.get(f'/api/runs/{run_id}/proposals').json()['proposals']
    assert proposals
    actionable_proposal = next(
        (
            proposal
            for proposal in proposals
            if proposal['proposal_state'] not in {'blocked', 'error', 'skipped'} and proposal['proposed_value']
        ),
        None,
    )
    assert actionable_proposal is not None
    detail = client.get(f"/api/runs/{run_id}/proposals/{proposals[0]['proposal_id']}")
    assert detail.status_code == 200
    assert 'row_context' in detail.json()

    review = client.post(f'/api/runs/{run_id}/reviews', json={'proposal_id': actionable_proposal['proposal_id'], 'decision': ReviewDecisionType.ACCEPT.value})
    assert review.status_code == 200
    refreshed = client.get(f'/api/runs/{run_id}/summary').json()
    assert refreshed['reviewed_proposals'] >= 1

    pending_ids = [proposal['proposal_id'] for proposal in proposals[:5]]
    bulk = client.post(f'/api/runs/{run_id}/bulk-accept', json={'proposal_ids': pending_ids})
    assert bulk.status_code == 200
    decisions_path = tmp_path / 'artifacts' / run_id / 'review' / 'decisions.jsonl'
    decisions_text = decisions_path.read_text(encoding='utf-8')
    assert '"decided_at"' in decisions_text
    audit_log = (tmp_path / 'artifacts' / run_id / 'exports' / 'audit_log.csv').read_text(encoding='utf-8')
    assert 'recorded_in_review_log' not in audit_log
    workbook = client.get(f'/api/runs/{run_id}/downloads/workbook')
    assert workbook.status_code == 200


def test_match_outcomes_cover_unmatched_ambiguous_and_duplicate(tmp_path: Path):
    config = load_config(FIXTURE_CONFIG)
    config.paths.output_dir = str(tmp_path / 'artifacts')
    run = Runner(Path(config.paths.output_dir)).execute(config)
    app = create_app(tmp_path / 'artifacts')
    client = TestClient(app)
    run_id = run.run_id
    matches = client.get(f'/api/runs/{run_id}/matches').json()['matches']
    outcomes = {item['outcome'] for item in matches}
    assert 'unmatched' in outcomes
    assert 'duplicate_row_conflict' in outcomes
    assert 'ambiguous' in outcomes or any('Top candidate' in item['rationale'] for item in matches)


def test_input_summary_includes_config_source_and_output_dir(tmp_path: Path):
    config = load_config(FIXTURE_CONFIG)
    config.paths.output_dir = str(tmp_path / 'custom-artifacts')
    run = Runner(Path(config.paths.output_dir)).execute(config, config_path='inline-request')
    app = create_app(tmp_path / 'artifacts')
    client = TestClient(app)
    run_id = run.run_id

    input_summary = client.get(f'/api/runs/{run_id}/input-summary')
    assert input_summary.status_code == 200
    payload = input_summary.json()
    assert payload['output_dir'] == str(tmp_path / 'custom-artifacts')
    assert payload['config_path'] == 'inline-request'


def test_api_create_run_returns_immediate_run_record(tmp_path: Path):
    app = create_app(tmp_path / 'artifacts')
    client = TestClient(app)
    config = load_config(FIXTURE_CONFIG)
    config.paths.output_dir = str(tmp_path / 'artifacts')

    response = client.post('/api/runs', json={'config': config.model_dump(mode='json')})

    assert response.status_code == 200
    payload = response.json()
    assert payload['run_id'].startswith('run-')
    assert payload['status'] in {'created', 'validating', 'running'}


def test_missing_config_snapshot_returns_409_instead_of_500(tmp_path: Path):
    run_dir = tmp_path / 'artifacts' / 'run-missing-config'
    run_dir.mkdir(parents=True)
    (run_dir / 'run.json').write_text(
        '{"run_id": "run-missing-config", "created_at": "2026-03-22T00:00:00Z", "updated_at": "2026-03-22T00:00:00Z", "status": "created", "warnings": [], "provider_name": "stub-lmstudio", "provider_model": "stub-model", "provider_locality": "local", "verify_mode": true, "artifact_root": "artifacts/run-missing-config", "config_path": "", "message": ""}',
        encoding='utf-8',
    )

    app = create_app(tmp_path / 'artifacts')
    client = TestClient(app)

    response = client.get('/api/runs/run-missing-config/config')

    assert response.status_code == 409
    assert response.json()['detail'] == 'Config snapshot is not ready yet'


def test_extraction_uses_quote_page_fallback_when_geometry_is_missing():
    config = AppConfig(paths=RuntimePaths(table_path='table.csv', schema_path=None, pdf_dir='pdfs', output_dir='artifacts'))
    orchestrator = ExtractionOrchestrator(config)
    match = MatchRecord(pdf_id='pdf-1', pdf_name='paper.pdf', outcome=MatchOutcome.MATCHED, row_id='row-1', row_index=1)
    row = {'row_id': 'row-1', 'row_index': 1, 'Title': 'Paper title', 'Authors': 'Someone', 'Publication Year': '2024'}
    eligibility = {
        'Assay': CellEligibility(
            row_id='row-1',
            column_name='Assay',
            cell_id='cell-row-1-assay',
            current_value='',
            status=CellStatus.EMPTY,
            eligible=True,
            verify_target=False,
        )
    }
    schema = [SchemaColumn(column_name='Assay', description='Assay used in the study')]
    style_profiles = {
        'Assay': StyleProfile(
            column_name='Assay',
            field_type_guess='text',
            expected_length='short',
            tone='neutral',
            detail_level='concise',
            value_shape='free_text',
            unit_style='preserve_explicit_units',
            format_notes='No raw examples injected.',
        )
    }
    parsed_doc = ParsedDocument(
        pdf_id='pdf-1',
        pdf_name='paper.pdf',
        parser_name='fixture',
        parser_path='fixture',
        metadata=ParsedDocumentMetadata(title='Paper title', authors=['Someone'], publication_year='2024'),
        pages=[ParsedPage(page_number=1, width=700, height=900, image_path='parsed/pdf-1/page-1.png', text='Assay: Flow cytometry')],
        blocks=[],
        figures=[],
    )
    retrieval_chunks = [
        RetrievalChunk(
            chunk_id='chunk-1',
            pdf_id='pdf-1',
            page=1,
            block_type='paragraph',
            retrieval_text='Assay: Flow cytometry',
            display_text='Assay: Flow cytometry',
            score=0.9,
            bbox=None,
        )
    ]

    proposals, evidence = orchestrator.extract_for_match('run-1', match, row, parsed_doc, eligibility, schema, style_profiles, retrieval_chunks)

    assert proposals[0].proposal_state == ProposalState.FOUND
    assert proposals[0].needs_more_evidence is True
    assert 'quote_page_fallback' in {flag.value for flag in proposals[0].warning_flags}
    assert evidence[0].highlight == []
    assert evidence[0].page_width == 700
    assert evidence[0].page_height == 900


def test_invalid_metadata_rejected(tmp_path: Path):
    invalid = tmp_path / 'invalid.csv'
    invalid.write_text('Title,Authors\nOnly title,Someone\n', encoding='utf-8')
    config = load_config(FIXTURE_CONFIG)
    config.paths.table_path = str(invalid)
    config.paths.output_dir = str(tmp_path / 'artifacts')
    runner = Runner(Path(config.paths.output_dir))
    with pytest.raises(ValueError):
        runner.execute(config)
