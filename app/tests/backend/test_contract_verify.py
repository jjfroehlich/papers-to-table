from __future__ import annotations
import json
from pathlib import Path
from backend.app.contract_verify import verify_run_bundle

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows)+"\n", encoding='utf-8')

def _make_run(tmp_path: Path) -> Path:
    run = tmp_path / 'run'
    for rel in ['summaries','review','proposals','evidence','exports']:
        (run / rel).mkdir(parents=True, exist_ok=True)
    (run / 'run.json').write_text(json.dumps({'run_id':'r1','status':'completed','artifact_schema_version':'main_run_bundle.v2'}), encoding='utf-8')
    (run / 'summaries' / 'run_summary.json').write_text(json.dumps({'run_id':'r1','status':'completed','total_rows':1,'eligible_cells':1,'proposals_generated':1,'proposals_reviewed':1}), encoding='utf-8')
    _write_jsonl(run / 'evidence' / 'evidence.jsonl', [{'evidence_id':'e1','run_id':'r1','proposal_id':'p1','source_type':'direct_quote','is_primary':True}])
    _write_jsonl(run / 'proposals' / 'proposals.jsonl', [{'proposal_id':'p1','run_id':'r1','row_id':'row-1','column_name':'col','cell_id':'row-1::col','state':'found','support':'direct_evidence','evidence_ids':['e1']}])
    _write_jsonl(run / 'review' / 'decisions.jsonl', [{'review_decision_id':'d1','run_id':'r1','proposal_id':'p1','cell_id':'row-1::col','decision':'accepted','decision_source':'human_individual','decided_at':'2026-01-01T00:00:00Z'}])
    (run / 'exports' / 'audit_log_1.json').write_text(json.dumps([{'proposal_id':'p1','cell_id':'row-1::col','decision':'accepted','decision_source':'human_individual','auto_accepted':False,'exported_value':'x'}]), encoding='utf-8')
    return run

def test_verify_run_bundle_passes(tmp_path: Path) -> None:
    assert verify_run_bundle(_make_run(tmp_path))['ok'] is True

def test_verify_run_bundle_catches_cross_file_errors(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    _write_jsonl(run / 'review' / 'decisions.jsonl', [{'review_decision_id':'d1','run_id':'r1','proposal_id':'missing','cell_id':'row-1::col','decision':'accepted','decision_source':'human_individual','decided_at':'2026-01-01T00:00:00Z'}])
    result = verify_run_bundle(run)
    assert result['ok'] is False
    assert any('missing proposal_id' in e for e in result['errors'])


def test_verify_run_bundle_rejects_invalid_decision_source(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    _write_jsonl(run / 'review' / 'decisions.jsonl', [{'review_decision_id':'d1','run_id':'r1','proposal_id':'p1','cell_id':'row-1::col','decision':'accepted','decision_source':'not_real','decided_at':'2026-01-01T00:00:00Z'}])
    result = verify_run_bundle(run)
    assert result['ok'] is False
    assert any('decision_source' in e for e in result['errors'])
