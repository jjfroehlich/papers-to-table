from __future__ import annotations

from backend.app.model_policy import DEFAULT_MODEL_REQUEST_POLICY, resolve_model_request_policy


def test_unknown_model_uses_shared_default_policy() -> None:
    policy = resolve_model_request_policy("new-provider/new-model-v1")

    assert policy is DEFAULT_MODEL_REQUEST_POLICY
    assert policy.family == "generic"
    assert policy.preferred_structured_mode == "json_schema"
    assert policy.retry_malformed_structured_response is True


def test_qwen_policy_prefers_json_object_and_adds_json_reminder() -> None:
    policy = resolve_model_request_policy("qwen/qwen3.6-27b")

    assert policy.preferred_structured_mode == "json_object"
    assert policy.omit_max_tokens_for_structured is True
    assert policy.fast_abort_malformed_json_attempts == 1
    assert policy.retry_malformed_structured_response is False
    assert policy.ordered_structured_modes("json_schema")[:2] == ["json_object", "json_schema"]
    messages = policy.apply_messages([{"role": "user", "content": "Return the result."}], "json_object")
    assert "JSON" in messages[-1]["content"]
    assert "thinking" in messages[-1]["content"].casefold()


def test_gemma_and_gpt_oss_policy_keep_schema_first_without_prompt_mutation() -> None:
    for model_id in ["google/gemma-4-e4b", "openai/gpt-oss-20b"]:
        policy = resolve_model_request_policy(model_id)
        messages = [{"role": "user", "content": "Return the result."}]

        assert policy.preferred_structured_mode == "json_schema"
        assert policy.omit_max_tokens_for_structured is False
        assert policy.ordered_structured_modes("json_schema")[0] == "json_schema"
        assert policy.apply_messages(messages, "json_schema") == messages
