
Research whether Paper Table Agent should use **existing filled spreadsheet cells as examples in extraction prompts**, and if so, how to do that safely.

Please research whether Paper Table Agent should use **existing filled spreadsheet cells as examples in extraction prompts**, and if so, how to do that safely.

## Context

Paper Table Agent extracts structured information from scientific PDFs into spreadsheet cells using a schema.

Each schema column currently has:
- column_name
- description

We are considering also using examples from already-filled cells in that same column to help the model understand:
- expected answer format
- answer length
- whether outputs are numeric / short categorical / long text / argumentation
- typical unit or style patterns

Potential benefit:
- the model may better understand what kind of answer belongs in the column

Potential risks:
- hallucination or overfitting to example style/content
- copying patterns that do not belong in the current paper
- biasing the output incorrectly
- leakage in Verify-mode evaluation if cells used as examples are also later scored as targets

## Research questions

1. How do current extraction systems, document QA systems, or structured-output LLM pipelines use examples from existing datasets/tables?
2. Is using in-table examples a known good practice, and in what form?
3. What are the risks of:
   - hallucination
   - format overfitting
   - semantic anchoring to irrelevant examples
   - leakage in evaluation
4. How do other systems reduce these risks?
5. Are there safer ways to communicate expected output format without using actual existing content?
6. Should Paper Table Agent use filled-cell examples in MVP? If yes, under what safeguards?

## Deliverables

Please produce a report with:

### 1. Executive summary
State clearly whether you recommend:
- using examples in MVP
- not using them in MVP
- using only format-like examples
- using examples only in certain situations

### 2. Survey of approaches
Cover current practices in:
- extraction systems
- structured prompting
- few-shot prompting for information extraction
- schema-guided extraction
- table-to-text / document-to-table systems
- LLM evaluation settings where leakage matters

### 3. Risks and failure modes
Explain concretely:
- hallucination risks
- anchoring bias
- leakage risks in Verify mode
- how examples can distort extracted values

### 4. Safe design options for our app
Compare options such as:
- no examples
- synthetic format examples
- examples from other rows only
- examples from a held-out pool
- examples for formatting only, not semantics
- examples only for certain field types
- examples disabled in Verify mode
- examples excluded from evaluation targets automatically

### 5. Recommendation for Paper Table Agent
Give a concrete recommendation for:
- MVP
- later versions

### 6. Guardrails
List the minimum safeguards we would need if examples are used.

## Constraints

- Our app is local-first and review-oriented.
- We care about trustworthy evaluation and must avoid leakage.
- We do not want to introduce complexity unless it has a clear payoff.
- Please include citations/links and clearly separate evidence from opinion.

## Output format

Return a structured markdown report with headings:
- Executive summary
- Existing approaches
- Risks and failure modes
- Safe design options
- Recommended approach for MVP
- Later improvements
- Open questions

I’m gathering two things in parallel: what production systems actually do for schema/extraction prompting, and what the literature says about exemplar-driven bias and evaluation leakage. Then I’ll turn that into a concrete MVP recommendation with guardrails.

I’ve got the core evidence now. The pattern is pretty consistent: examples are useful for output shape and consistency, but the literature also shows models can latch onto superficial patterns in demonstrations, which is exactly the failure mode you’d want to avoid in Verify mode.

Thought for 3m 18s
Executive summary

Recommendation for MVP (opinion):
Do not use existing filled spreadsheet cells as free-form semantic examples in extraction prompts for MVP. Instead, use a safer middle path: keep prompts schema-first, add stronger field metadata and format hints, and allow only synthetic format-like examples for narrow field types such as numbers, booleans, enums, ranges, and unit formatting. In Verify mode, do not use any scored cells as prompt examples. If you later experiment with real examples, use a separate held-out exemplar pool that is excluded from evaluation.

Why this is my recommendation (evidence):
Current prompting guidance does support examples, but mainly as a way to steer output format, tone, and structure rather than to import task-specific semantic content. OpenAI explicitly recommends showing the desired output format through examples, and Anthropic says examples are especially reliable for steering format and structure, while also warning that examples should be relevant and diverse enough to avoid unintended patterns.

In current extraction systems, the dominant pattern I found is schema + field descriptions + document-level hints + grounding/citations, not “feed live values from the current spreadsheet as in-context semantic exemplars.” Google Document AI emphasizes document-level prompts and field descriptions as hints, Vertex’s document extraction sample requires values to come only from the document and to return null when missing, Azure query fields asks the user to specify the fields to extract, and LlamaExtract emphasizes field descriptions as extraction instructions.

The research literature gives a second reason to be cautious: demonstrations can help, but models often learn from surface regularities, priors, and shortcut features rather than the intended semantic mapping. Min et al. found that replacing ground-truth labels in demonstrations often barely hurts performance; Jang et al. describe “demonstration shortcut,” where models rely on the semantic priors of demonstrations instead of the intended input-label relationship; and Si et al. show that under-specified prompts can steer models toward the wrong predictive feature.

The evaluation risk is real. Work on contamination and evaluation warns that guideline contamination, annotation contamination, test-set leakage, and prompt-format overfitting can invalidate or distort results. One survey explicitly says exposure of the evaluation split invalidates the experiment; benchmark docs and evaluation frameworks commonly keep few-shot support examples separate from the test queries.

Bottom line (opinion):
For Paper Table Agent, examples are worth using only when they communicate format, not when they smuggle in likely content. For MVP, use format-like examples only, and keep them out of Verify-mode scoring.

Existing approaches
1) Prompting guides: examples are mainly for shaping outputs

OpenAI’s prompt guide recommends examples to articulate the desired output format, and Anthropic says examples are one of the most reliable ways to steer output format, tone, and structure. Anthropic also recommends that examples be relevant, diverse, and explicitly separated from instructions to reduce unintended pattern pickup.

Implication for your app (opinion):
This supports examples as a format-control tool. It is much weaker evidence for using actual filled cells as semantic priors for what the answer should say.

2) Extraction systems: schema descriptions and hints dominate

Google Document AI uses document-level prompts and field descriptions to improve extraction quality, and explicitly frames prompts as hints rather than rule engines. It also recommends generating and editing schemas with prompts, rather than relying on live target-table content.

Vertex AI’s document entity extraction example requires that the JSON schema be followed, that extracted values include only text strings found in the document, and that null be returned for missing entities.

Azure Document Intelligence’s query-field workflow asks the user to define which fields to extract, effectively extending the schema rather than relying on row exemplars.

LlamaExtract and LlamaIndex both emphasize that schemas and field descriptions act as instructions to the LLM. LlamaExtract explicitly says descriptions improve extraction accuracy and can carry formatting instructions; LlamaIndex says JSON schemas plus natural-language field descriptions are crucial for structured extraction.

Implication for your app (opinion):
The common production pattern is: define the field well, constrain the output, and ground it in the source. That is a better default than using already-filled cells from the active spreadsheet.

3) Some extraction libraries do use few-shot examples

Google’s LangExtract is a good counterexample: it explicitly supports few-shot examples, says they enforce a consistent output schema, and warns that “examples drive model behavior.” It also couples this with exact source grounding and warns when example extraction text is not verbatim/aligned.

Implication for your app (opinion):
If you use examples at all, LangExtract suggests the safe pattern: examples must be explicit, aligned, and paired with source grounding. Loose, untracked reuse of filled cells would be the risky version of this idea.

4) Few-shot IE research: example choice matters, but selection is nontrivial

Research on few-shot prompting shows that example selection matters a lot. IDS selects examples that are both diverse and strongly correlated with the test item, and example-selection work for sequence tagging/NER shows measurable gains when prompt examples are matched to the complexity of the test sentence.

At the same time, few-shot IE remains hard. An ACL study on few-shot event detection found that simple in-context learning baselines still lag substantially on IE tasks that require structured outputs.

Implication for your app (opinion):
If you eventually use examples, “just pick some filled cells from the table” is not enough. Selection policy matters, and getting it wrong can easily hurt rather than help.

5) Evaluation settings: support examples are usually split from test targets

In benchmark practice, few-shot support examples are usually drawn from a training or validation/support split, not from the test items being scored. LongBench samples few-shot examples from the training set for validation tasks, and the BasicSpatialAbility benchmark explicitly says the test split is evaluation-only and should not be used as few-shot examples; its validation split is the support set for prompting.

Implication for your app (opinion):
This strongly supports a disjoint “support pool vs evaluation pool” design if Paper Table Agent ever adopts real exemplars.

Risks and failure modes
Hallucination and unsupported filling

If examples contain semantically rich prior answers, the model may guess toward those patterns when the paper is ambiguous, rather than saying “not found.” More broadly, LLMs tend to guess when uncertain, which is a core source of hallucination.

Concrete PTA failure mode (opinion):
A column like “mechanism summary” or “main conclusion” could drift toward the tone or claims seen in previous filled cells, even when the current paper supports something else or nothing at all.

Anchoring and format overfitting

Demonstrations do not always teach the intended task. Min et al. found that correct labels in demonstrations are often less important than expected; Jang et al. identify “demonstration shortcut”; and Si et al. show that under-specified prompts can bias the model toward the wrong latent feature.

Concrete PTA failure mode (opinion):
If prior cells in a column often contain short categorical answers, the model may over-compress a genuinely nuanced answer. If prior cells often mention a common unit or assay, the model may prefer that pattern even when the paper uses a different one.

Semantic contamination from irrelevant examples

Anthropic recommends relevant and diverse examples specifically to avoid unintended patterns, and example-selection research shows that prompt quality depends heavily on which examples are chosen.

Concrete PTA failure mode (opinion):
Examples from unrelated subfields, organism systems, assay types, or reporting conventions could quietly bias the extraction toward the wrong ontology or vocabulary.

Leakage in Verify mode

Contamination literature distinguishes guideline, text, and annotation contamination, and explicitly states that if the evaluation split is exposed, the experiment is invalidated. Separately, work on automated evaluation flags test-set leakage and prompt-format overfitting as threats to reliable evaluation.

Concrete PTA failure mode (opinion):
If a verified cell is later scored, and its value or a near-duplicate was already shown as an in-context example, your score is no longer measuring extraction performance alone. It is partially measuring prompt leakage.

Distortion of answer style and reviewer trust

Current extraction tools increasingly emphasize source grounding, citations, and verifiable spans because structured extraction is only useful if users can trust where it came from. LangExtract, Vertex, and LlamaExtract all reflect this grounding-first pattern.

Concrete PTA failure mode (opinion):
If reviewers see outputs that “look like prior rows” more than they look like the paper, trust in the app will drop even if raw accuracy changes little.

Safe design options
Option A — No examples

What it is: rely on column name, description, source text, and structured output constraints only.
Pros: simplest, no leakage from exemplars, easiest to evaluate fairly.
Cons: weaker control of answer length/format for messy columns.

Assessment (opinion): good default baseline, especially for MVP.

Option B — Synthetic format examples only

What it is: allow non-semantic examples such as 12.5, yes, 2–5 days, upregulated, p53; MYC; SOX2, or not reported, explicitly labeled as format examples only.
Pros: captures formatting, units, brevity, and null-style without leaking semantic content; consistent with prompt-guidance that examples help with output form.
Cons: adds some schema complexity; limited benefit for long free-text fields.

Assessment (opinion): best MVP option if you want examples at all.

Option C — Examples from other rows in the same active sheet

What it is: sample filled cells from neighboring rows in the same column and insert them into the prompt.
Pros: cheap, zero extra curation.
Cons: highest anchoring risk; likely domain mismatch; hard to reason about leakage; dangerous in Verify mode.

Assessment (opinion): not recommended.

Option D — Held-out exemplar pool

What it is: maintain a separate pool of reviewed exemplars per column, stored outside the active evaluation set and never scored in the same run.
Pros: closer to benchmark best practice of support-vs-test separation; allows curation and diversity controls.
Cons: more infrastructure, provenance tracking, and maintenance.

Assessment (opinion): good later-stage option, not MVP.

Option E — Format-only examples for certain field types

What it is: enable examples only for numeric, enum, boolean, range, unit-bearing, or very short template-like fields.
Pros: most of the benefit with much less semantic risk.
Cons: inconsistent feature coverage across columns.

Assessment (opinion): strong choice for MVP if paired with synthetic examples.

Option F — Disable examples in Verify mode

What it is: examples may exist in normal extraction mode, but not when cells are being used for scoring.
Pros: protects evaluation integrity.
Cons: scores may no longer exactly reflect the “full assistive mode” behavior.

Assessment (opinion): necessary if you ever use real examples.

Option G — Use examples, but automatically exclude them from evaluation targets

What it is: any row used as a support example is removed from the scored set for that run.
Pros: reduces direct leakage.
Cons: still leaves anchoring risk; still more complex than schema-first design; can complicate run accounting.

Assessment (opinion): acceptable only in a later, carefully instrumented design.

Recommended approach for MVP
Evidence-based conclusion

The evidence supports three things. First, examples are genuinely useful for format control. Second, they can also create shortcut learning and anchoring. Third, reliable evaluation practice requires strict separation between support examples and scored targets.

My concrete MVP recommendation

Do not use existing filled cells as semantic examples in MVP.

Add richer schema metadata instead of live row examples:

value_type

allowed_values / enum set

unit_hint

null_policy

length_hint

extractive_vs_derived

optional format_example or format_examples that are synthetic and clearly non-semantic.

Allow synthetic format-only examples only for columns where format matters more than semantics.

In Verify mode, use no real examples from the spreadsheet at all.

Invest instead in evidence grounding: quote/snippet/page, span highlighting, and explicit “not found / ambiguous” behaviors. This is more aligned with the review-oriented nature of the product and with current extraction-system practice.

Suggested MVP rule by field type

Use synthetic format examples:
numbers, percentages, booleans, enums, ranges, units, short controlled strings.

Do not use examples at all:
open-ended summaries, mechanisms, rationale fields, interpretation-heavy fields, and any field later used for Verify-mode scoring.

Later improvements

Once MVP is stable, I would test examples only in a stricter architecture:

1) Build a reviewed exemplar bank

Use a small curated support pool per column, separate from active jobs and evaluation targets. Keep provenance and review status for every exemplar. This mirrors standard support/test separation used in few-shot evaluation.

2) Retrieve exemplars by field type and format, not by likely content

Bias retrieval toward answer shape, allowed vocabulary, and unit pattern. Avoid semantic-nearest-neighbor retrieval for open text until you have strong evidence it helps.

3) Restrict exemplars to low-risk columns

Start with columns where “good output” mostly means “correct format,” not “correct interpretation.”

4) Log exemplar provenance

For every generated cell, store which exemplar IDs were shown. This is required for later auditability.

5) Run ablations

Compare:

schema-only

schema + synthetic format examples

schema + held-out real exemplars

Track not only accuracy, but also unsupported-value rate, reviewer correction rate, null/missing-value behavior, and Verify-mode score stability.

Open questions

The biggest unresolved question is empirical: how much real uplift do semantic exemplars provide over better schema metadata alone? The literature says examples can help, but also says they can mislead, and the net effect is highly selection-dependent.

A second open question is whether some of your “free text” columns are actually hiding a smaller ontology. If many columns can be re-expressed as enum, boolean, numeric, range, or templated short text, then synthetic format examples plus better schema metadata may recover most of the benefit without using real filled cells.

A third open question is how much of the desired behavior should be expressed in the schema versus the prompt. The systems I reviewed lean heavily toward field descriptions and schema design as the durable control surface.

A fourth open question is product strategy: do you want Verify mode to measure the raw extractor, or the full reviewer-assist system? If it is the former, examples should stay off. If it is the latter, you still need strict support/eval separation and provenance tracking to keep the score trustworthy.

If useful, I can turn this into a shorter decision memo with a recommended prompt/schema design for Paper Table Agent.

However, the examples that are used in the prompt (to clarify format and tone), would never come from the table cells for which a new proposal is made. Because a new extraction is usually mainly done for empty cells. So any examples that exist in cells of a column could be used as examples to instruct format, tone etc, right? Evaluation by making proposals for cells with content will anyway not MVP because this will be hard to do quantitatively without much more complicated systems and more work. 

Your clarification changes the recommendation meaningfully: if examples are only used when filling empty cells, and Verify mode is not MVP, the biggest immediate problem is no longer evaluation leakage but anchoring and semantic drift. I’m checking what the literature and production docs suggest about that narrower setup.

Thought for 1m 49s

Yes — with your clarified scope, using existing filled cells becomes much more defensible.

If proposals are mainly generated for empty cells, and Verify mode / quantitative scoring is not part of MVP, then the biggest objection is no longer evaluation leakage. In that setup, using prior filled cells as format and style cues is a normal few-shot-style pattern: examples are widely used to steer output structure, and current extraction platforms generally emphasize schema/field descriptions plus formatting guidance as the main control surface.

But I still would not jump from that to “therefore any existing cell in the column is safe to use.” The literature on in-context learning shows that demonstrations often influence models through surface form, priors, and shortcuts, not just the intended mapping. Min et al. found that models often benefit from demonstration format even when labels are randomized, and later work on “demonstration shortcut” shows models can lean on semantic priors in the examples rather than the actual evidence in the input. So leakage becomes much less important in your clarified MVP, but anchoring, copying, and semantic drift remain real risks, especially for open-text columns.

So my updated recommendation would be:

For MVP:
Use examples selectively, but treat them as format exemplars, not as general semantic exemplars.

What that means in practice:

Good candidates: booleans, enums, short categorical values, numeric fields, units, ranges, short templated text.

Bad candidates: free-text summaries, mechanism descriptions, interpretation-heavy fields, “conclusion” fields, rationale/argumentation fields.

Even for allowed fields, I would prefer a ladder like this:

Best: derive a column profile from existing cells rather than inserting raw cells.
Example: typical length 1–3 words, usually one of {yes, no, unclear}, common unit µM, range style x–y, null style not reported.

Second-best: use synthetic or canonicalized examples derived from existing cells.
Example: instead of showing “Oct4 was strongly reduced after 48 h”, show “[short effect summary, 4–8 words]” or “decreased”.

Only if needed: use real filled cells, but only for low-semantic fields and with strict safeguards.

That aligns with vendor guidance too: current extraction systems lean heavily on field descriptions / schema design as the main way to improve accuracy, and examples are typically an iterative aid rather than the primary source of truth.

The main rule I’d use is:

Use existing cells to teach shape, never to teach substance.

Concretely, if you do use raw examples from the column, I’d require these safeguards:

show at most 2–3 examples

choose examples that are diverse but structurally representative

exclude examples from the same target row

clearly label them in the prompt as
“Examples of expected output format/style only. Do not copy their content. Use only evidence from the current PDF.”

require null / not found when the paper does not support a value

require a supporting quote/page/evidence object for every proposal

disable examples for open-ended text fields

log which examples were shown for each extraction, so you can audit later

So the answer to your “right?” is:

Mostly yes, but only for certain column types and only with safeguards.
Given your clarified MVP, I would now recommend:

schema + field description first

column-profile / synthetic format hints second

real same-column examples only for low-risk field types

no real examples for interpretation-heavy text columns

That is a materially more permissive recommendation than my earlier one, because your clarification removes the biggest immediate evaluation problem. The remaining question is not “is this invalid?” but “how much semantic anchoring are you willing to tolerate for the convenience gain?” And for MVP, the safest answer is: allow it narrowly, not universally.

I can turn this into a concrete prompt/schema design, with a decision table for which column types may use examples and which must not.

Could we prompt an llm model to look at all existing content for a column and create a format instruction? So in cases where a column contains long text, instead of using all these cell entries as examples have a llm model summarize the format/tone/style/detail etc, so that this can go into the prompt for the llm model which then tries to extract the relevant information and outputs it with the desired format/tone/style/detail.

I’m checking whether there’s solid support for “summarize the column into an output-style spec” rather than passing raw examples. My expectation is that this will be safer than raw exemplars, but only if the summary is constrained to style and not allowed to smuggle likely content.

Thought for 28s

Yes — that is a strong idea, and in your setting it is probably better than passing raw cell examples, especially for long-text columns.

The reason is that official prompting guidance consistently treats examples as a way to control format, structure, and style, while extraction platforms put most of the weight on schema and field descriptions. OpenAI explicitly recommends example outputs for showing the desired response shape, Anthropic recommends examples for output control and structured prompts, and LlamaExtract emphasizes detailed field descriptions as a core driver of extraction quality.

At the same time, research on in-context learning suggests that raw examples can influence models through surface form and semantic priors, not only through the intended task. Min et al. found that models often benefit from the label space and format of demonstrations even when the labels themselves are randomized, and Jang et al. describe a “demonstration shortcut,” where the model leans on priors from the demonstrations instead of learning the intended mapping from input to output.

So the safer design is:

Recommended pattern

Use a two-step pipeline.

Step 1: build a column style spec

Run an LLM once over the existing non-empty cells in a column and ask it to produce a format instruction, not examples. That output should describe things like:

typical answer length

whether answers are sentence fragments, full sentences, or multi-sentence summaries

whether they are extractive, paraphrased, or interpretive

preferred level of detail

whether units, abbreviations, gene symbols, or statistical notation are usually preserved

null / missing-value style

whether the column tends to contain one fact, a compact summary, or a mini-argument

This is a good fit for prompt chaining, which Anthropic explicitly recommends for decomposing a complex task into stages with checks on intermediate outputs.

Step 2: use that style spec during extraction

Then pass the extractor a prompt like:

Column description: ...
Output style profile: ...
Extract the value from the current PDF only.
Use the style profile only for formatting/detail level.
Do not infer content from prior rows.
If the paper does not support a value, return null / not reported.

That keeps the model focused on the current paper while still giving it guidance on the expected output shape. Structured-output guidance from Google and Gemini also supports this general pattern: constrain the output with schema and return null when unsupported.

Why this is better than raw examples

A style/profile summary has three advantages.

First, it is lighter. You do not need to stuff many long cells into the prompt.
Second, it is safer. It reduces the chance that the model copies phrasing or semantic content from prior rows.
Third, it is more reusable. You can cache one style profile per column and reuse it across many extraction runs. This matches the general guidance to iterate on prompt structure and schema rather than overloading the model with lots of raw demonstrations.

The main danger

Yes, there is still one important risk: the “style summary” itself can accidentally become a semantic prior.

For example, if the summarizer says:

“This column usually contains brief mechanistic statements about transcriptional repression”

that may bias the extractor toward producing repression-like content even when the current paper supports activation or something else.

So the column-summary prompt should be strictly limited to output-shape properties, not topical tendencies.

What the summary should and should not contain
Good

“Usually 1 sentence”

“Usually 10–25 words”

“Uses compact scientific prose”

“Preserves gene/protein symbols”

“Includes units when available”

“Avoids speculation”

“Returns ‘not reported’ when absent”

Bad

“Usually says the treatment increases expression”

“Often mentions apoptosis”

“These papers tend to report mouse data”

“Most rows describe inhibitory effects”

Those are no longer format cues; they are semantic cues.

Best version for long-text columns

For long-text columns, I would ask the first LLM to output a structured style card, something like:

length_target: short / medium / long

typical_word_range: 15–40

voice: neutral scientific

granularity: one main claim plus one qualifier

allowed_inference_level: low

preferred_structure: effect → target → condition

terminology_policy: preserve domain terms from source

missing_value_policy: "not reported"

forbidden_behavior: do not copy themes/content from prior rows

That is much safer than feeding 10 previous long free-text cells into the extraction prompt.

My recommendation for Paper Table Agent

For MVP, I would do this:

For each column, generate a cached style/format profile from existing filled cells.

Store that profile as metadata next to the schema.

Use it during extraction as a format-only instruction.

Keep a hard rule in the prompt: content must come only from the current PDF evidence.

For long-text columns, never pass many raw cell examples unless you later prove they help.

So the answer is: yes, absolutely — and this is probably the safer version of the idea.

The only important caveat is that the “format instruction generator” must be explicitly prevented from summarizing the meaning of the column contents. It should summarize only how answers are written, not what they usually say.

A good one-line product rule would be:

Summarize prior cells into a style spec, not a semantic prior.

I can draft the exact prompt for both stages next: one prompt that generates the column style profile, and one extraction prompt that consumes it.