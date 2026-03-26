"""
Batch 2 — PDF-to-row matching.

Implements:
- T033: Grounded paper-metadata extraction from ParsedDocument
- T034: Deterministic matching scoring (title similarity, author overlap, year)
- T035: Limited fallback adjudication for ambiguous cases
- T036: Final match outcome assignment (matched / ambiguous / unmatched / duplicate_row_conflict)
- T037: Duplicate-row conflict detection + extraction blocking
- T038: Persist matching artifacts and reasoning summaries
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .parsing import ExtractedMetadata, ParsedDocument
from .schemas import MatchOutcome

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# T033 — Grounded paper-metadata extraction
# ---------------------------------------------------------------------------

# Patterns for DOI and arXiv
_DOI_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def extract_paper_metadata(doc: ParsedDocument) -> ExtractedMetadata:
    """
    Extract grounded paper-level metadata from a ParsedDocument (T033).

    Pulls title, authors, publication year, DOI, and arXiv ID from the
    document's existing metadata field and from the earliest blocks.

    Does not hallucinate: only returns values actually found in the document.
    """
    meta = doc.metadata

    # Best-effort: if Docling already found a title, use it
    title = meta.title
    authors = list(meta.authors)
    year = meta.publication_year
    doi = meta.doi
    arxiv_id = meta.arxiv_id

    # Look through early pages (first 2 pages of blocks) for additional signals
    early_blocks = [b for b in doc.blocks if b.page_no <= 2]

    # Try to find DOI or arXiv from text if not already present
    if not doi or not arxiv_id:
        for block in early_blocks:
            text = block.text
            if not doi:
                m = _DOI_RE.search(text)
                if m:
                    doi = m.group(0).rstrip(".,;)")
            if not arxiv_id:
                m = _ARXIV_RE.search(text)
                if m:
                    arxiv_id = m.group(1)

    # Try to find year from early blocks if not found
    if not year:
        for block in early_blocks:
            m = _YEAR_RE.search(block.text)
            if m:
                candidate = int(m.group(0))
                if 1900 <= candidate <= 2100:
                    year = candidate
                    break

    return ExtractedMetadata(
        title=title,
        authors=authors,
        publication_year=year,
        doi=doi,
        arxiv_id=arxiv_id,
        abstract=meta.abstract,
    )


# ---------------------------------------------------------------------------
# T034 — Deterministic matching scoring
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Lowercase, remove punctuation/stopwords for robust title comparison."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _title_similarity(a: str, b: str) -> float:
    """Return a [0, 1] similarity score between two normalized titles."""
    if not a or not b:
        return 0.0
    a_norm = _normalize_title(a)
    b_norm = _normalize_title(b)
    if a_norm == b_norm:
        return 1.0
    # Token-based Jaccard similarity
    a_tokens = set(a_norm.split())
    b_tokens = set(b_norm.split())
    if not a_tokens or not b_tokens:
        return 0.0
    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return intersection / union


def _normalize_author(name: str) -> str:
    """Normalize an author name to 'lastname' for robust overlap computation."""
    parts = re.split(r"[,\s]+", name.lower().strip())
    return parts[0] if parts else name.lower().strip()


def _author_overlap(pdf_authors: list[str], row_authors_raw: str) -> float:
    """Return [0, 1] author overlap ratio between PDF authors and a row's Authors string."""
    if not pdf_authors or not row_authors_raw:
        return 0.0
    # Row authors may be separated by ; or ,
    separators = re.split(r"[;,&]", row_authors_raw)
    row_names = [_normalize_author(s) for s in separators if s.strip()]
    pdf_names = [_normalize_author(a) for a in pdf_authors if a.strip()]
    if not pdf_names or not row_names:
        return 0.0
    matches = sum(1 for p in pdf_names if any(p in r or r in p for r in row_names))
    return matches / max(len(pdf_names), len(row_names))


def _year_match(pdf_year: int | None, row_year_raw: Any) -> float:
    """Return 1.0 if years match (with ±1 tolerance), 0.0 if neither is available."""
    if pdf_year is None:
        return 0.0
    try:
        row_year = int(str(row_year_raw).strip().split(".")[0])
    except (ValueError, TypeError):
        return 0.0
    if row_year == pdf_year:
        return 1.0
    if abs(row_year - pdf_year) == 1:
        return 0.5
    return 0.0


def _identifier_match(meta: ExtractedMetadata, row: dict[str, Any]) -> float:
    """Return 1.0 if a DOI or arXiv ID matches a value in the row, else 0."""
    if not meta.doi and not meta.arxiv_id:
        return 0.0
    row_values = " ".join(str(v) for v in row.values() if v).lower()
    if meta.doi and meta.doi.lower() in row_values:
        return 1.0
    if meta.arxiv_id and meta.arxiv_id.lower() in row_values:
        return 1.0
    return 0.0


# Score thresholds
MATCH_THRESHOLD = 0.70     # score >= this → matched
AMBIGUOUS_THRESHOLD = 0.40  # score in [ambiguous, match) → potentially ambiguous
TITLE_WEIGHT = 0.60
AUTHOR_WEIGHT = 0.25
YEAR_WEIGHT = 0.10
IDENTIFIER_WEIGHT = 0.30   # applied on top if identifier found, can lift score past threshold


def score_pdf_against_row(
    meta: ExtractedMetadata,
    row: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """
    Compute a deterministic match score between PDF metadata and a table row.

    Returns (total_score, component_scores).
    """
    title_score = _title_similarity(meta.title or "", str(row.get("Title") or ""))
    author_score = _author_overlap(meta.authors, str(row.get("Authors") or ""))
    year_score = _year_match(meta.publication_year, row.get("Publication Year"))
    id_score = _identifier_match(meta, row)

    # Identifier match can confidently override low title/author scores
    total = (
        title_score * TITLE_WEIGHT
        + author_score * AUTHOR_WEIGHT
        + year_score * YEAR_WEIGHT
        + id_score * IDENTIFIER_WEIGHT
    )
    # Normalize to [0, 1]
    total = min(total, 1.0)

    components = {
        "title": title_score,
        "authors": author_score,
        "year": year_score,
        "identifier": id_score,
    }
    return total, components


# ---------------------------------------------------------------------------
# T035 — Limited fallback adjudication for ambiguous cases
# ---------------------------------------------------------------------------

def _adjudicate_ambiguous(
    candidates: list[tuple[str, float, dict[str, float]]],
    meta: ExtractedMetadata,
) -> list[tuple[str, float, dict[str, float]]]:
    """
    Apply limited deterministic adjudication for plausible ambiguous cases.

    Rules:
    1. If one candidate has a title similarity >= 0.9, prefer it
    2. If one candidate matches by identifier, prefer it
    3. Otherwise leave ambiguous
    """
    # Prefer identifier match
    id_winners = [(row_id, score, comps) for row_id, score, comps in candidates if comps.get("identifier", 0) > 0.0]
    if len(id_winners) == 1:
        return id_winners

    # Prefer high title similarity
    high_title = [(row_id, score, comps) for row_id, score, comps in candidates if comps.get("title", 0) >= 0.90]
    if len(high_title) == 1:
        return high_title

    return candidates  # remain ambiguous


# ---------------------------------------------------------------------------
# MatchResult and core matching function (T036, T037)
# ---------------------------------------------------------------------------

class MatchResult(BaseModel):
    """Matching outcome for one PDF."""
    pdf_id: str
    outcome: MatchOutcome
    matched_row_id: str | None = None
    top_score: float = 0.0
    score_components: dict[str, float] = Field(default_factory=dict)
    candidate_scores: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""


def match_pdf_to_rows(
    pdf_id: str,
    meta: ExtractedMetadata,
    table_rows: list[dict[str, Any]],
) -> MatchResult:
    """
    Match one PDF (identified by its extracted metadata) to the most likely table row.

    Returns a MatchResult with outcome + evidence.
    """
    if not meta.title and not meta.authors and not meta.doi and not meta.arxiv_id:
        return MatchResult(
            pdf_id=pdf_id,
            outcome=MatchOutcome.UNMATCHED,
            rationale="PDF yielded no extractable metadata (title, authors, DOI, or arXiv ID) — cannot match",
        )

    scored: list[tuple[str, float, dict[str, float]]] = []
    for row in table_rows:
        row_id = str(row.get("Title") or "")
        if not row_id:
            continue
        score, components = score_pdf_against_row(meta, row)
        scored.append((row_id, score, components))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    candidate_scores = [
        {"row_id": row_id, "score": score, "components": comps}
        for row_id, score, comps in scored
    ]

    if not scored:
        return MatchResult(
            pdf_id=pdf_id,
            outcome=MatchOutcome.UNMATCHED,
            candidate_scores=candidate_scores,
            rationale="No scoreable rows in the table",
        )

    best_row_id, best_score, best_components = scored[0]

    if best_score < AMBIGUOUS_THRESHOLD:
        return MatchResult(
            pdf_id=pdf_id,
            outcome=MatchOutcome.UNMATCHED,
            top_score=best_score,
            candidate_scores=candidate_scores,
            rationale=f"Best score {best_score:.3f} is below the ambiguous threshold ({AMBIGUOUS_THRESHOLD}); no plausible match found",
        )

    if best_score >= MATCH_THRESHOLD:
        return MatchResult(
            pdf_id=pdf_id,
            outcome=MatchOutcome.MATCHED,
            matched_row_id=best_row_id,
            top_score=best_score,
            score_components=best_components,
            candidate_scores=candidate_scores,
            rationale=f"Title/author/year scoring produced confident match (score={best_score:.3f} ≥ {MATCH_THRESHOLD})",
        )

    # Score in ambiguous range — try adjudication
    ambiguous_candidates = [
        (row_id, score, comps)
        for row_id, score, comps in scored
        if score >= AMBIGUOUS_THRESHOLD
    ]

    adjudicated = _adjudicate_ambiguous(ambiguous_candidates, meta)

    if len(adjudicated) == 1:
        adj_row_id, adj_score, adj_comps = adjudicated[0]
        return MatchResult(
            pdf_id=pdf_id,
            outcome=MatchOutcome.MATCHED,
            matched_row_id=adj_row_id,
            top_score=adj_score,
            score_components=adj_comps,
            candidate_scores=candidate_scores,
            rationale=f"Adjudicated ambiguous match to '{adj_row_id}' via identifier or strong title signal (score={adj_score:.3f})",
        )

    return MatchResult(
        pdf_id=pdf_id,
        outcome=MatchOutcome.AMBIGUOUS,
        top_score=best_score,
        candidate_scores=candidate_scores,
        rationale=f"Match score {best_score:.3f} is in the ambiguous range [{AMBIGUOUS_THRESHOLD}, {MATCH_THRESHOLD}) with {len(ambiguous_candidates)} plausible candidate(s); extraction is blocked",
    )


def detect_duplicate_row_conflicts(match_results: list[MatchResult]) -> list[MatchResult]:
    """
    Detect duplicate-row conflicts and update outcomes (T037).

    If two or more PDFs match the same row, all of them are re-labeled
    DUPLICATE_ROW_CONFLICT and their matched_row_id is kept for reference.
    """
    row_to_pdfs: dict[str, list[int]] = {}
    for idx, result in enumerate(match_results):
        if result.outcome == MatchOutcome.MATCHED and result.matched_row_id:
            row_to_pdfs.setdefault(result.matched_row_id, []).append(idx)

    conflict_rows = {row_id for row_id, idxs in row_to_pdfs.items() if len(idxs) > 1}

    updated: list[MatchResult] = []
    for result in match_results:
        if (
            result.outcome == MatchOutcome.MATCHED
            and result.matched_row_id in conflict_rows
        ):
            updated.append(
                result.model_copy(
                    update={
                        "outcome": MatchOutcome.DUPLICATE_ROW_CONFLICT,
                        "rationale": (
                            f"Row '{result.matched_row_id}' is claimed by multiple PDFs; "
                            "extraction blocked until conflict is resolved manually"
                        ),
                    }
                )
            )
        else:
            updated.append(result)

    return updated


# ---------------------------------------------------------------------------
# T038 — Persist matching artifacts and summaries
# ---------------------------------------------------------------------------

class MatchingSummary(BaseModel):
    """Per-run matching outcome summary stored under matching/."""
    run_id: str
    total_pdfs: int
    matched: int
    ambiguous: int
    unmatched: int
    duplicate_row_conflict: int
    results: list[MatchResult] = Field(default_factory=list)


def run_matching_for_run(
    pdf_metas: dict[str, ExtractedMetadata],
    table_rows: list[dict[str, Any]],
    matching_dir: Path,
    run_id: str,
) -> MatchingSummary:
    """
    Run the full matching pipeline for all PDFs in a run (T034–T037).

    1. Score each PDF against each row
    2. Assign match outcomes
    3. Detect duplicate-row conflicts
    4. Persist artifacts (T038)
    5. Return MatchingSummary

    Args:
        pdf_metas: mapping of pdf_id → ExtractedMetadata
        table_rows: list of row dicts from the input table
        matching_dir: run artifact dir / matching/
        run_id: run identifier for summary
    """
    matching_dir.mkdir(parents=True, exist_ok=True)

    # Score and assign initial outcomes
    results: list[MatchResult] = []
    for pdf_id, meta in pdf_metas.items():
        result = match_pdf_to_rows(pdf_id, meta, table_rows)
        results.append(result)

    # Detect duplicate-row conflicts
    results = detect_duplicate_row_conflicts(results)

    # Aggregate counts
    counts = {outcome: 0 for outcome in MatchOutcome}
    for result in results:
        counts[result.outcome] += 1

    summary = MatchingSummary(
        run_id=run_id,
        total_pdfs=len(results),
        matched=counts[MatchOutcome.MATCHED],
        ambiguous=counts[MatchOutcome.AMBIGUOUS],
        unmatched=counts[MatchOutcome.UNMATCHED],
        duplicate_row_conflict=counts[MatchOutcome.DUPLICATE_ROW_CONFLICT],
        results=results,
    )

    # Persist full results JSONL (one record per PDF)
    results_path = matching_dir / "matching_results.jsonl"
    with results_path.open("w", encoding="utf-8") as fh:
        for result in results:
            fh.write(json.dumps(result.model_dump(mode="json"), ensure_ascii=False) + "\n")

    # Persist summary JSON
    summary_path = matching_dir / "matching_summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary.model_dump(mode="json", exclude={"results"}), fh, ensure_ascii=False, indent=2)

    # Persist categorized sub-files for easy inspection
    unresolved = [r for r in results if r.outcome != MatchOutcome.MATCHED]
    unresolved_path = matching_dir / "unresolved.json"
    with unresolved_path.open("w", encoding="utf-8") as fh:
        json.dump(
            [r.model_dump(mode="json") for r in unresolved],
            fh,
            ensure_ascii=False,
            indent=2,
        )

    return summary


def load_matching_summary(matching_dir: Path) -> MatchingSummary | None:
    """Load a persisted matching summary from matching_dir, or return None."""
    summary_path = matching_dir / "matching_summary.json"
    results_path = matching_dir / "matching_results.jsonl"
    if not summary_path.exists():
        return None

    with summary_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    results: list[MatchResult] = []
    if results_path.exists():
        with results_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        results.append(MatchResult.model_validate(json.loads(line)))
                    except Exception:
                        pass

    data["results"] = [r.model_dump(mode="json") for r in results]
    try:
        return MatchingSummary.model_validate(data)
    except Exception:
        return None


def load_unresolved_matches(matching_dir: Path) -> list[dict[str, Any]]:
    """Load the unresolved matches list from artifacts."""
    unresolved_path = matching_dir / "unresolved.json"
    if not unresolved_path.exists():
        return []
    with unresolved_path.open("r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return []
