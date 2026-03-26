from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from ..artifacts import ArtifactStore
from ..ids import new_evidence_id, new_proposal_id, stable_cell_id
from ..models import (
    EvidenceRecord,
    EvidenceSourceType,
    ProposalRecord,
    ProposalState,
    RunConfig,
    SupportLabel,
)


class ProviderError(RuntimeError):
    pass


class LmStudioProvider:
    def __init__(self, base_url: str, model_name: str, timeout_seconds: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def capability_probe(self) -> dict[str, Any]:
        return {"provider": "lm_studio", "structured_output": True, "vision": True}

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise ProviderError(f"provider_unreachable:{exc}") from exc
        parsed = json.loads(body)
        return parsed

    def _default_stub(self, request: dict[str, Any], mode: str) -> dict[str, Any]:
        passages = request.get("retrieved_passages", [])
        if passages:
            quote = passages[0].get("display_text", "")[:220]
            page = passages[0].get("page", 1)
            if quote:
                return {
                    "proposal_state": "inferred",
                    "proposed_value": "Needs reviewer confirmation",
                    "rationale": f"{mode} stub used because provider call is disabled or unavailable",
                    "calculation": None,
                    "support_label": "weak_evidence",
                    "evidence": {"quote_text": quote, "page": page, "highlight": None},
                }
        return {
            "proposal_state": "unclear",
            "proposed_value": None,
            "rationale": f"{mode} stub could not find relevant evidence",
            "calculation": None,
            "support_label": "weak_evidence",
            "evidence": {"quote_text": None, "page": None, "highlight": None},
        }

    def extract(self, request: dict[str, Any], mode: str = "text") -> dict[str, Any]:
        if request.get("provider_call_enabled", False) is not True:
            return self._default_stub(request, mode)
        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "proposal_response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "proposal_state": {"type": "string"},
                        "proposed_value": {"type": ["string", "null"]},
                        "rationale": {"type": ["string", "null"]},
                        "calculation": {"type": ["string", "null"]},
                        "support_label": {"type": "string"},
                        "evidence": {
                            "type": "object",
                            "properties": {
                                "quote_text": {"type": ["string", "null"]},
                                "page": {"type": ["integer", "null"]},
                                "highlight": {"type": ["object", "null"]},
                            },
                            "required": ["quote_text", "page", "highlight"],
                        },
                    },
                    "required": ["proposal_state", "proposed_value", "rationale", "calculation", "support_label", "evidence"],
                },
            },
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You extract structured values from scientific papers."},
                {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
            ],
            "response_format": schema,
            "temperature": 0,
        }
        response = self._post_json("/chat/completions", payload)
        try:
            content = response["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception as exc:  # pragma: no cover - external response variance
            raise ProviderError(f"malformed_provider_response:{exc}") from exc
        return parsed


class ExtractionService:
    FIGURE_HINTS = {"figure", "graph", "plot", "chart", "image", "microscopy"}

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    @staticmethod
    def _is_empty(value: Any, placeholders: set[str]) -> bool:
        if pd.isna(value):
            return True
        text = str(value).strip()
        return text == "" or text.lower() in placeholders

    @staticmethod
    def _map_state(value: str) -> ProposalState:
        mapping = {
            "found": ProposalState.FOUND,
            "inferred": ProposalState.INFERRED,
            "unclear": ProposalState.UNCLEAR,
            "blocked": ProposalState.BLOCKED,
            "error": ProposalState.ERROR,
            "skipped": ProposalState.SKIPPED,
        }
        return mapping.get(value, ProposalState.UNCLEAR)

    @staticmethod
    def _map_support(value: str) -> SupportLabel:
        mapping = {
            "direct_evidence": SupportLabel.DIRECT,
            "inferred_from_evidence": SupportLabel.INFERRED,
            "weak_evidence": SupportLabel.WEAK,
            "figure_based_evidence": SupportLabel.FIGURE,
        }
        return mapping.get(value, SupportLabel.WEAK)

    def _needs_figure_fallback(self, column_name: str, description: str, result: dict[str, Any]) -> bool:
        hints = f"{column_name} {description}".lower()
        likely = any(hint in hints for hint in self.FIGURE_HINTS)
        state = self._map_state(str(result.get("proposal_state", "unclear")))
        no_evidence = not (result.get("evidence") or {}).get("quote_text")
        return likely and (state in {ProposalState.UNCLEAR, ProposalState.ERROR} or no_evidence)

    def _build_figure_package(self, parsed_doc: dict[str, Any], retrieval_chunks: list[dict[str, Any]]) -> dict[str, Any]:
        pages = parsed_doc.get("pages", [])
        full_page = pages[0].get("full_page_path") if pages else None
        caption_chunk = next((chunk for chunk in retrieval_chunks if chunk.get("chunk_type") == "caption"), None)
        return {
            "crop": full_page,
            "caption": caption_chunk.get("display_text") if caption_chunk else None,
            "nearby_text": [chunk.get("display_text") for chunk in retrieval_chunks[:2]],
            "full_page_reference": full_page,
        }

    def run(
        self,
        *,
        run_id: str,
        run_dir: Path,
        config: RunConfig,
        table_df: pd.DataFrame,
        schema_df: pd.DataFrame,
        style_profiles: dict[str, dict[str, Any]],
        matching_results: list[dict[str, Any]],
        parsed_docs: list[dict[str, Any]],
        retrieval_chunks: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        provider = LmStudioProvider(config.provider.base_url, config.provider.model_name)
        provider_probe = provider.capability_probe()
        placeholder_values = {p.strip().lower() for p in config.review.placeholder_values}
        parsed_by_pdf = {doc["pdf_id"]: doc for doc in parsed_docs}

        proposals: list[ProposalRecord] = []
        evidence_rows: list[EvidenceRecord] = []
        diagnostics: list[dict[str, Any]] = []

        for match in matching_results:
            pdf_id = match["pdf_id"]
            parsed_doc = parsed_by_pdf.get(pdf_id, {})
            matched_row_index = match.get("matched_row_index")
            match_outcome = match.get("match_outcome")
            row_id = f"row_{matched_row_index}" if matched_row_index is not None else f"blocked_{pdf_id}"
            row = table_df.iloc[matched_row_index] if matched_row_index is not None else None
            chunks = retrieval_chunks.get(pdf_id, [])

            for _, schema_row in schema_df.iterrows():
                column_name = str(schema_row["column_name"])
                description = str(schema_row.get("description", "")).strip()
                cell_id = stable_cell_id(row_id, column_name)
                proposal_id = new_proposal_id(run_id, pdf_id, cell_id)
                source_mode = "text"

                if match_outcome != "matched":
                    proposal = ProposalRecord(
                        proposal_id=proposal_id,
                        run_id=run_id,
                        pdf_id=pdf_id,
                        row_id=row_id,
                        column_name=column_name,
                        cell_id=cell_id,
                        source_mode=source_mode,
                        proposal_state=ProposalState.BLOCKED,
                        support_label=SupportLabel.WEAK,
                        proposed_value=None,
                        rationale=f"Extraction blocked due to match outcome: {match_outcome}",
                        needs_more_evidence=True,
                    )
                    proposals.append(proposal)
                    diagnostics.append({"proposal_id": proposal_id, "status": "blocked", "reason": match_outcome})
                    continue

                if column_name not in table_df.columns:
                    proposal = ProposalRecord(
                        proposal_id=proposal_id,
                        run_id=run_id,
                        pdf_id=pdf_id,
                        row_id=row_id,
                        column_name=column_name,
                        cell_id=cell_id,
                        source_mode=source_mode,
                        proposal_state=ProposalState.SKIPPED,
                        support_label=SupportLabel.WEAK,
                        rationale="Column does not exist in table",
                        needs_more_evidence=False,
                    )
                    proposals.append(proposal)
                    diagnostics.append({"proposal_id": proposal_id, "status": "skipped", "reason": "missing_column"})
                    continue

                current_value = row[column_name]
                is_empty = self._is_empty(current_value, placeholder_values)
                if (not is_empty) and (not config.review.verify_mode):
                    continue

                selected_chunks = chunks[: config.retrieval.top_k]
                request_payload = {
                    "row_context": {
                        "row_index": int(matched_row_index),
                        "title": str(row.get("Title", "")),
                        "authors": str(row.get("Authors", "")),
                        "publication_year": str(row.get("Publication Year", "")),
                    },
                    "column": {"name": column_name, "description": description},
                    "style_profile": style_profiles.get(column_name, {}),
                    "retrieved_passages": selected_chunks,
                    "current_cell_value": None if is_empty else str(current_value),
                    "verify_mode": config.review.verify_mode,
                    "provider_call_enabled": config.provider.enable_live_calls,
                }

                try:
                    model_result = provider.extract(request_payload, mode="text")
                    state = self._map_state(str(model_result.get("proposal_state", "unclear")))
                except ProviderError as exc:
                    state = ProposalState.ERROR
                    model_result = {
                        "proposal_state": "error",
                        "proposed_value": None,
                        "rationale": str(exc),
                        "calculation": None,
                        "support_label": "weak_evidence",
                        "evidence": {"quote_text": None, "page": None, "highlight": None},
                    }

                if config.figure_fallback.enabled and self._needs_figure_fallback(column_name, description, model_result):
                    source_mode = "vision"
                    fig_package = self._build_figure_package(parsed_doc, selected_chunks)
                    figure_result = provider._default_stub({"retrieved_passages": selected_chunks}, "vision")
                    figure_result["support_label"] = "figure_based_evidence"
                    figure_result["evidence"] = {
                        "quote_text": figure_result["evidence"].get("quote_text"),
                        "page": figure_result["evidence"].get("page") or 1,
                        "highlight": None,
                        "crop_path": fig_package.get("crop"),
                        "full_page_path": fig_package.get("full_page_reference"),
                        "caption_text": fig_package.get("caption"),
                    }
                    model_result = figure_result
                    state = self._map_state(str(model_result.get("proposal_state", "unclear")))

                support = self._map_support(str(model_result.get("support_label", "weak_evidence")))
                evidence = model_result.get("evidence", {})
                quote_text = evidence.get("quote_text")
                page = evidence.get("page")
                highlight = evidence.get("highlight")
                needs_more_evidence = not bool(quote_text and page)

                if needs_more_evidence and selected_chunks:
                    recovered = selected_chunks[0]
                    quote_text = recovered.get("display_text", "")[:240]
                    page = recovered.get("page", 1)
                    highlight = None
                    needs_more_evidence = False

                evidence_ids: list[str] = []
                primary_evidence_id: str | None = None
                if quote_text or evidence.get("crop_path"):
                    evidence_id = new_evidence_id(proposal_id, 0)
                    ev_row = EvidenceRecord(
                        evidence_id=evidence_id,
                        proposal_id=proposal_id,
                        pdf_id=pdf_id,
                        source_type=EvidenceSourceType.FIGURE if support == SupportLabel.FIGURE else EvidenceSourceType.TEXT,
                        page=page,
                        quote_text=quote_text,
                        highlight=highlight if isinstance(highlight, dict) else None,
                        caption_text=evidence.get("caption_text"),
                        crop_path=evidence.get("crop_path"),
                        full_page_path=evidence.get("full_page_path"),
                        anchor_confidence=1.0 if isinstance(highlight, dict) else 0.4,
                    )
                    evidence_rows.append(ev_row)
                    evidence_ids.append(evidence_id)
                    primary_evidence_id = evidence_id

                proposal = ProposalRecord(
                    proposal_id=proposal_id,
                    run_id=run_id,
                    pdf_id=pdf_id,
                    row_id=row_id,
                    column_name=column_name,
                    cell_id=cell_id,
                    source_mode=source_mode,
                    proposal_state=state,
                    support_label=support,
                    proposed_value=model_result.get("proposed_value"),
                    rationale=model_result.get("rationale"),
                    calculation=model_result.get("calculation"),
                    needs_more_evidence=needs_more_evidence,
                    primary_evidence_id=primary_evidence_id,
                    evidence_ids=evidence_ids,
                )
                proposals.append(proposal)
                diagnostics.append(
                    {
                        "proposal_id": proposal_id,
                        "status": proposal.proposal_state.value,
                        "support_label": proposal.support_label.value,
                        "quote_page_fallback": bool(quote_text and page and not highlight),
                        "figure_based": proposal.support_label == SupportLabel.FIGURE,
                    }
                )

        self.store.atomic_write(
            run_dir / "proposals" / "proposals.jsonl",
            "\n".join(item.model_dump_json() for item in proposals) + ("\n" if proposals else ""),
        )
        self.store.atomic_write(
            run_dir / "evidence" / "evidence.jsonl",
            "\n".join(item.model_dump_json() for item in evidence_rows) + ("\n" if evidence_rows else ""),
        )
        self.store.write_json(
            run_dir / "proposals" / "diagnostics.json",
            {
                "provider_probe": provider_probe,
                "proposal_count": len(proposals),
                "evidence_count": len(evidence_rows),
                "items": diagnostics,
            },
        )
        return {
            "proposal_count": len(proposals),
            "evidence_count": len(evidence_rows),
        }
