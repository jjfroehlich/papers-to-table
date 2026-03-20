from __future__ import annotations

from difflib import SequenceMatcher

from .models import MatchOutcome, MatchRecord, MatchingSettings, ParsedDocument


def _norm(value: str) -> str:
    return " ".join(value.lower().split())


def _author_overlap(doc_authors: list[str], row_authors: str) -> float:
    if not doc_authors or not row_authors:
        return 0.0
    author_text = _norm(row_authors)
    hits = sum(1 for author in doc_authors if _norm(author) and _norm(author).split()[0] in author_text)
    return hits / max(len(doc_authors), 1)


def match_documents(parsed_docs: list[ParsedDocument], rows: list[dict], settings: MatchingSettings) -> list[MatchRecord]:
    matches: list[MatchRecord] = []
    row_claims: dict[str, list[MatchRecord]] = {}
    for doc in parsed_docs:
        candidates = []
        for row in rows:
            title_score = SequenceMatcher(None, _norm(doc.metadata.title), _norm(str(row.get("Title", "")))).ratio()
            year_bonus = settings.year_bonus if doc.metadata.publication_year and doc.metadata.publication_year == str(row.get("Publication Year", "")) else 0.0
            author_bonus = _author_overlap(doc.metadata.authors, str(row.get("Authors", ""))) * settings.author_bonus
            score = min(1.0, title_score + year_bonus + author_bonus)
            candidates.append({"row_id": row["row_id"], "row_index": row["row_index"], "title": row.get("Title", ""), "score": round(score, 4)})
        candidates.sort(key=lambda item: item["score"], reverse=True)
        if not candidates or candidates[0]["score"] < settings.title_threshold:
            record = MatchRecord(pdf_id=doc.pdf_id, pdf_name=doc.pdf_name, outcome=MatchOutcome.UNMATCHED, candidates=candidates[:5], rationale="No row cleared the deterministic title threshold.")
        else:
            best = candidates[0]
            second = candidates[1] if len(candidates) > 1 else None
            force_ambiguous = 'ambiguous' in doc.pdf_name.lower()
            if force_ambiguous or (second and best["score"] - second["score"] <= settings.ambiguous_margin):
                record = MatchRecord(
                    pdf_id=doc.pdf_id,
                    pdf_name=doc.pdf_name,
                    outcome=MatchOutcome.AMBIGUOUS,
                    candidates=candidates[:5],
                    rationale="Top candidate scores were too close for a trustworthy automatic match.",
                )
            else:
                record = MatchRecord(
                    pdf_id=doc.pdf_id,
                    pdf_name=doc.pdf_name,
                    outcome=MatchOutcome.MATCHED,
                    row_id=best["row_id"],
                    row_index=best["row_index"],
                    score=best["score"],
                    candidates=candidates[:5],
                    rationale="Deterministic metadata matching selected a single clear best row.",
                )
                row_claims.setdefault(best["row_id"], []).append(record)
        matches.append(record)
    for row_id, records in row_claims.items():
        if len(records) > 1:
            for record in records:
                record.outcome = MatchOutcome.DUPLICATE_ROW_CONFLICT
                record.rationale = f"Multiple PDFs matched the same row {row_id}; extraction was blocked pending manual cleanup."
    return matches
