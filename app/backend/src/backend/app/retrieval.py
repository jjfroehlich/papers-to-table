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

import hashlib
import math
import pathlib
import re
import unicodedata
from datetime import datetime, timezone
from time import perf_counter
from typing import Optional

from pydantic import BaseModel, Field

from .artifacts import write_json

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')
_COUNT_LIKE_PATTERN = re.compile(r"(^\s*#)|\b(how many|number|count|total|sample size|n\s*=)\b", re.IGNORECASE)
SUPPORTED_RETRIEVAL_MODES = frozenset({"lexical", "hybrid_experimental"})


def _safe_filename(name: str, max_len: int = 16) -> str:
    """Return a filename-safe version of *name* for all platforms."""
    safe = _INVALID_FILENAME_CHARS.sub("_", name)
    safe = safe.replace(" ", "_")
    safe = re.sub(r"_+", "_", safe).strip("._")
    if not safe:
        safe = "artifact"
    if len(safe) <= max_len:
        return safe
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    truncated = safe[:max_len].rstrip("._") or "artifact"
    return f"{truncated}_{digest}"

# ---------------------------------------------------------------------------
# Retrieval chunk contract (T045)
# ---------------------------------------------------------------------------

CHUNK_TYPES = frozenset({"paragraph", "section", "caption", "table_region", "abstract", "list_item", "figure"})


class RetrievalChunk(BaseModel):
    """A single typed retrieval unit from a parsed document."""
    chunk_id: str
    source_block_id: str
    chunk_type: str         # paragraph | section | caption | table_region | abstract | list_item | figure
    page_number: int
    reading_order: int

    # T046: keep retrieval text and display text separate
    display_text: str       # source-preserving text for review display
    retrieval_text: str     # contextualized text used for BM25 scoring

    bbox: Optional[list[float]] = None
    provenance: str = "unknown"
    section_context: Optional[str] = None   # heading text of parent section
    is_neighbor: bool = False               # True when included as neighbor window
    figure_ref: Optional[str] = None
    caption_text: Optional[str] = None
    crop_path: Optional[str] = None
    full_page_path: Optional[str] = None


class RetrievalResult(BaseModel):
    """Top-k retrieval result for one (cell, query) pair."""
    run_id: str
    pdf_id: str
    column_name: str
    query: str
    top_k: int
    chunks: list[RetrievalChunk]
    mode: str = "lexical"
    request_mode: str = "baseline"
    policy: dict[str, object] = Field(default_factory=dict)
    stats: dict[str, object] = Field(default_factory=dict)
    rescue_reason: Optional[str] = None
    retrieved_at: str


class RetrievalPolicy(BaseModel):
    query_mode: str = "lexical"
    scoring_profile: str = "bm25_lite"
    heuristic_tags: list[str] = Field(default_factory=list)
    hint_terms: list[str] = Field(default_factory=list)
    allowed_chunk_types: list[str] = Field(default_factory=list)
    include_captions: bool = True
    include_tables: bool = True
    include_neighbor_window: bool = True
    top_k: int = 6


class RetrievalStats(BaseModel):
    chunk_build_ms: float = 0.0
    idf_build_ms: float = 0.0
    scoring_ms: float = 0.0
    total_ms: float = 0.0
    chunk_count_total: int = 0
    chunk_count_by_type: dict[str, int] = Field(default_factory=dict)
    candidate_chunk_count: int = 0
    selected_chunk_count: int = 0
    neighbor_chunk_count: int = 0
    chunk_build_count: int = 1
    idf_build_count: int = 1
    cached_index_used: bool = False


class RetrievalPreparedIndex(BaseModel):
    all_chunks: list[RetrievalChunk]
    candidate_chunks: list[RetrievalChunk]
    chunk_count_by_type: dict[str, int]
    avgdl: float
    idf: dict[str, float]


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

    figure_order_base = (
        max((int(block.get("reading_order", 0) or 0) for block in sorted_blocks), default=0) + 1
    )
    caption_by_id = {
        str(block.get("block_id")): block
        for block in sorted_blocks
        if str(block.get("block_type") or "") == "caption"
    }
    for fig_idx, figure in enumerate(doc_dict.get("figures", []) or []):
        if not isinstance(figure, dict):
            continue
        figure_ref = str(figure.get("figure_id") or figure.get("id") or f"figure_{fig_idx + 1}").strip()
        caption_text = str(figure.get("caption_text") or "").strip()
        caption_block_id = figure.get("caption_block_id")
        caption_block = caption_by_id.get(str(caption_block_id)) if caption_block_id is not None else None
        if not caption_text and caption_block is not None:
            caption_text = str(caption_block.get("text") or "").strip()
        if not caption_text and not figure_ref:
            continue
        page_number = int(figure.get("page_number") or (caption_block or {}).get("page_number") or 1)
        reading_order = int(
            figure.get("reading_order")
            or (caption_block or {}).get("reading_order")
            or (figure_order_base + fig_idx)
        )
        display_text = caption_text or figure_ref
        retrieval_parts = [f"[Figure: {figure_ref}]"]
        if caption_text:
            retrieval_parts.append(caption_text)
        if figure.get("nearby_text"):
            retrieval_parts.append(str(figure.get("nearby_text")).strip())
        retrieval_text = " ".join(part for part in retrieval_parts if part).strip()
        chunks.append(
            RetrievalChunk(
                chunk_id=f"chunk_figure_{_safe_filename(figure_ref, max_len=40)}_{fig_idx}",
                source_block_id=str(caption_block_id or figure_ref or fig_idx),
                chunk_type="figure",
                page_number=page_number,
                reading_order=reading_order,
                display_text=display_text or retrieval_text,
                retrieval_text=retrieval_text or display_text,
                bbox=figure.get("bbox"),
                provenance=str(figure.get("provenance") or "figure"),
                section_context=str(figure.get("section_context") or "") or None,
                is_neighbor=False,
                figure_ref=figure_ref or None,
                caption_text=caption_text or None,
                crop_path=figure.get("crop_path"),
                full_page_path=figure.get("full_page_path"),
            )
        )

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


def _build_retrieval_query_policy(column_name: str, column_description: str) -> RetrievalPolicy:
    combined = f"{column_name} {column_description}".lower()
    hints: list[str] = []
    heuristic_tags: list[str] = []

    if _COUNT_LIKE_PATTERN.search(combined):
        heuristic_tags.append("count_like")
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
        heuristic_tags.append("variant_or_sequence")
        hints.extend([
            "sequences",
            "pairs",
            "combinations",
            "plasmids",
            "barcodes",
        ])

    if re.search(r"\b(episomal|ori|origin of replication|backbone|vector)\b", combined):
        heuristic_tags.append("vector_or_backbone")
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
        heuristic_tags.append("methods_or_library")
        hints.extend([
            "methods",
            "design",
            "library",
            "cloning",
            "construct",
        ])

    hint_terms = _unique_terms(hints)
    return RetrievalPolicy(
        query_mode="lexical_with_hints" if hint_terms else "lexical",
        heuristic_tags=heuristic_tags,
        hint_terms=hint_terms,
    )


def build_retrieval_query(column_name: str, column_description: str) -> str:
    """Build a retrieval query with light field-aware expansion.

    The expansion is intentionally lexical and conservative. It helps columns whose
    user-facing wording does not closely match how papers describe the answer.
    """
    base_query = f"{column_name}: {column_description}".strip()
    hint_terms = _build_retrieval_query_policy(column_name, column_description).hint_terms
    if not hint_terms:
        return base_query

    return f"{base_query}\nRetrieval hints: {' '.join(hint_terms)}"


def _build_retrieval_query_with_policy(
    column_name: str,
    column_description: str,
) -> tuple[str, RetrievalPolicy]:
    policy = _build_retrieval_query_policy(column_name, column_description)
    query = build_retrieval_query(column_name, column_description)
    return query, policy


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


def _coverage_score(query_terms: list[str], chunk_text: str) -> float:
    if not query_terms:
        return 0.0
    query_vocab = set(query_terms)
    chunk_vocab = set(_tokenize(chunk_text))
    if not chunk_vocab:
        return 0.0
    return len(query_vocab & chunk_vocab) / len(query_vocab)


def _score_chunks_with_metadata(
    query: str,
    chunks: list[RetrievalChunk],
    retrieval_mode: str = "lexical",
    *,
    precomputed_idf: dict[str, float] | None = None,
    precomputed_avgdl: float | None = None,
) -> tuple[list[tuple[float, RetrievalChunk]], dict[str, float]]:
    if not chunks:
        return [], {"idf_build_ms": 0.0, "scoring_ms": 0.0}

    if retrieval_mode not in SUPPORTED_RETRIEVAL_MODES:
        retrieval_mode = "lexical"

    query_terms = _tokenize(query)
    if not query_terms:
        return [(0.0, c) for c in chunks], {"idf_build_ms": 0.0, "scoring_ms": 0.0}

    if precomputed_idf is None:
        idf_started = perf_counter()
        idf = _build_idf(chunks)
        idf_build_ms = (perf_counter() - idf_started) * 1000.0
    else:
        idf = precomputed_idf
        idf_build_ms = 0.0

    if precomputed_avgdl is None:
        total_len = sum(len(_tokenize(c.retrieval_text)) for c in chunks)
        avgdl = total_len / len(chunks) if chunks else 100.0
    else:
        avgdl = precomputed_avgdl

    scoring_started = perf_counter()
    base_scores = [
        (_bm25_score(query_terms, c.retrieval_text, idf, avgdl=avgdl), c)
        for c in chunks
    ]
    if retrieval_mode == "hybrid_experimental":
        max_bm25 = max((score for score, _ in base_scores), default=0.0)
        scored = []
        for bm25_score, chunk in base_scores:
            bm25_component = (bm25_score / max_bm25) if max_bm25 > 0 else 0.0
            coverage_component = _coverage_score(query_terms, chunk.retrieval_text)
            scored.append(((bm25_component * 0.7) + (coverage_component * 0.3), chunk))
    else:
        scored = base_scores

    scored.sort(key=lambda x: -x[0])
    scoring_ms = (perf_counter() - scoring_started) * 1000.0
    return scored, {
        "idf_build_ms": round(idf_build_ms, 3),
        "scoring_ms": round(scoring_ms, 3),
    }


def score_chunks(
    query: str,
    chunks: list[RetrievalChunk],
    retrieval_mode: str = "lexical",
) -> list[tuple[float, RetrievalChunk]]:
    """Score chunks against a query using the configured retrieval mode."""
    scored, _metadata = _score_chunks_with_metadata(query, chunks, retrieval_mode=retrieval_mode)
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

def _retrieve_with_metadata(
    query: str,
    doc_dict: dict,
    top_k: int = 6,
    include_captions: bool = True,
    include_tables: bool = True,
    include_neighbor_window: bool = True,
    retrieval_mode: str = "lexical",
    prepared_index: RetrievalPreparedIndex | None = None,
    used_cached_index: bool = False,
) -> tuple[list[RetrievalChunk], RetrievalStats]:
    """Retrieve top-k relevant chunks from a ParsedDocument dict with stats.

    T047:
    - top_k = 6 default
    - captions and tables included when relevant
    - one neighbor window added per selected chunk
    - NO reranking, HyDE, or query expansion in MVP baseline
    """
    total_started = perf_counter()
    if prepared_index is None:
        chunk_started = perf_counter()
        all_chunks = build_chunks_from_parsed_doc(doc_dict)
        chunk_build_ms = (perf_counter() - chunk_started) * 1000.0
    else:
        all_chunks = prepared_index.all_chunks
        chunk_build_ms = 0.0
    if not all_chunks:
        return [], RetrievalStats(chunk_build_ms=round(chunk_build_ms, 3), total_ms=round((perf_counter() - total_started) * 1000.0, 3))

    if prepared_index is None:
        chunk_count_by_type: dict[str, int] = {}
        for chunk in all_chunks:
            chunk_count_by_type[chunk.chunk_type] = chunk_count_by_type.get(chunk.chunk_type, 0) + 1

        allowed_types = {"paragraph", "section", "abstract", "list_item", "figure"}
        if include_captions:
            allowed_types.add("caption")
        if include_tables:
            allowed_types.add("table_region")

        candidate_chunks = [c for c in all_chunks if c.chunk_type in allowed_types]
        if not candidate_chunks:
            candidate_chunks = all_chunks
        idf = _build_idf(candidate_chunks)
        total_len = sum(len(_tokenize(c.retrieval_text)) for c in candidate_chunks)
        avgdl = total_len / len(candidate_chunks) if candidate_chunks else 100.0
    else:
        chunk_count_by_type = dict(prepared_index.chunk_count_by_type)
        candidate_chunks = prepared_index.candidate_chunks or prepared_index.all_chunks
        idf = prepared_index.idf
        avgdl = prepared_index.avgdl

    scored, scoring_meta = _score_chunks_with_metadata(
        query,
        candidate_chunks,
        retrieval_mode=retrieval_mode,
        precomputed_idf=idf,
        precomputed_avgdl=avgdl,
    )
    top_chunks = [chunk for _, chunk in scored[:top_k]]
    selected_ids = {c.chunk_id for c in top_chunks}

    if include_neighbor_window:
        result = _add_neighbor_window(selected_ids, all_chunks)
    else:
        result = sorted(top_chunks, key=lambda c: (c.page_number, c.reading_order))

    neighbor_chunk_count = sum(1 for chunk in result if chunk.is_neighbor)
    stats = RetrievalStats(
        chunk_build_ms=round(chunk_build_ms, 3),
        idf_build_ms=scoring_meta["idf_build_ms"],
        scoring_ms=scoring_meta["scoring_ms"],
        total_ms=round((perf_counter() - total_started) * 1000.0, 3),
        chunk_count_total=len(all_chunks),
        chunk_count_by_type=chunk_count_by_type,
        candidate_chunk_count=len(candidate_chunks),
        selected_chunk_count=len(top_chunks),
        neighbor_chunk_count=neighbor_chunk_count,
        chunk_build_count=0 if used_cached_index else 1,
        idf_build_count=0 if used_cached_index else 1,
        cached_index_used=used_cached_index,
    )
    return result, stats


def prepare_retrieval_index(
    doc_dict: dict,
    *,
    include_captions: bool = True,
    include_tables: bool = True,
) -> RetrievalPreparedIndex:
    all_chunks = build_chunks_from_parsed_doc(doc_dict)
    chunk_count_by_type: dict[str, int] = {}
    for chunk in all_chunks:
        chunk_count_by_type[chunk.chunk_type] = chunk_count_by_type.get(chunk.chunk_type, 0) + 1

    allowed_types = {"paragraph", "section", "abstract", "list_item", "figure"}
    if include_captions:
        allowed_types.add("caption")
    if include_tables:
        allowed_types.add("table_region")

    candidate_chunks = [chunk for chunk in all_chunks if chunk.chunk_type in allowed_types]
    if not candidate_chunks:
        candidate_chunks = all_chunks

    idf = _build_idf(candidate_chunks)
    total_len = sum(len(_tokenize(chunk.retrieval_text)) for chunk in candidate_chunks)
    avgdl = total_len / len(candidate_chunks) if candidate_chunks else 100.0
    return RetrievalPreparedIndex(
        all_chunks=all_chunks,
        candidate_chunks=candidate_chunks,
        chunk_count_by_type=chunk_count_by_type,
        avgdl=avgdl,
        idf=idf,
    )


def retrieve(
    query: str,
    doc_dict: dict,
    top_k: int = 6,
    include_captions: bool = True,
    include_tables: bool = True,
    include_neighbor_window: bool = True,
    retrieval_mode: str = "lexical",
) -> list[RetrievalChunk]:
    """Retrieve top-k relevant chunks from a ParsedDocument dict."""
    chunks, _stats = _retrieve_with_metadata(
        query,
        doc_dict,
        top_k=top_k,
        include_captions=include_captions,
        include_tables=include_tables,
        include_neighbor_window=include_neighbor_window,
        retrieval_mode=retrieval_mode,
    )
    return chunks


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
    mode: str = "baseline",
    rescue_reason: Optional[str] = None,
    retrieval_mode: str = "lexical",
    retrieval_cache: dict[tuple[str, str, bool, bool], RetrievalPreparedIndex] | None = None,
    cache_key: str | None = None,
    column_plan: Optional[dict] = None,
) -> RetrievalResult:
    """Build and persist retrieval result for one (pdf, column) pair."""
    query, policy = _build_retrieval_query_with_policy(column_name, column_description)
    prepared_index: RetrievalPreparedIndex | None = None
    include_captions = True
    include_tables = True
    include_neighbor_window = True
    allowed_chunk_types = ["abstract", "caption", "figure", "list_item", "paragraph", "section", "table_region"]
    retrieval_profile = "general"
    retrieval_hints: list[str] = []
    if isinstance(column_plan, dict):
        retrieval_profile = str(column_plan.get("retrieval_profile") or "general")
        raw_hints = column_plan.get("retrieval_hints")
        if isinstance(raw_hints, list):
            retrieval_hints = [str(hint).strip() for hint in raw_hints if str(hint).strip()]
    if retrieval_hints:
        query = f"{query} " + " ".join(retrieval_hints[:12])
        policy.hint_terms = list(dict.fromkeys([*policy.hint_terms, *retrieval_hints[:12]]))
    if retrieval_profile == "metadata":
        include_captions = False
        include_tables = False
        include_neighbor_window = True
        allowed_chunk_types = ["abstract", "paragraph", "section"]
        top_k = min(max(top_k, 4), 7)
    elif retrieval_profile == "methods":
        include_captions = False
        include_tables = True
        include_neighbor_window = True
        allowed_chunk_types = ["abstract", "list_item", "paragraph", "section", "table_region"]
        top_k = max(top_k, 8)
    elif retrieval_profile == "visual":
        include_captions = True
        include_tables = True
        include_neighbor_window = True
        allowed_chunk_types = ["caption", "figure", "paragraph", "section", "table_region"]
        top_k = max(top_k, 10)
    elif retrieval_profile == "claims":
        include_captions = False
        include_tables = False
        include_neighbor_window = True
        allowed_chunk_types = ["abstract", "paragraph", "section"]
        top_k = max(top_k, 8)
    elif retrieval_profile == "results":
        include_captions = True
        include_tables = True
        include_neighbor_window = True
        allowed_chunk_types = ["caption", "paragraph", "section", "table_region"]
        top_k = max(top_k, 8)
    if retrieval_cache is not None and cache_key is not None:
        cache_tuple = (cache_key, retrieval_mode, include_captions, include_tables)
        prepared_index = retrieval_cache.get(cache_tuple)
        used_cached_index = prepared_index is not None
        if prepared_index is None:
            prepared_index = prepare_retrieval_index(
                doc_dict,
                include_captions=include_captions,
                include_tables=include_tables,
            )
            retrieval_cache[cache_tuple] = prepared_index
    else:
        used_cached_index = False

    chunks, stats = _retrieve_with_metadata(
        query,
        doc_dict,
        top_k=top_k,
        include_captions=include_captions,
        include_tables=include_tables,
        include_neighbor_window=include_neighbor_window,
        retrieval_mode=retrieval_mode,
        prepared_index=prepared_index,
        used_cached_index=used_cached_index,
    )
    scoring_profile = "bm25_plus_token_coverage" if retrieval_mode == "hybrid_experimental" else "bm25_lite"
    policy = policy.model_copy(
        update={
            "scoring_profile": scoring_profile,
            "allowed_chunk_types": allowed_chunk_types,
            "include_captions": include_captions,
            "include_tables": include_tables,
            "include_neighbor_window": include_neighbor_window,
            "top_k": top_k,
            "retrieval_profile": retrieval_profile,
        }
    )
    result = RetrievalResult(
        run_id=run_id,
        pdf_id=pdf_id,
        column_name=column_name,
        query=query,
        top_k=top_k,
        chunks=chunks,
        mode=retrieval_mode,
        request_mode=mode,
        policy=policy.model_dump(),
        stats=stats.model_dump(),
        rescue_reason=rescue_reason,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_retrieval_result(run_dir, result)
    return result
