"""Batch 3: Retrieval — BM25-lite chunk retrieval from ParsedDocument.

T045 – MVP retrieval chunks (paragraph, section, caption, table_region)
T046 – Contextualized retrieval text + separate display text
T047 – MVP retrieval assembly (top_k=6, neighbor window, no reranking/HyDE)
T048 – Persist retrieval artifacts for inspection

Retrieval text separation is honest:
  - display_text: source-preserving text from the parsed document
  - retrieval_text: contextualized version with section header prepended
"""

from __future__ import annotations

import math
import pathlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

from .artifacts import write_json

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')
_COUNT_LIKE_PATTERN = re.compile(r"(^\s*#)|\b(how many|number|count|total|sample size|n\s*=)\b", re.IGNORECASE)


def _safe_filename(name: str, max_len: int = 48) -> str:
    """Return a filename-safe version of *name* for all platforms."""
    safe = _INVALID_FILENAME_CHARS.sub("_", name)
    safe = safe.replace(" ", "_")
    return safe[:max_len]

# ---------------------------------------------------------------------------
# Retrieval chunk contract (T045)
# ---------------------------------------------------------------------------

CHUNK_TYPES = frozenset({"paragraph", "section", "caption", "table_region", "abstract", "list_item"})


class RetrievalChunk(BaseModel):
    """A single typed retrieval unit from a parsed document."""
    chunk_id: str
    source_block_id: str
    chunk_type: str         # paragraph | section | caption | table_region | abstract | list_item
    page_number: int
    reading_order: int

    # T046: keep retrieval text and display text separate
    display_text: str       # source-preserving text for review display
    retrieval_text: str     # contextualized text used for BM25 scoring

    bbox: Optional[list[float]] = None
    provenance: str = "unknown"
    section_context: Optional[str] = None   # heading text of parent section
    is_neighbor: bool = False               # True when included as neighbor window


class RetrievalResult(BaseModel):
    """Top-k retrieval result for one (cell, query) pair."""
    run_id: str
    pdf_id: str
    column_name: str
    query: str
    top_k: int
    chunks: list[RetrievalChunk]
    retrieved_at: str


# ---------------------------------------------------------------------------
# Chunk building (T045)
# ---------------------------------------------------------------------------

def _to_block_chunk_type(block_type: str) -> str:
    """Map ParsedDocument block_type to RetrievalChunk chunk_type."""
    mapping = {
        "paragraph": "paragraph",
        "heading": "section",
        "section_heading": "section",
        "caption": "caption",
        "table_region": "table_region",
        "abstract": "abstract",
        "list_item": "list_item",
        "reference": "paragraph",   # treat references as paragraphs
        "unknown": "paragraph",
    }
    return mapping.get(block_type, "paragraph")


def build_chunks_from_parsed_doc(doc_dict: dict) -> list[RetrievalChunk]:
    """Build retrieval chunks from a ParsedDocument dict.

    Produces one chunk per block, mapping block_type to chunk_type.
    Attaches section context (nearest preceding heading) to each chunk.
    """
    blocks = doc_dict.get("blocks", [])
    if not blocks:
        return []

    chunks: list[RetrievalChunk] = []
    current_section: Optional[str] = None

    # Sort by reading_order to maintain order for section tracking
    sorted_blocks = sorted(blocks, key=lambda b: b.get("reading_order", 0))

    for idx, block in enumerate(sorted_blocks):
        block_type = block.get("block_type", "unknown")
        chunk_type = _to_block_chunk_type(block_type)

        # Update section context when we encounter a heading
        if block_type in ("heading", "section_heading"):
            current_section = block.get("text", "").strip()

        display_text = block.get("text", "").strip()
        if not display_text:
            continue

        # Build contextualized retrieval text (T046)
        if current_section and block_type not in ("heading", "section_heading"):
            retrieval_text = f"[Section: {current_section}] {display_text}"
        else:
            retrieval_text = display_text

        chunk = RetrievalChunk(
            chunk_id=f"chunk_{block.get('block_id', str(idx))}",
            source_block_id=block.get("block_id", str(idx)),
            chunk_type=chunk_type,
            page_number=block.get("page_number", 1),
            reading_order=block.get("reading_order", idx),
            display_text=display_text,
            retrieval_text=retrieval_text,
            bbox=block.get("bbox"),
            provenance=block.get("provenance", "unknown"),
            section_context=current_section,
            is_neighbor=False,
        )
        chunks.append(chunk)

    return chunks


# ---------------------------------------------------------------------------
# BM25-lite scoring (T047)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    text = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"[a-z0-9]+", text)


def _unique_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for term in terms:
        token = term.strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def build_retrieval_query(column_name: str, column_description: str) -> str:
    """Build a retrieval query with light field-aware expansion.

    The expansion is intentionally lexical and conservative. It helps columns whose
    user-facing wording does not closely match how papers describe the answer.
    """
    base_query = f"{column_name}: {column_description}".strip()
    combined = f"{column_name} {column_description}".lower()
    hints: list[str] = []

    if _COUNT_LIKE_PATTERN.search(combined):
        hints.extend([
            "count",
            "total",
            "number",
            "pairs",
            "pair",
            "combinations",
            "constructed",
            "tested",
            "included",
            "coverage",
        ])

    if re.search(r"\b(variant|variants|sequence|sequences|pair|pairs|barcode|barcodes|construct|constructs|plasmid|plasmids|element|elements)\b", combined):
        hints.extend([
            "sequences",
            "pairs",
            "combinations",
            "plasmids",
            "barcodes",
        ])

    if re.search(r"\b(episomal|ori|origin of replication|backbone|vector)\b", combined):
        hints.extend([
            "episomal",
            "plasmid",
            "vector",
            "backbone",
            "origin",
            "replication",
            "polya",
        ])

    if re.search(r"\b(clon|library|design|construct|assay format|readout)\b", combined):
        hints.extend([
            "methods",
            "design",
            "library",
            "cloning",
            "construct",
        ])

    hint_terms = _unique_terms(hints)
    if not hint_terms:
        return base_query

    return f"{base_query}\nRetrieval hints: {' '.join(hint_terms)}"


def _build_idf(chunks: list[RetrievalChunk]) -> dict[str, float]:
    """Compute IDF for each term across the chunk corpus."""
    N = len(chunks)
    if N == 0:
        return {}
    df: dict[str, int] = {}
    for chunk in chunks:
        terms = set(_tokenize(chunk.retrieval_text))
        for t in terms:
            df[t] = df.get(t, 0) + 1
    return {t: math.log((N - n + 0.5) / (n + 0.5) + 1.0) for t, n in df.items()}


def _bm25_score(
    query_terms: list[str],
    chunk_text: str,
    idf: dict[str, float],
    k1: float = 1.5,
    b: float = 0.75,
    avgdl: float = 100.0,
) -> float:
    tokens = _tokenize(chunk_text)
    dl = len(tokens) or 1
    tf_map: dict[str, int] = {}
    for t in tokens:
        tf_map[t] = tf_map.get(t, 0) + 1

    score = 0.0
    for term in query_terms:
        if term not in idf:
            continue
        tf = tf_map.get(term, 0)
        idf_val = idf[term]
        score += idf_val * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))
    return score


def score_chunks(query: str, chunks: list[RetrievalChunk]) -> list[tuple[float, RetrievalChunk]]:
    """BM25-lite scoring of chunks against a query."""
    if not chunks:
        return []

    query_terms = _tokenize(query)
    if not query_terms:
        return [(0.0, c) for c in chunks]

    idf = _build_idf(chunks)
    total_len = sum(len(_tokenize(c.retrieval_text)) for c in chunks)
    avgdl = total_len / len(chunks) if chunks else 100.0

    scored = [
        (_bm25_score(query_terms, c.retrieval_text, idf, avgdl=avgdl), c)
        for c in chunks
    ]
    scored.sort(key=lambda x: -x[0])
    return scored


# ---------------------------------------------------------------------------
# Neighbor-window expansion (T047)
# ---------------------------------------------------------------------------

def _add_neighbor_window(
    selected_ids: set[str],
    all_chunks: list[RetrievalChunk],
) -> list[RetrievalChunk]:
    """Add one immediate neighbor (prev/next by reading_order) per selected chunk.

    Returns a de-duplicated, reading-order-sorted list.
    Neighbor chunks are marked with is_neighbor=True.
    """
    by_order = {c.reading_order: c for c in all_chunks}
    orders = sorted(by_order.keys())
    order_idx = {o: i for i, o in enumerate(orders)}

    selected_orders = {
        c.reading_order for c in all_chunks if c.chunk_id in selected_ids
    }

    result_ids: set[str] = set(selected_ids)
    neighbor_chunks: list[RetrievalChunk] = []

    for sel_order in selected_orders:
        idx = order_idx.get(sel_order, -1)
        if idx < 0:
            continue
        for neighbor_idx in (idx - 1, idx + 1):
            if 0 <= neighbor_idx < len(orders):
                neighbor = by_order[orders[neighbor_idx]]
                if neighbor.chunk_id not in result_ids:
                    result_ids.add(neighbor.chunk_id)
                    # Mark as neighbor (copy with is_neighbor=True)
                    neighbor_chunks.append(
                        neighbor.model_copy(update={"is_neighbor": True})
                    )

    combined = [c for c in all_chunks if c.chunk_id in selected_ids] + neighbor_chunks
    combined.sort(key=lambda c: (c.page_number, c.reading_order))
    return combined


# ---------------------------------------------------------------------------
# Main retrieval entry point (T047)
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    doc_dict: dict,
    top_k: int = 6,
    include_captions: bool = True,
    include_tables: bool = True,
    include_neighbor_window: bool = True,
) -> list[RetrievalChunk]:
    """Retrieve top-k relevant chunks from a ParsedDocument dict.

    T047:
    - top_k = 6 default
    - captions and tables included when relevant
    - one neighbor window added per selected chunk
    - NO reranking, HyDE, or query expansion in MVP baseline
    """
    all_chunks = build_chunks_from_parsed_doc(doc_dict)
    if not all_chunks:
        return []

    # Filter to relevant chunk types
    allowed_types = {"paragraph", "section", "abstract", "list_item"}
    if include_captions:
        allowed_types.add("caption")
    if include_tables:
        allowed_types.add("table_region")

    candidate_chunks = [c for c in all_chunks if c.chunk_type in allowed_types]
    if not candidate_chunks:
        candidate_chunks = all_chunks

    scored = score_chunks(query, candidate_chunks)
    top_chunks = [chunk for _, chunk in scored[:top_k]]
    selected_ids = {c.chunk_id for c in top_chunks}

    if include_neighbor_window:
        result = _add_neighbor_window(selected_ids, all_chunks)
    else:
        result = sorted(top_chunks, key=lambda c: (c.page_number, c.reading_order))

    return result


# ---------------------------------------------------------------------------
# Persistence (T048)
# ---------------------------------------------------------------------------

def get_retrieval_dir(run_dir: pathlib.Path) -> pathlib.Path:
    return run_dir / "retrieval"


def get_retrieval_artifact_path(run_dir: pathlib.Path, pdf_id: str, column_name: str) -> pathlib.Path:
    safe_col = _safe_filename(column_name)
    return get_retrieval_dir(run_dir) / pdf_id / f"{safe_col}.json"


def persist_retrieval_result(
    run_dir: pathlib.Path,
    result: RetrievalResult,
) -> pathlib.Path:
    """Persist a retrieval result as JSON for inspection (T048)."""
    path = get_retrieval_artifact_path(run_dir, result.pdf_id, result.column_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, result.model_dump())
    return path


def load_retrieval_result(
    run_dir: pathlib.Path,
    pdf_id: str,
    column_name: str,
) -> Optional[RetrievalResult]:
    """Load a persisted retrieval result."""
    path = get_retrieval_artifact_path(run_dir, pdf_id, column_name)
    if not path.exists():
        return None
    from .artifacts import read_json
    try:
        data = read_json(path)
        return RetrievalResult.model_validate(data)
    except Exception:
        return None


def run_retrieval_for_cell(
    run_id: str,
    pdf_id: str,
    column_name: str,
    column_description: str,
    doc_dict: dict,
    run_dir: pathlib.Path,
    top_k: int = 6,
) -> RetrievalResult:
    """Build and persist retrieval result for one (pdf, column) pair."""
    query = build_retrieval_query(column_name, column_description)
    chunks = retrieve(query, doc_dict, top_k=top_k)
    result = RetrievalResult(
        run_id=run_id,
        pdf_id=pdf_id,
        column_name=column_name,
        query=query,
        top_k=top_k,
        chunks=chunks,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_retrieval_result(run_dir, result)
    return result
