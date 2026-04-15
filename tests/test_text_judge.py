from __future__ import annotations

import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock
from urllib import error

from paper_eval.cli import build_judge_config
from paper_eval.aggregate import build_run_summary
from paper_eval.contracts import (
    EvidenceItem,
    GoldCell,
    GoldDataset,
    JudgeConfig,
    JudgeResponse,
    LoadedRun,
    ProposalRecord,
    RunMetadata,
)
from paper_eval.errors import ContractError, EvaluationError
from paper_eval.judge import (
    DEFAULT_JUDGE_MODEL_ID,
    DEFAULT_JUDGE_PROVIDER,
    DEFAULT_LM_STUDIO_API_BASE,
    LMStudioTextJudge,
    build_judge_request,
)
from paper_eval.schema_loader import load_schema
from paper_eval.score import score_run


class FakeJudge:
    def __init__(self, verdict: str = "correct", resolved_model_id: str | None = None) -> None:
        self.verdict = verdict
        self.resolved_model_id = resolved_model_id or "lmstudio-runtime-model"
        self.requests = []

    def judge(self, judge_request) -> JudgeResponse:
        self.requests.append(judge_request)
        return JudgeResponse(
            verdict=self.verdict,
            rationale_label="semantic_match",
            metadata={
                "provider": DEFAULT_JUDGE_PROVIDER,
                "configured_model_id": "judge-model-1",
                "resolved_model_id": self.resolved_model_id,
                "judge_response_mode": "json_schema",
            },
        )


class FailingJudge:
    def __init__(self, message: str = "Judge returned non-JSON output despite strict structured-output request.") -> None:
        self.message = message
        self.requests = []

    def judge(self, judge_request) -> JudgeResponse:
        self.requests.append(judge_request)
        raise EvaluationError(self.message)


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        import json

        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class LMStudioJudgeAdapterTests(unittest.TestCase):
    def test_build_judge_config_defaults_to_lm_studio_and_default_model(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            config = build_judge_config(Namespace(judge_model=None, judge_api_base=None))

        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.provider, DEFAULT_JUDGE_PROVIDER)
        self.assertEqual(config.model_id, DEFAULT_JUDGE_MODEL_ID)
        self.assertEqual(config.api_base, DEFAULT_LM_STUDIO_API_BASE)
        self.assertEqual(config.temperature, 0.0)

    def test_lm_studio_adapter_uses_structured_json_and_records_runtime_model(self) -> None:
        judge_config = JudgeConfig(model_id="configured-model")
        judge = LMStudioTextJudge(judge_config)
        judge_request = build_judge_request(
            judge_config=judge_config,
            run_id="run-a",
            row_id="row-1",
            column_name="notes",
            cell_id="cell-1",
            gold_value="Gold answer",
            proposed_value="Proposal answer",
            field_description="Field description",
            evidence_excerpt="Evidence excerpt",
        )
        captured_request = {}

        def fake_urlopen(request_obj):
            import json

            if request_obj.full_url.endswith("/models"):
                return _FakeHTTPResponse({"data": [{"id": "configured-model"}]})
            captured_request["url"] = request_obj.full_url
            captured_request["headers"] = dict(request_obj.header_items())
            captured_request["payload"] = json.loads(request_obj.data.decode("utf-8"))
            return _FakeHTTPResponse(
                {
                    "model": "resolved-runtime-model",
                    "choices": [{"message": {"content": '{"verdict":"correct","rationale_label":"semantic_match"}'}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                }
            )

        with mock.patch("paper_eval.judge.request.urlopen", side_effect=fake_urlopen):
            response = judge.judge(judge_request)

        self.assertEqual(captured_request["url"], f"{DEFAULT_LM_STUDIO_API_BASE}/chat/completions")
        self.assertEqual(captured_request["payload"]["model"], "configured-model")
        self.assertEqual(captured_request["payload"]["temperature"], 0.0)
        self.assertEqual(captured_request["payload"]["response_format"]["type"], "json_schema")
        self.assertEqual(response.verdict, "correct")
        self.assertEqual(response.metadata["judge_response_mode"], "json_schema")
        self.assertEqual(response.metadata["provider"], DEFAULT_JUDGE_PROVIDER)
        self.assertEqual(response.metadata["configured_model_id"], "configured-model")
        self.assertEqual(response.metadata["resolved_model_id"], "resolved-runtime-model")

    def test_lm_studio_adapter_falls_back_to_json_object_when_json_schema_fails(self) -> None:
        judge_config = JudgeConfig(model_id="configured-model")
        judge = LMStudioTextJudge(judge_config)
        judge_request = build_judge_request(
            judge_config=judge_config,
            run_id="run-a",
            row_id="row-1",
            column_name="notes",
            cell_id="cell-1",
            gold_value="Gold answer",
            proposed_value="Proposal answer",
            field_description=None,
            evidence_excerpt=None,
        )
        seen_modes: list[str] = []

        def fake_urlopen(request_obj):
            import json

            if request_obj.full_url.endswith("/models"):
                return _FakeHTTPResponse({"data": [{"id": "configured-model"}]})
            payload = json.loads(request_obj.data.decode("utf-8"))
            seen_modes.append((payload.get("response_format") or {}).get("type", "none"))
            if len(seen_modes) == 1:
                return _FakeHTTPResponse(
                    {
                        "model": "resolved-runtime-model",
                        "choices": [{"message": {"content": "not valid json"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                    }
                )
            return _FakeHTTPResponse(
                {
                    "model": "resolved-runtime-model",
                    "choices": [{"message": {"content": '{"verdict":"correct","rationale_label":"semantic_match"}'}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                }
            )

        with mock.patch("paper_eval.judge.request.urlopen", side_effect=fake_urlopen):
            response = judge.judge(judge_request)

        self.assertEqual(seen_modes, ["json_schema", "json_object"])
        self.assertEqual(response.verdict, "correct")
        self.assertEqual(response.metadata["judge_response_mode"], "json_object")
        self.assertTrue(response.metadata["structured_output_fallback_used"])

    def test_lm_studio_adapter_falls_back_to_prompt_only_mode(self) -> None:
        judge_config = JudgeConfig(model_id="configured-model")
        judge = LMStudioTextJudge(judge_config)
        judge_request = build_judge_request(
            judge_config=judge_config,
            run_id="run-a",
            row_id="row-1",
            column_name="notes",
            cell_id="cell-1",
            gold_value="Gold answer",
            proposed_value="Proposal answer",
            field_description=None,
            evidence_excerpt=None,
        )
        seen_modes: list[str] = []

        def fake_urlopen(request_obj):
            import json

            if request_obj.full_url.endswith("/models"):
                return _FakeHTTPResponse({"data": [{"id": "configured-model"}]})
            payload = json.loads(request_obj.data.decode("utf-8"))
            seen_modes.append((payload.get("response_format") or {}).get("type", "none"))
            if len(seen_modes) < 3:
                return _FakeHTTPResponse(
                    {
                        "model": "resolved-runtime-model",
                        "choices": [{"message": {"content": "not valid json"}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                    }
                )
            return _FakeHTTPResponse(
                {
                    "model": "resolved-runtime-model",
                    "choices": [{"message": {"content": "```json\n{\"verdict\":\"correct\",\"rationale_label\":\"semantic_match\"}\n```"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                }
            )

        with mock.patch("paper_eval.judge.request.urlopen", side_effect=fake_urlopen):
            response = judge.judge(judge_request)

        self.assertEqual(seen_modes, ["json_schema", "json_object", "none"])
        self.assertEqual(response.verdict, "correct")
        self.assertEqual(response.metadata["judge_response_mode"], "none")

    def test_lm_studio_adapter_loads_model_when_not_already_loaded(self) -> None:
        judge_config = JudgeConfig(model_id="configured-model")
        judge = LMStudioTextJudge(judge_config)
        judge_request = build_judge_request(
            judge_config=judge_config,
            run_id="run-a",
            row_id="row-1",
            column_name="notes",
            cell_id="cell-1",
            gold_value="Gold answer",
            proposed_value="Proposal answer",
            field_description=None,
            evidence_excerpt=None,
        )
        seen_urls: list[str] = []
        model_probe_count = {"count": 0}
        load_payload = {}

        def fake_urlopen(request_obj):
            import json

            seen_urls.append(request_obj.full_url)
            if request_obj.full_url.endswith("/v1/models"):
                model_probe_count["count"] += 1
                if model_probe_count["count"] == 1:
                    return _FakeHTTPResponse({"data": []})
                return _FakeHTTPResponse({"data": [{"id": "configured-model"}]})
            if request_obj.full_url.endswith("/api/v1/models/load"):
                load_payload.update(json.loads(request_obj.data.decode("utf-8")))
                return _FakeHTTPResponse({"status": "loaded"})
            if request_obj.full_url.endswith("/chat/completions"):
                return _FakeHTTPResponse(
                    {
                        "model": "resolved-runtime-model",
                        "choices": [{"message": {"content": '{"verdict":"correct","rationale_label":"semantic_match"}'}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                    }
                )
            raise AssertionError(f"Unexpected URL {request_obj.full_url}")

        with mock.patch("paper_eval.judge.request.urlopen", side_effect=fake_urlopen):
            response = judge.judge(judge_request)

        self.assertEqual(load_payload["model"], "configured-model")
        self.assertTrue(any(url.endswith("/api/v1/models/load") for url in seen_urls))
        self.assertTrue(any(url.endswith("/chat/completions") for url in seen_urls))
        self.assertEqual(response.metadata["resolved_model_id"], "resolved-runtime-model")

    def test_lm_studio_adapter_reuses_verified_model_without_repeat_probe(self) -> None:
        judge_config = JudgeConfig(model_id="configured-model")
        judge = LMStudioTextJudge(judge_config)
        judge_request = build_judge_request(
            judge_config=judge_config,
            run_id="run-a",
            row_id="row-1",
            column_name="notes",
            cell_id="cell-1",
            gold_value="Gold answer",
            proposed_value="Proposal answer",
            field_description=None,
            evidence_excerpt=None,
        )
        model_probe_count = {"count": 0}
        completion_count = {"count": 0}

        def fake_urlopen(request_obj):
            if request_obj.full_url.endswith("/models"):
                model_probe_count["count"] += 1
                return _FakeHTTPResponse({"data": [{"id": "configured-model"}]})
            if request_obj.full_url.endswith("/chat/completions"):
                completion_count["count"] += 1
                return _FakeHTTPResponse(
                    {
                        "model": "resolved-runtime-model",
                        "choices": [{"message": {"content": '{"verdict":"correct","rationale_label":"semantic_match"}'}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                    }
                )
            raise AssertionError(f"Unexpected URL {request_obj.full_url}")

        with mock.patch("paper_eval.judge.request.urlopen", side_effect=fake_urlopen):
            judge.judge(judge_request)
            judge.judge(judge_request)

        self.assertEqual(model_probe_count["count"], 1)
        self.assertEqual(completion_count["count"], 2)

    def test_lm_studio_adapter_fails_truthfully_when_unavailable(self) -> None:
        judge_config = JudgeConfig(model_id="configured-model")
        judge = LMStudioTextJudge(judge_config)
        judge_request = build_judge_request(
            judge_config=judge_config,
            run_id="run-a",
            row_id="row-1",
            column_name="notes",
            cell_id="cell-1",
            gold_value="Gold answer",
            proposed_value="Proposal answer",
            field_description=None,
            evidence_excerpt=None,
        )

        with mock.patch(
            "paper_eval.judge.request.urlopen",
            side_effect=error.URLError("connection refused"),
        ):
            with self.assertRaisesRegex(EvaluationError, "LM Studio judge request failed"):
                judge.judge(judge_request)


class TextJudgeScoringTests(unittest.TestCase):
    def test_score_run_uses_judge_by_default_for_text_fields_and_persists_metadata(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="expanded biology description with assay context",
                field_type="text",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                raw_value="Expanded biological description for the assay",
                is_present=True,
            )
        )
        judge = FakeJudge(verdict="correct", resolved_model_id="runtime-qwen-model")

        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judge=judge,
            judge_config=JudgeConfig(model_id="judge-model-1"),
        )

        self.assertEqual(len(judge.requests), 1)
        self.assertEqual(len(result.judge_records), 1)
        scored_cell = result.scored_cells[0]
        judge_record = result.judge_records[0]
        self.assertEqual(scored_cell.scoring_policy, "judge")
        self.assertTrue(scored_cell.was_scored)
        self.assertTrue(scored_cell.is_correct)
        self.assertEqual(scored_cell.judge_provider, DEFAULT_JUDGE_PROVIDER)
        self.assertEqual(scored_cell.judge_configured_model_id, "judge-model-1")
        self.assertEqual(scored_cell.judge_resolved_model_id, "runtime-qwen-model")
        self.assertEqual(scored_cell.judge_verdict, "correct")
        self.assertEqual(scored_cell.judge_response_mode, "json_schema")
        self.assertEqual(scored_cell.judge_model_id, "judge-model-1")
        self.assertEqual(scored_cell.judge_prompt_version, "batch3-text-judge-v1")
        self.assertEqual(scored_cell.judge_input_hash, judge_record.judge_input_hash)
        self.assertEqual(judge_record.judge_provider, DEFAULT_JUDGE_PROVIDER)
        self.assertEqual(judge_record.judge_configured_model_id, "judge-model-1")
        self.assertEqual(judge_record.judge_resolved_model_id, "runtime-qwen-model")
        self.assertEqual(judge_record.judge_verdict, "correct")
        self.assertEqual(judge_record.judge_response_mode, "json_schema")
        self.assertEqual(judge_record.judge_model_id, "judge-model-1")

    def test_text_fields_can_opt_into_deterministic_override(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="label",
                cell_id="cell-label-1",
                proposed_value="Study-A",
                field_type="text",
                scoring_policy="deterministic",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="label",
                cell_id="cell-label-1",
                raw_value="study a",
                is_present=True,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))

        self.assertEqual(len(result.judge_records), 0)
        scored_cell = result.scored_cells[0]
        self.assertTrue(scored_cell.was_scored)
        self.assertTrue(scored_cell.is_correct)
        self.assertEqual(scored_cell.scoring_policy, "deterministic")
        self.assertIsNone(scored_cell.judge_verdict)

    def test_missing_judge_configuration_fails_truthfully_for_judge_text_policy(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="Some text",
                field_type="text",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                raw_value="Some gold text",
                is_present=True,
            )
        )

        with self.assertRaisesRegex(ContractError, "--judge-model"):
            score_run(loaded_run, gold, load_schema(None))

    def test_exact_text_match_skips_judge_even_when_policy_defaults_to_judge(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="Expanded biological description",
                field_type="text",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                raw_value="expanded   biological description",
                is_present=True,
            )
        )
        judge = FakeJudge(verdict="incorrect")

        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judge=judge,
            judge_config=JudgeConfig(model_id="judge-model-1"),
        )

        self.assertEqual(len(judge.requests), 0)
        self.assertEqual(len(result.judge_records), 0)
        scored_cell = result.scored_cells[0]
        self.assertTrue(scored_cell.was_scored)
        self.assertTrue(scored_cell.is_correct)
        self.assertEqual(scored_cell.scoring_policy, "deterministic")
        self.assertIn("text_exact_match_fast_path", scored_cell.diagnostic_flags)

    def test_judge_request_is_bounded_and_marks_truncation(self) -> None:
        request = build_judge_request(
            judge_config=JudgeConfig(model_id="judge-model", max_value_chars=20, max_evidence_chars=12),
            run_id="run-a",
            row_id="row-1",
            column_name="notes",
            cell_id="cell-notes-1",
            gold_value="x" * 80,
            proposed_value="y" * 80,
            field_description="description",
            evidence_excerpt="quoted evidence goes here",
        )

        self.assertTrue(request.was_truncated)
        self.assertLessEqual(len(request.gold_value), 20)
        self.assertLessEqual(len(request.proposed_value), 20)
        self.assertLessEqual(len(request.evidence_excerpt or ""), 12)
        self.assertTrue(request.gold_value.endswith("…"))

    def test_structured_fields_remain_deterministic_when_text_judge_runs(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                proposed_value="yes",
                field_type="boolean",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="semantic match with added context",
                field_type="text",
            ),
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                raw_value="true",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                raw_value="Semantically matching context",
                is_present=True,
            ),
        )
        judge = FakeJudge(verdict="correct", resolved_model_id="runtime-qwen-model")

        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judge=judge,
            judge_config=JudgeConfig(model_id="judge-model-1"),
        )

        self.assertEqual(len(judge.requests), 1)
        status_cell = next(cell for cell in result.scored_cells if cell.column_name == "status")
        notes_cell = next(cell for cell in result.scored_cells if cell.column_name == "notes")
        self.assertTrue(status_cell.was_scored)
        self.assertTrue(status_cell.is_correct)
        self.assertIsNone(status_cell.judge_verdict)
        self.assertTrue(notes_cell.was_scored)
        self.assertEqual(notes_cell.judge_resolved_model_id, "runtime-qwen-model")
        self.assertEqual(len(result.judge_records), 1)

    def test_structured_support_proxy_marks_supported_numeric_and_categorical_values(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                proposed_value="present",
                field_type="categorical",
                evidence_items=[
                    EvidenceItem(
                        evidence_id="ev-status",
                        page=1,
                        quote_text="Status remained present throughout follow-up.",
                    )
                ],
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="score",
                cell_id="cell-score-1",
                proposed_value="45.3",
                field_type="numeric",
                evidence_items=[
                    EvidenceItem(
                        evidence_id="ev-score",
                        page=1,
                        quote_text="Bone volume fraction was 45.3% after 12 weeks.",
                    )
                ],
            ),
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                raw_value="present",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="score",
                cell_id="cell-score-1",
                raw_value="45.3",
                is_present=True,
            ),
        )

        result = score_run(loaded_run, gold, load_schema(None))
        summary = build_run_summary(loaded_run, gold, result.scored_cells)

        for cell in result.scored_cells:
            if cell.record_kind != "gold_cell":
                continue
            self.assertEqual(cell.diagnostics["structured_support_proxy"]["status"], "supported")

        self.assertEqual(summary.metrics["structured_support_proxy_evaluated_count"], 2)
        self.assertEqual(summary.metrics["structured_support_proxy_supported_count"], 2)
        self.assertEqual(summary.metrics["structured_support_proxy_unsupported_count"], 0)
        self.assertEqual(summary.metrics["structured_support_proxy_unvalidated_count"], 0)
        self.assertEqual(summary.metrics["structured_support_proxy_supported_rate"], 1.0)

    def test_structured_support_proxy_marks_missing_searchable_evidence_as_unvalidated(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="score",
                cell_id="cell-score-1",
                proposed_value="45.3",
                field_type="numeric",
                evidence_items=[EvidenceItem(evidence_id="ev-score", page=1, quote_text=None)],
            )
        )
        loaded_run.page_text_by_page = {}
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="score",
                cell_id="cell-score-1",
                raw_value="45.3",
                is_present=True,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))
        summary = build_run_summary(loaded_run, gold, result.scored_cells)

        proxy = result.scored_cells[0].diagnostics["structured_support_proxy"]
        self.assertEqual(proxy["status"], "unvalidated")
        self.assertEqual(proxy["reason"], "no_searchable_evidence_text")
        self.assertEqual(summary.metrics["structured_support_proxy_evaluated_count"], 0)
        self.assertEqual(summary.metrics["structured_support_proxy_supported_count"], 0)
        self.assertEqual(summary.metrics["structured_support_proxy_unvalidated_count"], 1)
        self.assertIsNone(summary.metrics["structured_support_proxy_supported_rate"])

    def test_judge_runtime_failure_becomes_unclear_record_instead_of_aborting(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="semantic match with added context",
                field_type="text",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                raw_value="Semantically matching context",
                is_present=True,
            )
        )
        judge = FailingJudge()

        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judge=judge,
            judge_config=JudgeConfig(model_id="judge-model-1"),
        )

        self.assertEqual(len(judge.requests), 1)
        self.assertEqual(len(result.judge_records), 1)
        scored_cell = result.scored_cells[0]
        self.assertFalse(scored_cell.was_scored)
        self.assertIsNone(scored_cell.is_correct)
        self.assertEqual(scored_cell.judge_verdict, "unclear")
        self.assertIn("judge_verdict_unclear", scored_cell.diagnostic_flags)
        self.assertIn("judge_request_failed", scored_cell.diagnostic_flags)
        self.assertEqual(
            scored_cell.diagnostics["judge"]["error_message"],
            "Judge returned non-JSON output despite strict structured-output request.",
        )
        self.assertEqual(result.judge_records[0].judge_verdict, "unclear")
        self.assertEqual(result.judge_records[0].rationale_label, "judge_error")

    def test_headline_correctness_counts_missing_proposals(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                proposed_value="present",
                field_type="categorical",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                raw_value="present",
                is_present=True,
            ),
            GoldCell(
                row_id="row-2",
                column_name="status",
                cell_id="cell-status-2",
                raw_value="absent",
                is_present=True,
            ),
        )

        result = score_run(loaded_run, gold, load_schema(None))
        summary = build_run_summary(loaded_run, gold, result.scored_cells)

        self.assertEqual(summary.metrics["missing_proposal_count"], 1)
        self.assertEqual(summary.metrics["correctness"], 0.5)
        self.assertEqual(summary.metrics["correctness_on_gold_present"], 0.5)
        self.assertEqual(summary.metrics["correctness_mean"], 1.0)
        self.assertEqual(summary.metrics["correctness_scored_only"], 1.0)

    def _loaded_run(self, *proposals: ProposalRecord) -> LoadedRun:
        return LoadedRun(
            run_dir=Path("/tmp/run-a"),
            metadata=RunMetadata(run_id="run-a", run_dir=Path("/tmp/run-a")),
            proposals=list(proposals),
            page_text_by_page={1: "Status remained present throughout follow-up. Bone volume fraction was 45.3% after 12 weeks."},
        )

    def _gold_dataset(self, *cells: GoldCell) -> GoldDataset:
        return GoldDataset(source_path=Path("/tmp/gold.csv"), sheet_name=None, cells=list(cells))


if __name__ == "__main__":
    unittest.main()
