from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from paper_table_agent.config import RunConfig, RunPaths, capture_run_config, create_run_paths, load_prompt_versions
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.workflow import run_workflow
from paper_table_agent.io.schema import group_columns, load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.pdf.highlight import render_page_image
from paper_table_agent.retrieval.index import load_index
from paper_table_agent.retrieval.pipeline import RetrievalConfig, retrieve_context
from paper_table_agent.store.db import Store

st.set_page_config(page_title='Paper Table Agent', layout='wide')

st.title('Paper Table Agent')

run_tab, review_tab, export_tab, debug_tab = st.tabs(["Run", "Review", "Export", "Advanced"])


with run_tab:
    st.header('Start a Run')
    table_path = st.text_input('Table path', value='')
    pdf_folder = st.text_input('PDF folder', value='')
    schema_sheet = st.text_input('Schema sheet', value='schema')
    title_col = st.text_input('Title column', value='')
    authors_col = st.text_input('Authors column', value='')
    year_col = st.text_input('Year column', value='')
    verify_mode = st.checkbox('Verify locked cells', value=False)
    fast_mode = st.checkbox('Fast mode (skip HyDE/query expansion)', value=False)

    if 'group_mapping' not in st.session_state:
        st.session_state['group_mapping'] = {}
    if 'group_selection' not in st.session_state:
        st.session_state['group_selection'] = []

    if table_path and schema_sheet:
        if st.button('Load schema'):
            try:
                specs = load_schema(Path(table_path), schema_sheet)
                grouped = group_columns(specs)
                st.session_state['group_mapping'] = {
                    name: [spec.column_name for spec in specs] for name, specs in grouped.items()
                }
                st.session_state['group_selection'] = list(st.session_state['group_mapping'].keys())
            except Exception as exc:  # noqa: BLE001
                st.error(f'Failed to load schema: {exc}')

    if st.session_state['group_mapping']:
        st.session_state['group_selection'] = st.multiselect(
            'Groups to extract (order matters)',
            list(st.session_state['group_mapping'].keys()),
            default=st.session_state['group_selection'],
        )

    if st.button('Start run'):
        config = RunConfig(
            table_path=Path(table_path),
            pdf_folder=Path(pdf_folder),
            schema_sheet_name=schema_sheet,
            title_col=title_col or None,
            authors_col=authors_col or None,
            year_col=year_col or None,
            verify_mode=verify_mode,
            fast_mode=fast_mode,
        )
        if st.session_state['group_selection'] and st.session_state['group_mapping']:
            config.extraction.groups = [
                {"name": group, "columns": st.session_state['group_mapping'][group]}
                for group in st.session_state['group_selection']
            ]
        run_paths = create_run_paths(config.table_path)
        prompt_versions = load_prompt_versions(Path('paper_table_agent/prompts'))
        capture_run_config(config, run_paths, prompt_versions)
        store = Store.init_db(run_paths.db_path)
        run_workflow(config=config, run_paths=run_paths, store=store)
        st.success(f'Run completed: {run_paths.run_dir}')

    st.divider()
    st.subheader('Resume or stop a run')
    resume_dir = st.text_input('Run directory to resume', value='')
    col_resume, col_stop = st.columns(2)
    with col_resume:
        if st.button('Resume run') and resume_dir:
            run_dir = Path(resume_dir)
            config_path = run_dir / 'run_config.json'
            config = RunConfig.model_validate_json(config_path.read_text(encoding='utf-8'))
            store = Store.init_db(run_dir / 'proposals.sqlite')
            run_workflow(config=config, run_paths=RunPaths(run_dir=run_dir), store=store, resume=True)
            st.success(f'Resumed run: {run_dir}')
    with col_stop:
        if st.button('Stop run') and resume_dir:
            (Path(resume_dir) / 'STOP').write_text('stop', encoding='utf-8')
            st.warning('Stop requested. The run will halt after the current PDF.')


with review_tab:
    st.header('Review Proposals')
    run_dir = st.text_input('Run directory', value='')
    if run_dir:
        run_dir_path = Path(run_dir)
        store = Store.init_db(run_dir_path / 'proposals.sqlite')
        run_config = json.loads((run_dir_path / 'run_config.json').read_text(encoding='utf-8'))
        table = load_table(Path(run_config['table_path']))

        rows = [dict(row) for row in store.fetch_rows()]
        proposals = [dict(row) for row in store.conn.execute('SELECT * FROM proposals')]
        matches = [dict(row) for row in store.fetch_matches()]
        reviews = store.fetch_reviews()

        proposal_by_row: dict[str, list[dict[str, Any]]] = {}
        needs_evidence_rows: set[str] = set()
        for proposal in proposals:
            flags = json.loads(proposal.get('flags_json') or '{}')
            proposal['flags'] = flags
            proposal['evidence'] = json.loads(proposal.get('evidence_json') or '[]')
            proposal_by_row.setdefault(proposal['row_id'], []).append(proposal)
            if flags.get('needs_more_evidence'):
                needs_evidence_rows.add(proposal['row_id'])

        match_by_row: dict[str, list[dict[str, Any]]] = {}
        for match in matches:
            if match.get('row_id') is None:
                continue
            match_by_row.setdefault(match['row_id'], []).append(match)

        st.subheader('Filters')
        only_with_proposals = st.checkbox('Only rows with proposals', value=True)
        only_ambiguous = st.checkbox('Only ambiguous mappings', value=False)
        only_duplicates = st.checkbox('Only duplicates', value=False)
        only_needs_evidence = st.checkbox('Only needs more evidence', value=False)
        search = st.text_input('Search title', value='')

        filtered_rows = []
        for row in rows:
            row_id = row['row_id']
            if only_with_proposals and row_id not in proposal_by_row:
                continue
            row_matches = match_by_row.get(row_id, [])
            if only_ambiguous and not any(match['status'] == 'ambiguous' for match in row_matches):
                continue
            if only_duplicates and not any(match['status'] == 'duplicate' for match in row_matches):
                continue
            if only_needs_evidence and row_id not in needs_evidence_rows:
                continue
            if search and search.lower() not in str(row.get('title', '')).lower():
                continue
            filtered_rows.append(row)

        row_options = {f"{row['row_id']} | {row.get('title', '')}": row['row_id'] for row in filtered_rows}
        selection = st.selectbox('Row', list(row_options.keys()) if row_options else [])
        if selection:
            row_id = row_options[selection]
            row_data = next((row for row in rows if row['row_id'] == row_id), {})
            st.subheader('Row details')
            st.write(
                {
                    'Title': row_data.get('title'),
                    'Authors': row_data.get('authors'),
                    'Year': row_data.get('year'),
                }
            )
            row_matches = match_by_row.get(row_id, [])
            if row_matches:
                st.write('Mapping status:', [match['status'] for match in row_matches])

            row_proposals = proposal_by_row.get(row_id, [])
            if not row_proposals:
                st.info('No proposals for this row.')

            pdf_map = {row['pdf_id']: row['path'] for row in store.list_pdfs()}
            for proposal in row_proposals:
                st.markdown(f"### {proposal['column']}")
                st.write('Current value:', table.dataframe.at[int(row_id), proposal['column']])
                st.write('Proposed value:', proposal['proposed_value'])
                st.write('Confidence:', proposal.get('confidence'))
                if proposal['flags'].get('needs_more_evidence'):
                    st.warning('Needs more evidence')

                evidence_items = proposal.get('evidence', [])
                if evidence_items:
                    evidence_choice = st.selectbox(
                        'Evidence',
                        list(range(len(evidence_items))),
                        format_func=lambda idx: f"Page {evidence_items[idx].get('page')}",
                        key=f"evidence-{proposal['proposal_id']}",
                    )
                    evidence = evidence_items[evidence_choice]
                    st.write('Quote:', evidence.get('quote'))
                    st.write('Page:', evidence.get('page'))
                    rects = evidence.get('rects') or []
                    pdf_path = pdf_map.get(proposal['pdf_id'])
                    if pdf_path and evidence.get('page'):
                        image = render_page_image(pdf_path, int(evidence['page']), rects)
                        st.image(image, caption=f"PDF page {evidence['page']}")
                    if not rects:
                        st.warning('No highlight rectangles available for this evidence.')

                decision = st.radio(
                    'Decision',
                    ['pending', 'accepted', 'rejected', 'revised'],
                    index=0,
                    key=f"decision-{proposal['proposal_id']}",
                )
                final_value = st.text_input(
                    'Final value (for revise)',
                    value=reviews.get(proposal['proposal_id'], {}).get('final_value', ''),
                    key=f"final-{proposal['proposal_id']}",
                )
                note = st.text_area(
                    'Note',
                    value=reviews.get(proposal['proposal_id'], {}).get('note', ''),
                    key=f"note-{proposal['proposal_id']}",
                )
                if st.button('Save decision', key=f"save-{proposal['proposal_id']}"):
                    store.insert_review(
                        {
                            'review_id': proposal['proposal_id'],
                            'proposal_id': proposal['proposal_id'],
                            'decision': decision,
                            'final_value': final_value,
                            'note': note,
                        }
                    )
                    st.success('Saved')

            verify_events = [
                json.loads(row['payload_json'])
                for row in store.conn.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'verify_result'"
                )
            ]
            row_verifications = [item for item in verify_events if item.get('row_id') == row_id]
            if row_verifications:
                st.subheader('Verification checks')
                for item in row_verifications:
                    st.write(item)


with export_tab:
    st.header('Export')
    export_run_dir = st.text_input('Run directory to export', value='')
    if st.button('Export') and export_run_dir:
        export_run(Path(export_run_dir))
        st.success('Export completed')


with debug_tab:
    st.header('Retrieval Debug')
    st.write('Provide a run directory and PDF ID to inspect retrieval chunks.')
    debug_run_dir = st.text_input('Run dir', value='', key='debug-run-dir')
    pdf_id = st.text_input('PDF ID', value='', key='debug-pdf-id')
    query = st.text_input('Query', value='', key='debug-query')
    if st.button('Retrieve') and debug_run_dir and pdf_id and query:
        index = load_index(Path(debug_run_dir) / 'artifacts' / 'retrieval_indexes' / pdf_id)
        if not index:
            st.error('Retrieval index not found for that PDF.')
        else:
            context = retrieve_context(index, query, RetrievalConfig())
            for chunk in context.chunks:
                st.write(
                    chunk.chunk_id,
                    f"score {chunk.score:.3f}",
                    f"pages {chunk.page_start}-{chunk.page_end}",
                )
                st.code(chunk.text[:800])
