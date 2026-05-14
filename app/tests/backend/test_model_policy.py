from __future__ import annotations

from backend.app.model_policy import DEFAULT_MODEL_REQUEST_POLICY, resolve_model_request_policy


def test_unknown_model_uses_shared_default_policy() -> None:
    policy = resolve_model_request_policy("new-provider/new-model-v1")

    assert policy is DEFAULT_MODEL_REQUEST_POLICY
    assert policy.family == "generic"
    assert policy.preferred_structured_mode == "json_schema"
    assert policy.retry_malformed_structured_response is True


def test_qwen_policy_prefers_json_schema_and_keeps_non_thinking_json_guard() -> None:
    policy = resolve_model_request_policy("qwen/qwen3.6-27b")

    assert policy.preferred_structured_mode == "json_schema"
    assert policy.omit_max_tokens_for_structured is False
    assert policy.fast_abort_malformed_json_attempts == 3
    assert policy.retry_malformed_structured_response is True
    assert policy.request_defaults["top_p"] == 0.8
    assert policy.request_defaults["presence_penalty"] == 0.0
    assert policy.chat_template_kwargs_defaults == {"enable_thinking": False}
    assert policy.ordered_structured_modes("json_schema")[:2] == ["json_schema", "json_object"]
    messages = policy.apply_messages([{"role": "user", "content": "Return the result."}], "json_schema")
    assert "JSON" in messages[-1]["content"]
    assert "thinking" in messages[-1]["content"].casefold()


def test_gemma_and_gpt_oss_policy_keep_schema_first_without_prompt_mutation() -> None:
    for model_id in ["unsloth/gemma-4-26b-a4b-it", "openai/gpt-oss-20b"]:
        policy = resolve_model_request_policy(model_id)
        messages = [{"role": "user", "content": "Return the result."}]

        assert policy.preferred_structured_mode == "json_schema"
        assert policy.omit_max_tokens_for_structured is False
        assert policy.ordered_structured_modes("json_schema")[0] == "json_schema"
        assert policy.apply_messages(messages, "json_schema") == messages


def test_ministral_policy_has_reasoning_and_instruct_defaults() -> None:
    reasoning = resolve_model_request_policy("mistralai/ministral-3-14b-reasoning")
    instruct = resolve_model_request_policy("mistralai/ministral-3-3b-instruct")

    assert reasoning.family == "ministral_reasoning"
    assert reasoning.request_defaults == {"temperature": 0.7, "top_p": 0.95}
    assert instruct.family == "ministral_instruct"
    assert instruct.request_defaults == {"temperature": 0.15}
