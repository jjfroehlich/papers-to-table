CREATE TABLE IF NOT EXISTS pdfs (
    pdf_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    sha1 TEXT NOT NULL,
    n_pages INTEGER,
    status TEXT,
    error TEXT,
    parse_source TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS rows (
    row_id TEXT PRIMARY KEY,
    row_index INTEGER,
    title TEXT,
    authors TEXT,
    year TEXT,
    doi TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS locks (
    row_id TEXT,
    column TEXT,
    locked INTEGER,
    reason TEXT,
    PRIMARY KEY (row_id, column)
);

CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    pdf_id TEXT,
    row_id TEXT,
    confidence REAL,
    status TEXT,
    evidence_json TEXT,
    rationale TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS pdf_metadata (
    pdf_id TEXT PRIMARY KEY,
    title TEXT,
    authors TEXT,
    year TEXT,
    doi TEXT,
    confidence REAL,
    evidence_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS match_candidates (
    candidate_id TEXT PRIMARY KEY,
    pdf_id TEXT,
    row_id TEXT,
    score REAL,
    title TEXT,
    authors TEXT,
    year TEXT,
    rank INTEGER,
    source TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    pdf_id TEXT,
    row_id TEXT,
    column TEXT,
    proposed_value TEXT,
    status TEXT,
    confidence REAL,
    evidence_json TEXT,
    reasoning TEXT,
    flags_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS retrieval_chunks (
    pdf_id TEXT,
    chunk_id TEXT,
    chunk_pk TEXT,
    chunk_idx INTEGER,
    text TEXT,
    text_raw TEXT,
    retrieval_text TEXT,
    text_norm TEXT,
    metadata_json TEXT,
    page_start INTEGER,
    page_end INTEGER,
    chunk_type TEXT,
    created_at TEXT,
    PRIMARY KEY (pdf_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS extraction_attempts (
    attempt_id TEXT PRIMARY KEY,
    pdf_id TEXT,
    row_id TEXT,
    column TEXT,
    payload_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS debug_extraction (
    pdf_id TEXT PRIMARY KEY,
    payload_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    proposal_id TEXT,
    decision TEXT,
    final_value TEXT,
    note TEXT,
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    level TEXT,
    event_type TEXT,
    payload_json TEXT,
    created_at TEXT
);
