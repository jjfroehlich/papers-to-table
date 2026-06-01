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
        self.assertEqual(response.metadata["request_timeout_seconds"], 300.0)
        self.assertEqual(response.metadata["model_load_timeout_seconds"], 600.0)
        self.assertEqual(response.metadata["model_unload_timeout_seconds"], 180.0)
        self.assertTrue(response.metadata["lm_studio_lock_enabled"])
        self.assertTrue(response.metadata["lm_studio_lock_path"].endswith(".lock"))
        self.assertGreaterEqual(response.metadata["lm_studio_lock_wait_ms"], 0.0)

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
        management_probe_count = {"count": 0}
        model_probe_count = {"count": 0}
        load_payload = {}
        unload_payload = {}

        def fake_urlopen(request_obj):
            import json

            seen_urls.append(request_obj.full_url)
            if request_obj.full_url.endswith("/api/v1/models"):
                management_probe_count["count"] += 1
                return _FakeHTTPResponse(
                    {
                        "models": [
                            {
                                "key": "other-model",
                                "loaded_instances": [{"id": "other-instance", "config": {"context_length": 32768}}],
                            },
                            {"key": "configured-model", "loaded_instances": []},
                        ]
                    }
                )
            if request_obj.full_url.endswith("/v1/models"):
                model_probe_count["count"] += 1
                if model_probe_count["count"] == 1:
                    return _FakeHTTPResponse({"data": []})
                return _FakeHTTPResponse({"data": [{"id": "configured-model"}]})
            if request_obj.full_url.endswith("/api/v1/models/unload"):
                unload_payload.update(json.loads(request_obj.data.decode("utf-8")))
                return _FakeHTTPResponse({"instance_id": "other-instance"})
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
        self.assertEqual(unload_payload["instance_id"], "other-instance")
        self.assertTrue(any(url.endswith("/api/v1/models/unload") for url in seen_urls))
        self.assertTrue(any(url.endswith("/api/v1/models/load") for url in seen_urls))
        self.assertTrue(any(url.endswith("/chat/completions") for url in seen_urls))
        self.assertEqual(management_probe_count["count"], 1)
        self.assertEqual(response.metadata["resolved_model_id"], "resolved-runtime-model")

    def test_lm_studio_adapter_reuses_loaded_model_without_loading_again(self) -> None:
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
        management_probe_count = {"count": 0}
        model_probe_count = {"count": 0}
        completion_count = {"count": 0}
        load_count = {"count": 0}
        unload_count = {"count": 0}

        def fake_urlopen(request_obj):
            if request_obj.full_url.endswith("/api/v1/models"):
                management_probe_count["count"] += 1
                return _FakeHTTPResponse(
                    {
                        "models": [
                            {
                                "key": "configured-model",
                                "loaded_instances": [{"id": "configured-instance", "config": {}}],
                            }
                        ]
                    }
                )
            if request_obj.full_url.endswith("/models"):
                model_probe_count["count"] += 1
                return _FakeHTTPResponse({"data": [{"id": "configured-model"}]})
            if request_obj.full_url.endswith("/api/v1/models/unload"):
                unload_count["count"] += 1
                raise AssertionError("unload should not be requested when the target model is already the only loaded model")
            if request_obj.full_url.endswith("/api/v1/models/load"):
                load_count["count"] += 1
                raise AssertionError("load should not be requested when the target model is already loaded")
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

        self.assertEqual(management_probe_count["count"], 2)
        self.assertEqual(model_probe_count["count"], 2)
        self.assertEqual(completion_count["count"], 2)
        self.assertEqual(load_count["count"], 0)
        self.assertEqual(unload_count["count"], 0)

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
        loaded_run.metadata.page_count = 1
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

    def test_exact_text_match_uses_judge_by_default_when_policy_defaults_to_judge(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="Expanded biological description",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
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

        self.assertEqual(len(judge.requests), 1)
        self.assertEqual(len(result.judge_records), 1)
        scored_cell = result.scored_cells[0]
        self.assertTrue(scored_cell.was_scored)
        self.assertFalse(scored_cell.is_correct)
        self.assertEqual(scored_cell.scoring_policy, "judge")
        self.assertEqual(scored_cell.judge_verdict, "incorrect")
        self.assertNotIn("text_exact_match_fast_path", scored_cell.diagnostic_flags)

    def test_exact_text_match_fast_path_can_be_enabled_explicitly(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="Expanded biological description",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
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
            enable_text_exact_match_fast_path=True,
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

    def test_field_type_number_alias_scores_as_numeric(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                proposed_value="20",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="number",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                raw_value="10",
                is_present=True,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))

        scored_cell = result.scored_cells[0]
        self.assertEqual(scored_cell.field_type, "numeric")
        self.assertEqual(scored_cell.comparison_kind, "numeric")
        self.assertFalse(scored_cell.is_correct)
        self.assertEqual(scored_cell.deterministic_failure_kind, "numeric_hard_mismatch")
        self.assertFalse(scored_cell.adjudication_eligible)

    def test_unknown_proposal_field_type_fails_when_used_for_scoring(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                proposed_value="20",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="mystery",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                raw_value="10",
                is_present=True,
            )
        )

        with self.assertRaisesRegex(ContractError, "Unsupported field_type 'mystery'"):
            score_run(loaded_run, gold, load_schema(None))

    def test_unknown_proposal_field_type_is_ignored_for_gold_empty_diagnostic_rows(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                proposed_value="20",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="mystery",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                raw_value=None,
                is_present=False,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))

        scored_cell = result.scored_cells[0]
        self.assertEqual(scored_cell.join_status, "gold_empty_diagnostic")
        self.assertIsNone(scored_cell.field_type)
        self.assertIn("unsupported_field_type_ignored", scored_cell.diagnostic_flags)
        self.assertEqual(scored_cell.diagnostics["unsupported_field_type"]["value"], "mystery")

    def test_unknown_proposal_field_type_is_ignored_for_unmatched_diagnostic_rows(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-2",
                column_name="count",
                cell_id="cell-count-2",
                proposed_value="20",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="mystery",
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                raw_value="10",
                is_present=True,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))

        scored_cell = next(cell for cell in result.scored_cells if cell.record_kind == "proposal_diagnostic")
        self.assertEqual(scored_cell.join_status, "unmatched_proposal")
        self.assertIsNone(scored_cell.field_type)
        self.assertIn("unsupported_field_type_ignored", scored_cell.diagnostic_flags)
        self.assertEqual(scored_cell.diagnostics["unsupported_field_type"]["value"], "mystery")

    def test_infers_bare_zero_one_as_numeric_not_boolean(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="Number of UMAP plot panels in Figure 1",
                cell_id="cell-count-1",
                proposed_value="1",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type=None,
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="Number of UMAP plot panels in Figure 1",
                cell_id="cell-count-1",
                raw_value="1",
                is_present=True,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))

        scored_cell = result.scored_cells[0]
        self.assertEqual(scored_cell.field_type, "numeric")
        self.assertTrue(scored_cell.is_correct)

    def test_infers_clear_boolean_pairs_as_boolean(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                proposed_value="no",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type=None,
            )
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                raw_value="yes",
                is_present=True,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))

        scored_cell = result.scored_cells[0]
        self.assertEqual(scored_cell.field_type, "boolean")
        self.assertEqual(scored_cell.deterministic_failure_kind, "boolean_contradiction")
        self.assertFalse(scored_cell.adjudication_eligible)

    def test_structured_failure_kind_marks_future_adjudication_eligible_soft_failures(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="efficiency",
                cell_id="cell-efficiency-1",
                proposed_value="65",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="numeric",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="method",
                cell_id="cell-method-1",
                proposed_value="mouse and human",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="categorical",
                allowed_values=["human", "mouse"],
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="detected",
                cell_id="cell-detected-1",
                proposed_value="yes",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="boolean",
            ),
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="efficiency",
                cell_id="cell-efficiency-1",
                raw_value="65%",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="method",
                cell_id="cell-method-1",
                raw_value="human, mouse",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="detected",
                cell_id="cell-detected-1",
                raw_value="+",
                is_present=True,
            ),
        )

        result = score_run(loaded_run, gold, load_schema(None))
        summary = build_run_summary(loaded_run, gold, result.scored_cells)
        by_column = {cell.column_name: cell for cell in result.scored_cells}

        self.assertEqual(by_column["efficiency"].deterministic_failure_kind, "numeric_unit_or_percent_format")
        self.assertTrue(by_column["efficiency"].adjudication_eligible)
        self.assertEqual(by_column["method"].deterministic_failure_kind, "categorical_list_format_mismatch")
        self.assertTrue(by_column["method"].adjudication_eligible)
        self.assertEqual(by_column["detected"].deterministic_failure_kind, "boolean_unknown_vocabulary")
        self.assertTrue(by_column["detected"].adjudication_eligible)
        self.assertEqual(summary.metrics["structured_deterministic_failure_count"], 3)
        self.assertEqual(summary.metrics["structured_adjudication_eligible_count"], 3)
        self.assertEqual(summary.metrics["structured_adjudication_eligible_failure_rate"], 1.0)
        self.assertEqual(summary.metrics["structured_adjudication_eligible_rate"], 1.0)

    def test_structured_failure_kind_marks_other_soft_failures_as_adjudication_eligible(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="efficiency_inequality",
                cell_id="cell-efficiency-ineq",
                proposed_value="65",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="numeric",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="efficiency_pm",
                cell_id="cell-efficiency-pm",
                proposed_value="65",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="numeric",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="efficiency_near",
                cell_id="cell-efficiency-near",
                proposed_value="10.2",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="numeric",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="method_alias_gap",
                cell_id="cell-method-alias-gap",
                proposed_value="canonical label",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="categorical",
                allowed_values=["Canonical Label", "Other"],
            ),
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="efficiency_inequality",
                cell_id="cell-efficiency-ineq",
                raw_value=">=65",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="efficiency_pm",
                cell_id="cell-efficiency-pm",
                raw_value="65 ± 2",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="efficiency_near",
                cell_id="cell-efficiency-near",
                raw_value="10.0",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="method_alias_gap",
                cell_id="cell-method-alias-gap",
                raw_value="canonical short",
                is_present=True,
            ),
        )

        result = score_run(loaded_run, gold, load_schema(None))
        by_column = {cell.column_name: cell for cell in result.scored_cells}

        self.assertEqual(by_column["efficiency_inequality"].deterministic_failure_kind, "numeric_inequality_format")
        self.assertTrue(by_column["efficiency_inequality"].adjudication_eligible)
        self.assertEqual(by_column["efficiency_pm"].deterministic_failure_kind, "numeric_plus_minus_format")
        self.assertTrue(by_column["efficiency_pm"].adjudication_eligible)
        self.assertEqual(by_column["efficiency_near"].deterministic_failure_kind, "numeric_near_miss")
        self.assertTrue(by_column["efficiency_near"].adjudication_eligible)
        self.assertEqual(by_column["method_alias_gap"].deterministic_failure_kind, "categorical_alias_gap")
        self.assertTrue(by_column["method_alias_gap"].adjudication_eligible)

    def test_structured_failure_kind_marks_hard_failures_as_not_adjudication_eligible(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                proposed_value="no",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="boolean",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                proposed_value="20",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="numeric",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="method",
                cell_id="cell-method-1",
                proposed_value="mouse",
                proposal_status="value_proposed",
                evidence_status="direct_strong",
                review_bucket="review",
                field_type="categorical",
                allowed_values=["human", "mouse"],
            ),
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                raw_value="yes",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="count",
                cell_id="cell-count-1",
                raw_value="10",
                is_present=True,
            ),
            GoldCell(
                row_id="row-1",
                column_name="method",
                cell_id="cell-method-1",
                raw_value="human",
                is_present=True,
            ),
        )

        result = score_run(loaded_run, gold, load_schema(None))
        by_column = {cell.column_name: cell for cell in result.scored_cells}

        self.assertEqual(by_column["status"].deterministic_failure_kind, "boolean_contradiction")
        self.assertFalse(by_column["status"].adjudication_eligible)
        self.assertEqual(by_column["count"].deterministic_failure_kind, "numeric_hard_mismatch")
        self.assertFalse(by_column["count"].adjudication_eligible)
        self.assertEqual(by_column["method"].deterministic_failure_kind, "categorical_allowed_value_mismatch")
        self.assertFalse(by_column["method"].adjudication_eligible)

    def test_proposal_field_type_aliases_canonicalize_when_used(self) -> None:
        cases = [
            ("number", "numeric", "10", "10", None),
            ("integer", "numeric", "10", "10", None),
            ("float", "numeric", "10.5", "10.5", None),
            ("bool", "boolean", "yes", "yes", None),
            ("enum", "categorical", "Human", "Human", None),
            ("category", "categorical", "Human", "Human", None),
            ("string", "text", "alpha", "alpha", "deterministic"),
            ("free_text", "text", "alpha", "alpha", "deterministic"),
            ("free-text", "text", "alpha", "alpha", "deterministic"),
        ]
        for index, (proposal_field_type, expected, gold_value, proposed_value, scoring_policy) in enumerate(cases, start=1):
            with self.subTest(proposal_field_type=proposal_field_type):
                loaded_run = self._loaded_run(
                    ProposalRecord(
                        run_id="run-a",
                        row_id=f"row-{index}",
                        column_name=f"column-{index}",
                        cell_id=f"cell-{index}",
                        proposed_value=proposed_value,
                        proposal_status="value_proposed",
                        evidence_status="direct_strong",
                        review_bucket="review",
                        field_type=proposal_field_type,
                        scoring_policy=scoring_policy,
                    )
                )
                gold = self._gold_dataset(
                    GoldCell(
                        row_id=f"row-{index}",
                        column_name=f"column-{index}",
                        cell_id=f"cell-{index}",
                        raw_value=gold_value,
                        is_present=True,
                    )
                )

                result = score_run(loaded_run, gold, load_schema(None))

                self.assertEqual(result.scored_cells[0].field_type, expected)

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
        self.assertEqual(summary.metrics["content_correctness"], 0.5)
        self.assertEqual(summary.metrics["correctness"], 0.5)
        self.assertEqual(summary.metrics["correctness_on_gold_present"], 0.5)
        self.assertEqual(summary.metrics["content_correctness_mean"], 1.0)
        self.assertEqual(summary.metrics["content_correctness_scored_only"], 1.0)
        self.assertEqual(summary.metrics["correctness_mean"], 1.0)
        self.assertEqual(summary.metrics["correctness_scored_only"], 1.0)
        self.assertEqual(summary.metrics["proposal_coverage_on_content_gold_present"], 0.5)
        self.assertEqual(summary.metrics["proposal_coverage_on_all_gold_present"], 0.5)
        self.assertEqual(summary.metrics["proposal_coverage_on_gold_present"], 0.5)

    def test_required_metadata_proposals_eliminate_old_nine_join_failure_pattern(self) -> None:
        proposals: list[ProposalRecord] = []
        gold_cells: list[GoldCell] = []
        for row_index in range(3):
            row_id = f"row-{row_index + 1}"
            for column_name, value, field_type in [
                ("Title", f"Paper {row_index + 1}", "text"),
                ("Authors", f"Author {row_index + 1}", "text"),
                ("Publication Year", "2024", "numeric"),
            ]:
                cell_id = f"cell-{row_id}-{column_name.replace(' ', '-').lower()}"
                proposals.append(
                    ProposalRecord(
                        run_id="run-a",
                        row_id=row_id,
                        column_name=column_name,
                        cell_id=cell_id,
                        proposed_value=value,
                        field_type=field_type,
                        scoring_policy="deterministic",
                        extraction_lane="metadata_front_matter",
                    )
                )
                gold_cells.append(
                    GoldCell(
                        row_id=row_id,
                        column_name=column_name,
                        cell_id=cell_id,
                        raw_value=value,
                        is_present=True,
                    )
                )
        loaded_run = self._loaded_run(*proposals)
        gold = self._gold_dataset(*gold_cells)

        result = score_run(loaded_run, gold, load_schema(None))
        summary = build_run_summary(loaded_run, gold, result.scored_cells)

        self.assertEqual(summary.metrics["metadata_gold_present_cell_count"], 9)
        self.assertEqual(summary.metrics["missing_proposal_count"], 0)
        self.assertEqual(summary.metrics["join_failure_count"], 0)
        self.assertEqual(summary.metrics["metadata_correctness"], 1.0)

    def test_summary_splits_content_metadata_and_evidence_grounded_metrics(self) -> None:
        loaded_run = LoadedRun(
            run_dir=Path("/tmp/run-a"),
            metadata=RunMetadata(
                run_id="run-a",
                run_dir=Path("/tmp/run-a"),
                style_profile_mode="masked_rows",
            ),
            proposals=[
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
                    extraction_lane="content",
                ),
                ProposalRecord(
                    run_id="run-a",
                    row_id="row-1",
                    column_name="year",
                    cell_id="cell-year-1",
                    proposed_value="2024",
                    field_type="numeric",
                    extraction_lane="metadata_front_matter",
                    failure_attribution="parser_gap",
                ),
            ],
            page_text_by_page={1: "Status remained present throughout follow-up."},
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
            GoldCell(
                row_id="row-1",
                column_name="year",
                cell_id="cell-year-1",
                raw_value="2024",
                is_present=True,
            ),
        )

        result = score_run(loaded_run, gold, load_schema(None))
        summary = build_run_summary(loaded_run, gold, result.scored_cells)

        self.assertEqual(summary.metrics["content_correctness"], 0.5)
        self.assertEqual(summary.metrics["content_correctness_scored_only"], 1.0)
        self.assertEqual(summary.metrics["overall_correctness"], 2 / 3)
        self.assertEqual(summary.metrics["overall_correctness_scored_only"], 1.0)
        self.assertEqual(summary.metrics["metadata_correctness"], 1.0)
        self.assertEqual(summary.metrics["evidence_grounded_correctness"], 0.5)
        self.assertEqual(summary.metrics["parser_gap_count"], 1)
        self.assertEqual(summary.metrics["benchmark_style_profile_mode"], "masked_rows")
        self.assertIn("year", summary.metrics["metadata_summary"]["fields"])

    def test_dual_judge_summary_records_disagreement_and_per_judge_counts(self) -> None:
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

        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judges={"judge_a": FakeJudge("correct"), "judge_b": FakeJudge("incorrect")},
            judge_configs={
                "judge_a": JudgeConfig(model_id="judge-model-a", label="judge_a"),
                "judge_b": JudgeConfig(model_id="judge-model-b", label="judge_b"),
            },
        )
        summary = build_run_summary(loaded_run, gold, result.scored_cells)

        self.assertTrue(summary.metrics["dual_judge_completed"])
        self.assertEqual(summary.metrics["judge_disagreement_count"], 1)
        self.assertEqual(summary.metrics["judge_disagreement_rate"], 1.0)
        self.assertEqual(summary.metrics["judge_summary"]["request_failed_count"]["judge_a"], 0)
        self.assertEqual(summary.metrics["judge_summary"]["verdict_counts"]["judge_b"]["incorrect"], 1)

    def test_dual_judge_execution_is_judge_major_and_reported(self) -> None:
        calls: list[tuple[str, str | None]] = []
        cleanup_calls: list[str] = []

        class RecordingJudge(FakeJudge):
            def __init__(self, label: str, verdict: str) -> None:
                super().__init__(verdict=verdict)
                self.label = label

            def judge(self, judge_request) -> JudgeResponse:
                calls.append((self.label, judge_request.cell_id))
                return super().judge(judge_request)

            def cleanup_model_residency(self) -> None:
                cleanup_calls.append(self.label)

        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="expanded biology description with assay context",
                field_type="text",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-2",
                column_name="notes",
                cell_id="cell-notes-2",
                proposed_value="another expanded biology description",
                field_type="text",
            ),
        )
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                raw_value="Expanded biological description for the assay",
                is_present=True,
            ),
            GoldCell(
                row_id="row-2",
                column_name="notes",
                cell_id="cell-notes-2",
                raw_value="Another biological description for the assay",
                is_present=True,
            ),
        )

        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judges={"judge_a": RecordingJudge("judge_a", "correct"), "judge_b": RecordingJudge("judge_b", "correct")},
            judge_configs={
                "judge_a": JudgeConfig(model_id="judge-model-a", label="judge_a"),
                "judge_b": JudgeConfig(model_id="judge-model-b", label="judge_b"),
            },
        )
        summary = build_run_summary(
            loaded_run,
            gold,
            result.scored_cells,
            judge_execution_summary=result.judge_execution_summary,
        )

        self.assertEqual(
            calls,
            [
                ("judge_a", "cell-notes-1"),
                ("judge_a", "cell-notes-2"),
                ("judge_b", "cell-notes-1"),
                ("judge_b", "cell-notes-2"),
            ],
        )
        self.assertEqual(result.judge_execution_summary["execution_order"], ["judge_a", "judge_b"])
        self.assertEqual(result.judge_execution_summary["eligible_cell_count"], 2)
        self.assertEqual(result.judge_execution_summary["batch_count"], 2)
        self.assertEqual(cleanup_calls, ["judge_a", "judge_b"])
        self.assertEqual(summary.metrics["judge_execution_summary"]["execution_policy"], "judge_major_grouped_by_provider_model_settings")

    def test_run_summary_never_reports_content_coverage_above_one(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="Title",
                cell_id="cell-title-1",
                proposed_value="Paper Title",
                field_type="text",
            ),
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="notes",
                cell_id="cell-notes-1",
                proposed_value="expanded biology description with assay context",
                field_type="text",
            ),
        )
        gold = self._gold_dataset(
            GoldCell(row_id="row-1", column_name="Title", cell_id="cell-title-1", raw_value="Paper Title", is_present=True),
            GoldCell(row_id="row-1", column_name="notes", cell_id="cell-notes-1", raw_value="Expanded biological description", is_present=True),
        )
        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judges={"judge_a": FakeJudge("correct")},
            judge_configs={"judge_a": JudgeConfig(model_id="judge-model-a", label="judge_a")},
        )

        summary = build_run_summary(loaded_run, gold, result.scored_cells, judge_execution_summary=result.judge_execution_summary)

        self.assertLessEqual(summary.metrics["proposal_coverage_on_content_gold_present"], 1.0)

    def test_dual_judge_partial_failure_preserves_successful_judge_result(self) -> None:
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

        result = score_run(
            loaded_run,
            gold,
            load_schema(None),
            text_judges={"judge_a": FakeJudge("correct"), "judge_b": FailingJudge("judge-b failed")},
            judge_configs={
                "judge_a": JudgeConfig(model_id="judge-model-a", label="judge_a"),
                "judge_b": JudgeConfig(model_id="judge-model-b", label="judge_b"),
            },
        )

        scored_cell = result.scored_cells[0]
        self.assertTrue(scored_cell.was_scored)
        self.assertTrue(scored_cell.is_correct)
        self.assertEqual(scored_cell.judge_results["judge_a"]["verdict"], "correct")
        self.assertEqual(scored_cell.judge_results["judge_b"]["verdict"], "unclear")
        self.assertIn("judge_request_failed", scored_cell.diagnostic_flags)
        self.assertEqual(result.judge_execution_summary["eligible_cell_counts_by_judge"]["judge_b"], 1)

    def test_evidence_anchor_audit_reports_reason_histograms(self) -> None:
        loaded_run = self._loaded_run(
            ProposalRecord(
                run_id="run-a",
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                proposed_value="present",
                field_type="categorical",
                evidence_items=[
                    EvidenceItem(evidence_id="ev-good", page=1, quote_text="Status remained present throughout follow-up."),
                    EvidenceItem(evidence_id="ev-bad", page=5, quote_text="missing page evidence"),
                ],
            )
        )
        loaded_run.metadata.page_count = 1
        gold = self._gold_dataset(
            GoldCell(
                row_id="row-1",
                column_name="status",
                cell_id="cell-status-1",
                raw_value="present",
                is_present=True,
            )
        )

        result = score_run(loaded_run, gold, load_schema(None))
        summary = build_run_summary(loaded_run, gold, result.scored_cells)

        self.assertEqual(summary.metrics["evidence_item_count"], 2)
        self.assertEqual(summary.metrics["validated_evidence_item_count"], 1)
        self.assertEqual(summary.metrics["anchor_invalid_count"], 1)
        self.assertEqual(summary.metrics["evidence_anchor_reason_counts"]["page_out_of_bounds"], 1)

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
