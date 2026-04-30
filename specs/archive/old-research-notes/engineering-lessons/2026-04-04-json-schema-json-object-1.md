Main problems we encountered
1) LM Studio / local model could not reliably handle strict json_schema-style constrained output

At one point the app crashed with an LM Studio error like:

HTTP 400
Failed to process regex

This strongly suggested that the backend was sending a guided JSON / regex / schema-constrained output request that LM Studio (or the specific local model/backend combination) could not compile or enforce.

This happened especially in the extraction step, where the schema was relatively complex.

2) Even when the request succeeded, the model often returned invalid or partially invalid JSON

We repeatedly saw proposals in review like:

No proposal because: llm json error

The model was often returning output that looked close to JSON, but failed parsing or validation because of things like:

malformed JSON structure
wrong field names
wrong column identifiers
wrong chunk identifiers
pseudo-JSON or explanatory text mixed into the payload
quotes/evidence fields not matching the expected schema
3) Our prompt templates made JSON compliance harder than it needed to be

One important issue was that some prompt examples described the output using type placeholders instead of real JSON values, for example things like:

"confidence": 0-1
"page": int
"col_id": int

That is not valid JSON, and local models can imitate that formatting. So instead of helping the model, the prompt was nudging it toward invalid output.

4) We were depending too much on schema-valid output in places where local models are fragile

The system originally treated structured output as a hard requirement. So if the model failed JSON parsing or schema validation, the pipeline often ended up with:

no proposal
llm json error
unclear / no-evidence outcomes

That made the overall extraction coverage much worse.

How we solved or mitigated the issues
1) We stopped relying on strict schema/regex-constrained output for LM Studio

Instead of assuming that json_schema or regex-guided decoding would work reliably, we moved toward a more robust approach:

use plain “return JSON only” prompting
validate client-side
retry/repair if needed

In other words:

guidance in prompt
validation in app
not hard dependency on LM Studio’s schema-enforcement features

This avoided the Failed to process regex class of failures.

2) We added a fallback path when guided JSON fails

The safer pattern became:

Try structured JSON generation in the normal way.
If LM Studio rejects it or returns bad JSON:
retry without strict schema guidance
ask for plain JSON only
Parse and validate on our side.

So the app no longer depends on the backend/model being perfect at native structured output.

3) We improved prompt design for JSON output

We changed the extraction prompts so they use:

real valid JSON examples
no pseudo-types like int or 0-1
clearer field expectations
stricter “JSON only, no prose” instructions

That reduced the frequency of malformed outputs.

4) We added JSON repair / extraction logic in the client

Instead of failing immediately on imperfect output, the app now follows a more tolerant flow:

strip markdown fences if present
extract the first plausible JSON object
parse it
if parsing fails, run a repair step
if still invalid, log the raw output and persist an error state

This made the system much more robust against near-valid local-model outputs.

5) We improved error handling so one JSON failure does not break the whole run

Previously, a bad extraction response could effectively kill usefulness for that proposal or even interrupt the workflow.

The improved behavior is:

persist the failure as structured metadata
keep the run going
log the raw model output and validation error
surface the issue in review/debug info instead of crashing

So JSON errors became recoverable run-time issues, not catastrophic failures.

6) We separated “proposal generation” from “evidence quality”

A major conceptual fix was this:

bad or weak evidence should not automatically erase the proposed value
the model should still propose its best value
evidence quality becomes a flag (weak, none, needs_more_evidence), not a hard blocker

This matters because earlier, JSON/evidence validation failures often indirectly caused:

proposed_value = null
“No value proposed”

We shifted toward:

keep best-effort proposal
annotate uncertainty
let the human reviewer decide
Practical conclusion

The main lesson was:

For local models via LM Studio, strict json_schema / regex-constrained output is brittle.
The more reliable pattern is:
plain JSON prompting + client-side parsing + repair + validation + graceful fallback.

That ended up being much more robust than assuming the model/backend would always honor strict structured-output contracts.

Recommended durable policy going forward

For this project, the safest default is:

avoid hard dependency on backend-native schema enforcement
use prompt-based JSON output
validate/repair in Python
persist raw failures for debugging
never let JSON failure wipe out the entire run
do not suppress best-effort proposals just because evidence/JSON is imperfect

If you want, I can also turn this into a short section for your README.md or AGENTS.md under something like “Structured output lessons learned”.