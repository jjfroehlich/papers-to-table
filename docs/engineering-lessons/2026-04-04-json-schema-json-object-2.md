We ran into two main classes of problems with json_schema / json_object style outputs.

1. Backend-level structured output failures

With LM Studio, some models/backend combinations rejected structured output requests outright, most visibly as HTTP 400: Failed to process regex.
This happened especially with response_format: { type: "json_schema", ... }, likely because the backend translated parts of the schema into grammar/regex constraints it could not compile.
In practice, this meant the run failed before proposals were produced, even when the underlying model could answer normally in plain chat mode.

How we addressed it

We stopped assuming structured output support and treated it as a capability, not a default.
We added logic to:
detect regex/grammar-related 400s,
classify them as backend incompatibility,
disable guided/structured JSON for that model/backend,
retry in prompt-only JSON mode instead of json_schema.
We also moved toward schema sanitization/simplification, so unsupported schema features like regex-heavy constraints do not get sent to fragile backends.

2. Model output was “JSON-like” but not valid strict JSON

Some local models, especially GLM-like behavior, returned:
explanations before JSON,
<think> blocks,
fenced ```json code blocks,
wrong types or shape drift,
partially valid JSON with extra text around it.
That broke strict parsing and Pydantic validation, so stages like header extraction or matching failed and the pipeline never reached proposal generation.

How we addressed it

We hardened the JSON ingestion path:
strip markdown fences,
strip <think>-style wrappers,
extract the first/last balanced JSON object from mixed output,
only then parse and validate.
If that still failed, we added a repair step rather than dropping the result immediately.
We also improved prompts to explicitly say:
return JSON only,
no code fences,
no commentary,
no wrapper text.

3. Prompt/schema mismatch with local models

Even when the backend accepted structured output, local models often did not reliably satisfy the exact schema.
They might omit fields, rename fields, or return strings where numbers were expected.

How we addressed it

We made the schema/output contract more tolerant where possible.
We improved logging of:
raw model output,
validation errors,
whether repair was attempted,
whether guided JSON was active.
This made it much easier to see whether the problem was:
backend rejection,
invalid JSON text,
or schema validation mismatch.

4. “Guided JSON off” did not always fully solve it

We discovered that even after turning guided JSON off in config, some failures still looked like regex/grammar issues.
That suggested the incompatibility was not only in our explicit response_format, but could also be caused by how LM Studio/backend/model handled certain structured-output or grammar paths internally.

How we addressed it

We added more explicit compatibility probing and better diagnostics.
We learned to treat certain models as effectively not suitable for structured JSON on that backend, even if plain chat worked.
In practice, this pushed us toward:
model/backend probing,
fallback routing,
and favoring models like Qwen that behaved better in prompt-only JSON mode.

Net result

The main solution was not “make the schema stricter.”
It was:
use structured output only when the backend truly supports it,
fall back to plain JSON prompting when needed,
aggressively harden parsing/repair,
and log enough metadata to distinguish backend incompatibility from model-formatting problems.

What worked best in practice

Qwen-style models were the most usable because they could often return workable JSON in prompt-only mode.
GPT-OSS on LM Studio remained problematic because of backend regex/grammar incompatibility.
GLM improved once parsing became more tolerant, but operational issues like slowness and model unloads still remained separate problems.

So the big lesson was: json_schema / json_object is not a universal reliability feature in local agent stacks. It has to be treated as an optional optimization layered on top of a robust plain-text-to-JSON fallback.