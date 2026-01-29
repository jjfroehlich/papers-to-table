# LM Studio compatibility: logging + prompt budgeting

## What changed
- Added LLM request observability (model, endpoint, timeouts, payload flags, prompt sizes, and safe snippets) behind a debug flag so local providers can be diagnosed without dumping full prompts.
- Logged HTTP 400 response bodies from LM Studio to expose root causes like regex/schema rejections.
- Introduced prompt token budgeting and context-limit handling to prevent llama.cpp `n_keep >= n_ctx` truncation failures, plus longer read timeouts for slow local generations.

## Why it matters
Local OpenAI-compatible servers vary in supported payload fields and context limits. Without targeted logging and proactive prompt budgeting, failures look like opaque JSON errors and runs can fail mid-generation.

## Durable rule?
Yes. Always ship local-provider integrations with opt-in request logging and a conservative prompt/token budget; rely on server-side truncation as a last resort.

## Proposed update
Add a note to provider configuration guidance to require explicit prompt/token budgets and to enable LLM debug logs when onboarding new local models.
