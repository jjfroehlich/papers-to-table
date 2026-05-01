from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .artifacts import get_review_lookup_path, read_json, write_json
from .ids import generate_row_id
from .ingest import load_schema, load_table
from .matching import load_match_results


def build_review_lookup(
    *,
    run_id: str,
    table_path: str,
    schema_path: Optional[str],
    run_dir: Path,
) -> dict[str, Any]:
    dataframe = load_table(table_path)
    schema = load_schema(schema_path, table_path)
    return build_review_lookup_from_dataframe(
        run_id=run_id,
        table_path=table_path,
        schema_path=schema_path,
        dataframe=dataframe,
        schema=schema,
        match_results=load_match_results(run_dir),
    )


def build_review_lookup_from_dataframe(
    *,
    run_id: str,
    table_path: str,
    schema_path: Optional[str],
    dataframe: Any,
    schema: list[dict],
    match_results: list[Any],
) -> dict[str, Any]:
    def _read_match_field(match_result: Any, field_name: str) -> Any:
        if isinstance(match_result, dict):
            return match_result.get(field_name)
        return getattr(match_result, field_name, None)

    rows_by_id: dict[str, Any] = {}
    rows_by_index: dict[str, str] = {}
    for row_index, row in dataframe.iterrows():
        values = row.to_dict()
        title = str(values.get('Title', '') or '').strip() or None
        authors = str(values.get('Authors', '') or '').strip() or None
        year = values.get('Publication Year')
        row_id = generate_row_id(int(row_index), str(values.get('Title', '')))
        rows_by_index[str(int(row_index))] = row_id
        paper_label_parts = [part for part in [authors.split(';')[0].strip() if authors else None, str(year).strip() if year not in (None, '') else None] if part]
        rows_by_id[row_id] = {
            'row_id': row_id,
            'row_index': int(row_index),
            'title': title,
            'authors': authors,
            'year': year,
            'paper_label': ' · '.join(paper_label_parts) if paper_label_parts else title or row_id,
            'values': values,
        }

    columns_by_name: dict[str, Any] = {
        column['column_name']: {
            'name': column['column_name'],
            'description': column.get('description'),
            'field_type': column.get('field_type'),
            'allowed_values': column.get('allowed_values'),
        }
        for column in schema
    }

    papers_by_pdf_id: dict[str, Any] = {}
    for match_result in match_results:
        matched_row_index = _read_match_field(match_result, 'matched_row_index')
        pdf_id = _read_match_field(match_result, 'pdf_id')
        if pdf_id in (None, ''):
            continue
        match_outcome = _read_match_field(match_result, 'outcome')
        if hasattr(match_outcome, 'value'):
            match_outcome = match_outcome.value
        match_outcome = str(match_outcome) if match_outcome is not None else 'unknown'

        row_id = rows_by_index.get(str(matched_row_index)) if matched_row_index is not None else None
        row_context = rows_by_id.get(row_id) if row_id else None
        papers_by_pdf_id[str(pdf_id)] = {
            'pdf_id': str(pdf_id),
            'match_outcome': match_outcome,
            'matched_row_index': matched_row_index,
            'row_id': row_id,
            'paper_title': row_context.get('title') if row_context else None,
            'paper_authors': row_context.get('authors') if row_context else None,
            'paper_year': row_context.get('year') if row_context else None,
            'paper_label': row_context.get('paper_label') if row_context else str(pdf_id),
        }

    return {
        'run_id': run_id,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'table_path': table_path,
        'schema_path': schema_path,
        'rows_by_id': rows_by_id,
        'rows_by_index': rows_by_index,
        'columns_by_name': columns_by_name,
        'papers_by_pdf_id': papers_by_pdf_id,
    }


def persist_review_lookup(
    run_id: str,
    output_dir: str,
    table_path: str,
    schema_path: Optional[str],
    *,
    dataframe: Any | None = None,
    schema: list[dict] | None = None,
) -> dict[str, Any]:
    run_dir = Path(output_dir) / run_id
    if dataframe is not None and schema is not None:
        lookup = build_review_lookup_from_dataframe(
            run_id=run_id,
            table_path=table_path,
            schema_path=schema_path,
            dataframe=dataframe,
            schema=schema,
            match_results=load_match_results(run_dir),
        )
    else:
        lookup = build_review_lookup(run_id=run_id, table_path=table_path, schema_path=schema_path, run_dir=run_dir)
    write_json(get_review_lookup_path(output_dir, run_id), lookup)
    return lookup


def load_review_lookup(output_dir: str, run_id: str) -> Optional[dict[str, Any]]:
    path = get_review_lookup_path(output_dir, run_id)
    if not path.exists():
        return None
    return read_json(path)


def ensure_review_lookup(output_dir: str, run_id: str, table_path: str, schema_path: Optional[str]) -> dict[str, Any]:
    existing = load_review_lookup(output_dir, run_id)
    if existing is not None:
        return existing
    return persist_review_lookup(run_id, output_dir, table_path, schema_path)
