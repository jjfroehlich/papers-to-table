CREATE TABLE debug_extraction (
    pdf_id TEXT PRIMARY KEY,
    payload_json TEXT,
    created_at TEXT
)

CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    level TEXT,
    event_type TEXT,
    payload_json TEXT,
    created_at TEXT
)

CREATE TABLE extraction_attempts (
    attempt_id TEXT PRIMARY KEY,
    pdf_id TEXT,
    row_id TEXT,
    column TEXT,
    payload_json TEXT,
    created_at TEXT
)

CREATE TABLE locks (
    row_id TEXT,
    column TEXT,
    locked INTEGER,
    reason TEXT,
    PRIMARY KEY (row_id, column)
)

CREATE TABLE match_candidates (
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
)

CREATE TABLE matches (
    match_id TEXT PRIMARY KEY,
    pdf_id TEXT,
    row_id TEXT,
    confidence REAL,
    status TEXT,
    evidence_json TEXT,
    rationale TEXT,
    created_at TEXT
)

CREATE TABLE pdf_metadata (
    pdf_id TEXT PRIMARY KEY,
    title TEXT,
    authors TEXT,
    year TEXT,
    doi TEXT,
    confidence REAL,
    evidence_json TEXT,
    created_at TEXT
)

CREATE TABLE pdfs (
    pdf_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    sha1 TEXT NOT NULL,
    n_pages INTEGER,
    status TEXT,
    error TEXT,
    parse_source TEXT,
    created_at TEXT
)

CREATE TABLE proposals (
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
)

CREATE TABLE retrieval_chunks (
    pdf_id TEXT,
    chunk_id TEXT,
    chunk_pk TEXT,
    chunk_idx INTEGER,
    text TEXT,
    text_raw TEXT,
    text_norm TEXT,
    page_start INTEGER,
    page_end INTEGER,
    chunk_type TEXT,
    created_at TEXT,
    PRIMARY KEY (pdf_id, chunk_id)
)

CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY,
    proposal_id TEXT,
    decision TEXT,
    final_value TEXT,
    note TEXT,
    reviewed_at TEXT
)

CREATE TABLE rows (
    row_id TEXT PRIMARY KEY,
    row_index INTEGER,
    title TEXT,
    authors TEXT,
    year TEXT,
    doi TEXT,
    status TEXT
)
