"""Batch 2: PDF-to-row matching with deterministic scoring and blocked-match outcomes.

T033 – Grounded paper-metadata extraction from ParsedDocument
T034 – Deterministic matching scoring
T035 – Limited fallback adjudication for plausible ambiguous cases
T036 – Final match outcome assignment (matched/ambiguous/unmatched/duplicate_row_conflict)
T037 – Duplicate-row conflict detection
T038 – Matching artifact persistence and reasoning summaries
T039 – API helpers for unmatched/ambiguous/conflict records
"""

from __future__ import annotations

import pathlib
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from pydantic import BaseModel

from .artifacts import write_json
from .parsing import _DOI_PATTERN, _YEAR_PATTERN
from .schemas import MatchOutcome


# ---------------------------------------------------------------------------
# PaperMetadata extracted from ParsedDocument (T033)
# ---------------------------------------------------------------------------

class PaperMetadata(BaseModel):
    """Grounded metadata extracted from a ParsedDocument for matching."""
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    abstract_snippet: Optional[str] = None


# ---------------------------------------------------------------------------
# MatchResult (T036)
# ---------------------------------------------------------------------------

class MatchResult(BaseModel):
    """Final match outcome for one PDF."""
    pdf_id: str
    pdf_path: str
    outcome: MatchOutcome
    matched_row_index: Optional[int] = None
    matched_row_title: Optional[str] = None
    score: float
    runner_up_score: float
    runner_up_row_index: Optional[int] = None
    conflict_pdf_ids: list[str] = []
    conflict_row_indices: list[int] = []
    reasoning: str
    blocked: bool            # True when extraction must be blocked
    blocked_reason: Optional[str] = None
    matched_at: str


class MatchSummary(BaseModel):
    """Aggregate match summary across all PDFs in a run."""
    run_id: str
    total_pdfs: int
    matched: int
    ambiguous: int
    unmatched: int
    duplicate_row_conflict: int
    generated_at: str


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Normalize text for matching: lowercase, strip diacritics, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _title_jaccard(t1: str, t2: str) -> float:
    """Jaccard similarity between normalized title word sets."""
    words1 = set(_norm(t1).split())
    words2 = set(_norm(t2).split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)


def _author_overlap(paper_authors: list[str], row_authors_str: str) -> float:
    """Fraction of paper last-names found in the row's author string."""
    if not paper_authors or not row_authors_str.strip():
        return 0.0

    paper_lastnames = set()
    for a in paper_authors:
        lastname = _extract_first_author_lastname(a)
        if lastname:
            paper_lastnames.add(lastname)

    row_lastnames = set()
    for a in re.split(r";|\band\b", row_authors_str, flags=re.IGNORECASE):
        a = a.strip()
        if a:
            lastname = _extract_first_author_lastname(a)
            if lastname:
                row_lastnames.add(lastname)

    if not paper_lastnames or not row_lastnames:
        return 0.0

    matches = paper_lastnames & row_lastnames
    return len(matches) / len(paper_lastnames)


def _normalize_doi(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    return text.rstrip(".")


def _extract_row_doi(row: dict) -> Optional[str]:
    for key in ("DOI", "Doi", "doi"):
        value = str(row.get(key, "") or "").strip()
        if value:
            return value
    return None


def _doi_match_score(left: str, right: str) -> float:
    return 1.0 if _normalize_doi(left) == _normalize_doi(right) else 0.0


def _extract_first_author_lastname(author_value: str) -> Optional[str]:
    text = author_value.strip()
    if not text:
        return None
    first_author = re.split(r";|\band\b", text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if "," in first_author:
        token = first_author.split(",", 1)[0]
    else:
        token = first_author.split()[-1]
    normalized = _norm(token)
    return normalized or None


def _first_author_match(paper_authors: list[str], row_authors_str: str) -> bool:
    if not paper_authors or not row_authors_str.strip():
        return False
    paper_first = _extract_first_author_lastname(paper_authors[0])
    row_first = _extract_first_author_lastname(row_authors_str)
    return bool(paper_first and row_first and paper_first == row_first)


# ---------------------------------------------------------------------------
# Metadata extraction from ParsedDocument (T033)
# ---------------------------------------------------------------------------

def extract_paper_metadata(doc_dict: dict) -> PaperMetadata:
    """Extract grounded matching metadata from a ParsedDocument dict (T033).

    Uses:
    1. Structured metadata fields when present (from docling or PDF header)
    2. Text-based heuristics as fallback

    Grounded means: derived from the actual parsed document content, not
    from table expectations.
    """
    meta = doc_dict.get("metadata", {})

    title: Optional[str] = meta.get("title") or None
    year: Optional[int] = meta.get("year") or None
    doi: Optional[str] = meta.get("doi") or None
    abstract_snippet: Optional[str] = None

    # Authors: may be list or None
    raw_authors = meta.get("authors")
    authors: Optional[list[str]] = raw_authors if raw_authors else None

    full_text: str = doc_dict.get("full_text", "")

    # --- Title fallback: extract from blocks ---
    if not title and full_text:
        title = _extract_title_from_text(full_text, doc_dict.get("blocks", []))

    # --- Year fallback ---
    if not year and full_text:
        year = _extract_year_from_text(full_text)

    # --- DOI fallback ---
    if not doi and full_text:
        doi_match = _DOI_PATTERN.search(full_text)
        if doi_match:
            doi = doi_match.group(1).rstrip(".")

    # --- Abstract snippet ---
    for block in doc_dict.get("blocks", []):
        if block.get("block_type") in ("abstract", "paragraph"):
            text = block.get("text", "")
            if len(text) > 100:
                abstract_snippet = text[:500]
                break

    return PaperMetadata(
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        abstract_snippet=abstract_snippet,
    )


def _extract_title_from_text(full_text: str, blocks: list[dict]) -> Optional[str]:
    """Extract title heuristically from text blocks."""
    # Prefer first heading/section_heading/abstract block on page 1-2
    for block in blocks:
        if block.get("page_number", 99) > 2:
            break
        btype = block.get("block_type", "")
        text = block.get("text", "").strip()
        if btype in ("heading", "section_heading") and 15 < len(text) < 300:
            return re.sub(r"\s+", " ", text)

    # Fall back to first substantial line in full_text
    for line in full_text.split("\n"):
        line = line.strip()
        if 20 < len(line) < 300:
            if not re.search(
                r"vol\.|doi:|journal|article|©|nature|science|published|received",
                line, re.IGNORECASE
            ):
                return re.sub(r"\s+", " ", line)
    return None


def _extract_year_from_text(full_text: str) -> Optional[int]:
    """Extract most-common plausible publication year from text."""
    matches = _YEAR_PATTERN.findall(full_text)
    if not matches:
        return None
    counter = Counter(matches)
    return int(counter.most_common(1)[0][0])


# ---------------------------------------------------------------------------
# Deterministic scoring (T034)
# ---------------------------------------------------------------------------

_DOI_WEIGHT = 0.45
_TITLE_WEIGHT = 0.15
_FIRST_AUTHOR_WEIGHT = 0.15
_AUTHOR_WEIGHT = 0.1
_YEAR_WEIGHT = 0.1
_EXACT_TITLE_BONUS = 0.05


def score_against_row(paper: PaperMetadata, row: dict) -> float:
    """Score a paper's metadata against a single table row (T034).

    Returns a float in [0, 1].
    """
    score = 0.0

    row_title = str(row.get("Title", "") or "").strip()
    row_year = str(row.get("Publication Year", "") or "").strip()
    row_authors = str(row.get("Authors", "") or "").strip()
    row_doi = _extract_row_doi(row)

    if paper.doi and row_doi:
        score += _DOI_WEIGHT * _doi_match_score(paper.doi, row_doi)

    if paper.title and row_title:
        sim = _title_jaccard(paper.title, row_title)
        score += _TITLE_WEIGHT * sim
        if _norm(paper.title) == _norm(row_title):
            score += _EXACT_TITLE_BONUS

    if paper.year and row_year:
        try:
            ry = int(re.sub(r"[^\d]", "", row_year)[:4])
            if ry == paper.year:
                score += _YEAR_WEIGHT
            elif abs(ry - paper.year) == 1:
                # Off-by-one: online-first vs print year is common
                score += _YEAR_WEIGHT * 0.5
        except (ValueError, TypeError):
            pass

    if paper.authors and row_authors:
        if _first_author_match(paper.authors, row_authors):
            score += _FIRST_AUTHOR_WEIGHT
        overlap = _author_overlap(paper.authors, row_authors)
        score += _AUTHOR_WEIGHT * overlap

    return round(min(score, 1.0), 6)


def score_all_rows(paper: PaperMetadata, df: pd.DataFrame) -> list[tuple[int, float]]:
    """Score a paper against all rows in the table.

    Returns:
        List of (row_index, score) sorted descending by score.
    """
    results = []
    rows = df.to_dict("records")
    for i, row in enumerate(rows):
        s = score_against_row(paper, row)
        results.append((i, s))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Match outcome assignment (T035, T036)
# ---------------------------------------------------------------------------

# Thresholds — tuned for identifier/author/year-first matching
_MATCH_THRESHOLD = 0.35
_AMBIGUITY_GAP_MIN = 0.15     # runner-up must be at least this far below top to be "matched"


def assign_match_outcome(
    pdf_id: str,
    pdf_path: str,
    paper: PaperMetadata,
    scored_rows: list[tuple[int, float]],
    df: pd.DataFrame,
    ambiguity_threshold: float = _AMBIGUITY_GAP_MIN,
) -> MatchResult:
    """Assign a match outcome for one PDF (T035, T036).

    Args:
        pdf_id: PDF identifier.
        pdf_path: Path to the PDF file.
        paper: Extracted paper metadata.
        scored_rows: List of (row_index, score) sorted descending.
        df: The full table DataFrame.
        ambiguity_threshold: Minimum gap between top and runner-up to be "matched".

    Returns:
        MatchResult with outcome, matched row, scores, reasoning, and blocked flag.
    """
    now = datetime.now(timezone.utc).isoformat()

    if not scored_rows:
        return MatchResult(
            pdf_id=pdf_id,
            pdf_path=pdf_path,
            outcome=MatchOutcome.unmatched,
            score=0.0,
            runner_up_score=0.0,
            reasoning="No rows in table to match against.",
            blocked=True,
            blocked_reason="unmatched: no rows in table",
            matched_at=now,
        )

    top_idx, top_score = scored_rows[0]
    runner_up_idx: Optional[int] = None
    runner_up_score = 0.0
    if len(scored_rows) > 1:
        runner_up_idx, runner_up_score = scored_rows[1]

    top_row = df.iloc[top_idx].to_dict()
    top_row_title = str(top_row.get("Title", "") or "")

    # --- Unmatched: top score below threshold ---
    if top_score < _MATCH_THRESHOLD:
        return MatchResult(
            pdf_id=pdf_id,
            pdf_path=pdf_path,
            outcome=MatchOutcome.unmatched,
            score=top_score,
            runner_up_score=runner_up_score,
            runner_up_row_index=runner_up_idx,
            reasoning=(
                f"Best score {top_score:.3f} below threshold {_MATCH_THRESHOLD}. "
                f"No table row sufficiently similar to paper title: '{paper.title}'"
            ),
            blocked=True,
            blocked_reason=f"unmatched: best score {top_score:.3f} < {_MATCH_THRESHOLD}",
            matched_at=now,
        )

    # --- Ambiguous: runner-up too close ---
    gap = top_score - runner_up_score
    if gap < ambiguity_threshold:
        # Limited fallback adjudication (T035): check if runner-up is a near-duplicate row
        # (same title + year in the table). If so, we can still pick the top row.
        is_duplicate_row = _are_rows_near_duplicate(
            df.iloc[top_idx].to_dict() if top_idx < len(df) else {},
            df.iloc[runner_up_idx].to_dict() if runner_up_idx is not None and runner_up_idx < len(df) else {},
        )

        if not is_duplicate_row:
            return MatchResult(
                pdf_id=pdf_id,
                pdf_path=pdf_path,
                outcome=MatchOutcome.ambiguous,
                score=top_score,
                runner_up_score=runner_up_score,
                runner_up_row_index=runner_up_idx,
                matched_row_index=top_idx,
                matched_row_title=top_row_title,
                reasoning=(
                    f"Top score {top_score:.3f} vs runner-up {runner_up_score:.3f} "
                    f"(gap {gap:.3f} < {ambiguity_threshold}). "
                    f"Cannot deterministically choose between row {top_idx} and {runner_up_idx}."
                ),
                blocked=True,
                blocked_reason=(
                    f"ambiguous: gap {gap:.3f} between row {top_idx} "
                    f"(score {top_score:.3f}) and row {runner_up_idx} "
                    f"(score {runner_up_score:.3f}) is below {ambiguity_threshold}"
                ),
                matched_at=now,
            )
        else:
            # Adjudication: runner-up is a near-duplicate table row — pick top row and note it
            return MatchResult(
                pdf_id=pdf_id,
                pdf_path=pdf_path,
                outcome=MatchOutcome.matched,
                score=top_score,
                runner_up_score=runner_up_score,
                runner_up_row_index=runner_up_idx,
                matched_row_index=top_idx,
                matched_row_title=top_row_title,
                reasoning=(
                    f"Top score {top_score:.3f}; runner-up row {runner_up_idx} is a near-duplicate "
                    f"table entry (same title/year). Adjudicated to row {top_idx}. "
                    f"Note: table contains duplicate rows — consider deduplication."
                ),
                blocked=False,
                blocked_reason=None,
                matched_at=now,
            )

    # --- Matched: clear winner ---
    return MatchResult(
        pdf_id=pdf_id,
        pdf_path=pdf_path,
        outcome=MatchOutcome.matched,
        score=top_score,
        runner_up_score=runner_up_score,
        runner_up_row_index=runner_up_idx,
        matched_row_index=top_idx,
        matched_row_title=top_row_title,
        reasoning=(
            f"Clear match: score {top_score:.3f} vs runner-up {runner_up_score:.3f} "
            f"(gap {gap:.3f} >= {ambiguity_threshold}). "
            f"Matched to row {top_idx}: '{top_row_title[:60]}'"
        ),
        blocked=False,
        blocked_reason=None,
        matched_at=now,
    )


def _are_rows_near_duplicate(row_a: dict, row_b: dict) -> bool:
    """Return True if two table rows describe the same paper (title + year near-match)."""
    if not row_a or not row_b:
        return False
    title_a = str(row_a.get("Title", "") or "")
    title_b = str(row_b.get("Title", "") or "")
    year_a = str(row_a.get("Publication Year", "") or "").strip()
    year_b = str(row_b.get("Publication Year", "") or "").strip()

    title_sim = _title_jaccard(title_a, title_b)
    year_match = year_a == year_b and bool(year_a)

    # Near-duplicate: high title similarity + same year
    return title_sim >= 0.85 and year_match


# ---------------------------------------------------------------------------
# Duplicate-row conflict detection (T037)
# ---------------------------------------------------------------------------

def detect_duplicate_row_conflicts(
    results: list[MatchResult],
) -> list[MatchResult]:
    """Re-label PDFs as duplicate_row_conflict when two PDFs claim the same row (T037).

    If two or more different PDFs are matched to the same row_index, ALL of those
    PDFs are relabeled as duplicate_row_conflict and blocked.

    Returns:
        Updated list of MatchResults.
    """
    # Build map from row_index -> list of matched PDFs
    row_to_pdfs: dict[int, list[int]] = {}
    for i, r in enumerate(results):
        if r.outcome == MatchOutcome.matched and r.matched_row_index is not None:
            row_to_pdfs.setdefault(r.matched_row_index, []).append(i)

    # Find conflicting rows (more than one PDF claims the same row)
    conflicting_rows: set[int] = {
        row_idx
        for row_idx, pdf_indices in row_to_pdfs.items()
        if len(pdf_indices) > 1
    }

    if not conflicting_rows:
        return results

    updated = list(results)
    for i, result in enumerate(updated):
        if (
            result.outcome == MatchOutcome.matched
            and result.matched_row_index in conflicting_rows
        ):
            conflicting_pdf_count = len(row_to_pdfs[result.matched_row_index])
            conflict_pdf_ids = [
                updated[pdf_idx].pdf_id
                for pdf_idx in row_to_pdfs[result.matched_row_index]
            ]
            updated[i] = result.model_copy(update={
                "outcome": MatchOutcome.duplicate_row_conflict,
                "blocked": True,
                "conflict_pdf_ids": conflict_pdf_ids,
                "conflict_row_indices": [result.matched_row_index],
                "blocked_reason": (
                    f"duplicate_row_conflict: {conflicting_pdf_count} PDFs "
                    f"all matched to row {result.matched_row_index} "
                    f"('{str(result.matched_row_title or '')[:50]}')"
                ),
                "reasoning": result.reasoning + (
                    f" [CONFLICT: row {result.matched_row_index} was claimed by PDFs "
                    f"{', '.join(conflict_pdf_ids)}; extraction blocked for all]"
                ),
            })

    return updated


# ---------------------------------------------------------------------------
# Run matching across all PDFs (T033–T037)
# ---------------------------------------------------------------------------

def run_matching(
    pdf_docs: list[dict],
    df: pd.DataFrame,
    ambiguity_threshold: float = _AMBIGUITY_GAP_MIN,
) -> list[MatchResult]:
    """Run the full matching pipeline for all PDFs in a run.

    Args:
        pdf_docs: List of ParsedDocument dicts (from parsed_document.json artifacts).
        df: The table DataFrame.
        ambiguity_threshold: Minimum score gap to confirm a match.

    Returns:
        List of MatchResult, one per PDF, with duplicate-row conflicts resolved.
    """
    results: list[MatchResult] = []

    for doc_dict in pdf_docs:
        pdf_id = doc_dict.get("pdf_id", "unknown")
        pdf_path = doc_dict.get("pdf_path", "")

        paper = extract_paper_metadata(doc_dict)
        scored_rows = score_all_rows(paper, df)
        result = assign_match_outcome(
            pdf_id=pdf_id,
            pdf_path=pdf_path,
            paper=paper,
            scored_rows=scored_rows,
            df=df,
            ambiguity_threshold=ambiguity_threshold,
        )
        results.append(result)

    # Detect cross-PDF conflicts (T037)
    results = detect_duplicate_row_conflicts(results)

    return results


# ---------------------------------------------------------------------------
# Artifact persistence (T038)
# ---------------------------------------------------------------------------

def get_matching_dir(run_dir: pathlib.Path) -> pathlib.Path:
    return run_dir / "matching"


def persist_match_artifacts(
    run_dir: pathlib.Path,
    run_id: str,
    results: list[MatchResult],
) -> None:
    """Store matching artifacts and reasoning summaries (T038).

    Layout:
        {run_dir}/matching/
            match_results.json        – all MatchResult records
            match_summary.json        – aggregate counts + lists
            unmatched.json            – unmatched PDF IDs and reasoning
            ambiguous.json            – ambiguous PDF IDs and reasoning
            conflicts.json            – duplicate_row_conflict IDs and reasoning
    """
    matching_dir = get_matching_dir(run_dir)
    matching_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    # All results
    write_json(
        matching_dir / "match_results.json",
        [r.model_dump() for r in results],
    )

    # Partition by outcome
    matched = [r for r in results if r.outcome == MatchOutcome.matched]
    ambiguous = [r for r in results if r.outcome == MatchOutcome.ambiguous]
    unmatched = [r for r in results if r.outcome == MatchOutcome.unmatched]
    conflicts = [r for r in results if r.outcome == MatchOutcome.duplicate_row_conflict]

    # Summary
    summary = MatchSummary(
        run_id=run_id,
        total_pdfs=len(results),
        matched=len(matched),
        ambiguous=len(ambiguous),
        unmatched=len(unmatched),
        duplicate_row_conflict=len(conflicts),
        generated_at=now,
    )
    write_json(matching_dir / "match_summary.json", summary.model_dump())

    # Inspectable blocked lists (T038: inspectable rather than silently leaking)
    write_json(
        matching_dir / "unmatched.json",
        [
            {
                "pdf_id": r.pdf_id,
                "pdf_path": r.pdf_path,
                "score": r.score,
                "reasoning": r.reasoning,
                "blocked_reason": r.blocked_reason,
            }
            for r in unmatched
        ],
    )
    write_json(
        matching_dir / "ambiguous.json",
        [
            {
                "pdf_id": r.pdf_id,
                "pdf_path": r.pdf_path,
                "score": r.score,
                "runner_up_score": r.runner_up_score,
                "matched_row_index": r.matched_row_index,
                "runner_up_row_index": r.runner_up_row_index,
                "reasoning": r.reasoning,
                "blocked_reason": r.blocked_reason,
            }
            for r in ambiguous
        ],
    )
    write_json(
        matching_dir / "conflicts.json",
        [
            {
                "pdf_id": r.pdf_id,
                "pdf_path": r.pdf_path,
                "matched_row_index": r.matched_row_index,
                "matched_row_title": r.matched_row_title,
                "conflict_pdf_ids": r.conflict_pdf_ids,
                "conflict_row_indices": r.conflict_row_indices,
                "score": r.score,
                "reasoning": r.reasoning,
                "blocked_reason": r.blocked_reason,
            }
            for r in conflicts
        ],
    )


# ---------------------------------------------------------------------------
# API helpers (T039)
# ---------------------------------------------------------------------------

def load_match_results(run_dir: pathlib.Path) -> list[dict]:
    """Load all match results from the artifact bundle."""
    path = get_matching_dir(run_dir) / "match_results.json"
    if not path.exists():
        return []
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_match_summary(run_dir: pathlib.Path) -> Optional[dict]:
    """Load the match summary from the artifact bundle."""
    path = get_matching_dir(run_dir) / "match_summary.json"
    if not path.exists():
        return None
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_unmatched(run_dir: pathlib.Path) -> list[dict]:
    path = get_matching_dir(run_dir) / "unmatched.json"
    if not path.exists():
        return []
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_ambiguous(run_dir: pathlib.Path) -> list[dict]:
    path = get_matching_dir(run_dir) / "ambiguous.json"
    if not path.exists():
        return []
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_conflicts(run_dir: pathlib.Path) -> list[dict]:
    path = get_matching_dir(run_dir) / "conflicts.json"
    if not path.exists():
        return []
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)
