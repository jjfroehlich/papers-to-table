from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import pathlib

from backend.app.artifacts import init_run_bundle, write_json
from backend.app.extraction import EvidenceRecord, ProposalRecord, persist_evidence, persist_proposal
from backend.app.ids import generate_cell_id, generate_evidence_id, generate_row_id
from backend.app.ingest import load_table
from backend.app.matching import MatchOutcome, MatchResult, persist_match_artifacts
from backend.app.review import recompute_summaries
from backend.app.schemas import EvidenceSourceType, ProposalState, RunStatus, SupportLabel, WarningCategory


@dataclass(frozen=True)
class DemoRunIds:
    review: str
    export: str
    screenshots: str


@dataclass(frozen=True)
class DemoRuntime:
    runtime_root: pathlib.Path
    runs_dir: pathlib.Path
    run_ids: DemoRunIds


def prepare_demo_runtime(runtime_root: pathlib.Path, repo_root: pathlib.Path) -> DemoRuntime:
    runtime_root.mkdir(parents=True, exist_ok=True)
    runs_dir = runtime_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    table_path = repo_root / "tests" / "fixtures" / "tables" / "literature_fixture.xlsx"
    schema_path = repo_root / "tests" / "fixtures" / "tables" / "literature_fixture_schema.csv"
    pdf_dir = repo_root / "tests" / "fixtures" / "papers"
    pdf_path = pdf_dir / "paper_1.pdf"

    table = load_table(str(table_path))
    row_index = 2
    row = table.iloc[row_index]
    row_title = str(row["Title"])
    row_id = generate_row_id(row_index, row_title)

    run_ids = DemoRunIds(
        review="run_docs_review",
        export="run_docs_export",
        screenshots="run_docs_screenshots",
    )

    for offset, run_id in enumerate((run_ids.review, run_ids.export, run_ids.screenshots)):
        created_at = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=offset)
        _build_demo_run(
            runs_dir=runs_dir,
            run_id=run_id,
            row_index=row_index,
            row_id=row_id,
            row=row.to_dict(),
            row_title=row_title,
            repo_root=repo_root,
            table_path=table_path,
            schema_path=schema_path,
            pdf_dir=pdf_dir,
            pdf_path=pdf_path,
            created_at=created_at,
        )

    return DemoRuntime(runtime_root=runtime_root, runs_dir=runs_dir, run_ids=run_ids)


def _build_demo_run(
    *,
    runs_dir: pathlib.Path,
    run_id: str,
    row_index: int,
    row_id: str,
    row: dict,
    row_title: str,
    repo_root: pathlib.Path,
    table_path: pathlib.Path,
    schema_path: pathlib.Path,
    pdf_dir: pathlib.Path,
    pdf_path: pathlib.Path,
    created_at: datetime,
) -> None:
    run_dir = init_run_bundle(str(runs_dir), run_id)
    pdf_id = "paper_1"
    created_iso = created_at.isoformat()

    run_json = {
        "run_id": run_id,
        "status": RunStatus.completed_with_warnings.value,
        "config_path": str(repo_root / "config.example.json"),
        "table_path": str(table_path),
        "schema_path": str(schema_path),
        "pdf_dir": str(pdf_dir),
        "output_dir": str(runs_dir),
        "verify_mode": False,
        "eval_mode": False,
        "run_mode": "normal",
        "provider_token": "lm_studio",
        "provider_locality": "local",
        "provider_mode": "live_local",
        "provider_text_model_id": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
        "provider_vision_model_id": None,
        "provider_readiness_error": None,
        "started_at": created_iso,
        "completed_at": (created_at + timedelta(minutes=2)).isoformat(),
        "current_stage": None,
        "total_rows": 1,
        "eligible_cells": 2,
        "proposals_generated": 2,
        "proposals_reviewed": 0,
        "warnings": [
            {
                "category": WarningCategory.partial_extraction.value,
                "message": "Parser fallback used for one paper; review highlighted evidence before export.",
            },
            {
                "category": WarningCategory.fallback_evidence_used.value,
                "message": "One proposal uses quote-plus-page fallback instead of an exact highlight.",
            },
        ],
        "error_message": None,
        "created_at": created_iso,
    }
    write_json(run_dir / "run.json", run_json)
    write_json(
        run_dir / "config.snapshot.json",
        {
            "table_path": str(table_path),
            "schema_path": str(schema_path),
            "pdf_dir": str(pdf_dir),
            "output_dir": str(runs_dir),
            "verify_mode": False,
            "provider": {
                "token": "lm_studio",
                "base_url": "http://localhost:1234",
                "text_model": {"model_id": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF"},
            },
        },
    )
    write_json(
        run_dir / "inputs" / "input_summary.json",
        {
            "run_id": run_id,
            "table_path": str(table_path),
            "schema_path": str(schema_path),
            "pdf_dir": str(pdf_dir),
            "output_dir": str(runs_dir),
            "verify_mode": False,
            "table_rows": 1,
            "schema_columns": 2,
            "pdf_count": 1,
            "recorded_at": created_iso,
        },
    )
    write_json(
        run_dir / "summaries" / "provider_mode.json",
        {
            "provider_mode": "live_local",
            "provider_locality": "local",
            "provider_token": "lm_studio",
            "provider_readiness_error": None,
            "text_model_id": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
            "vision_model_id": None,
        },
    )
    parsed_dir = run_dir / "parsed" / pdf_id
    parsed_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        parsed_dir / "parsed_document.json",
        {
            "pdf_id": pdf_id,
            "source_path": str(pdf_path),
            "metadata": {
                "title": row_title,
                "authors": [str(row["Authors"]).split(";")[0].strip()],
                "year": int(str(row["Publication Year"])),
            },
            "full_text": "Demo parsed document used for Playwright regression coverage and screenshots.",
            "blocks": [],
        },
    )

    match_result = MatchResult(
        pdf_id=pdf_id,
        pdf_path=str(pdf_path),
        outcome=MatchOutcome.matched,
        matched_row_index=row_index,
        matched_row_title=row_title,
        score=0.98,
        runner_up_score=0.12,
        reasoning="Matched deterministically for docs coverage.",
        blocked=False,
        matched_at=created_iso,
    )
    persist_match_artifacts(run_dir, run_id, [match_result])

    species_cell = generate_cell_id(row_id, "Species")
    species_proposal_id = f"{run_id}__{species_cell}"
    exact_evidence_id = generate_evidence_id(species_proposal_id)
    supporting_evidence_id = generate_evidence_id(species_proposal_id)
    persist_proposal(
        run_dir,
        ProposalRecord(
            proposal_id=species_proposal_id,
            run_id=run_id,
            pdf_id=pdf_id,
            row_id=row_id,
            column_name="Species",
            cell_id=species_cell,
            state=ProposalState.found,
            support=SupportLabel.direct_evidence,
            proposed_value="human",
            rationale="- Exact quote on page 1 names the human assay system.\n- Supporting passage keeps the paper context visible.",
            primary_evidence_id=exact_evidence_id,
            ordered_supporting_evidence_ids=[supporting_evidence_id],
            evidence_ids=[exact_evidence_id, supporting_evidence_id],
            warning_flags=[],
            needs_more_evidence=False,
            is_verify_mode=False,
            provider_mode="live_local",
            created_at=created_iso,
        ),
    )
    persist_evidence(
        run_dir,
        EvidenceRecord(
            evidence_id=exact_evidence_id,
            run_id=run_id,
            proposal_id=species_proposal_id,
            pdf_id=pdf_id,
            source_type=EvidenceSourceType.direct_quote,
            quote_text="We apply VAMP-seq to quantify the abundance of 7,801 single-amino-acid variants of PTEN and TPMT in human cells.",
            page_number=1,
            exact_highlight_regions=[{"x0": 72, "y0": 540, "x1": 356, "y1": 575, "page": 1}],
            approximate_highlight_regions=None,
            anchor_confidence=0.98,
            evidence_rank=1,
            is_primary=True,
            created_at=created_iso,
        ),
    )
    persist_evidence(
        run_dir,
        EvidenceRecord(
            evidence_id=supporting_evidence_id,
            run_id=run_id,
            proposal_id=species_proposal_id,
            pdf_id=pdf_id,
            source_type=EvidenceSourceType.quote_plus_page,
            quote_text="We demonstrate that the assay is applicable to other genes, highlighting its generalizability in a human cell context.",
            page_number=2,
            exact_highlight_regions=None,
            approximate_highlight_regions=None,
            anchor_confidence=0.42,
            evidence_rank=2,
            is_primary=False,
            created_at=created_iso,
        ),
    )

    model_cell = generate_cell_id(row_id, "Model system")
    model_proposal_id = f"{run_id}__{model_cell}"
    model_evidence_id = generate_evidence_id(model_proposal_id)
    persist_proposal(
        run_dir,
        ProposalRecord(
            proposal_id=model_proposal_id,
            run_id=run_id,
            pdf_id=pdf_id,
            row_id=row_id,
            column_name="Model system",
            cell_id=model_cell,
            state=ProposalState.unclear,
            support=SupportLabel.weak_evidence,
            proposed_value="HEK293T",
            rationale="- The paper names HEK293T in a weaker context.\n- Review the fallback quote before exporting.",
            primary_evidence_id=model_evidence_id,
            ordered_supporting_evidence_ids=[],
            evidence_ids=[model_evidence_id],
            warning_flags=["fallback_evidence_used", "weak_evidence"],
            needs_more_evidence=True,
            is_verify_mode=False,
            provider_mode="live_local",
            created_at=created_iso,
        ),
    )
    persist_evidence(
        run_dir,
        EvidenceRecord(
            evidence_id=model_evidence_id,
            run_id=run_id,
            proposal_id=model_proposal_id,
            pdf_id=pdf_id,
            source_type=EvidenceSourceType.quote_plus_page,
            quote_text="We demonstrate variant abundance by massively parallel sequencing (VAMP-seq) in HEK293T cells.",
            page_number=3,
            exact_highlight_regions=None,
            approximate_highlight_regions=None,
            anchor_confidence=0.31,
            evidence_rank=1,
            is_primary=True,
            created_at=created_iso,
        ),
    )

    recompute_summaries(run_dir, run_id)
