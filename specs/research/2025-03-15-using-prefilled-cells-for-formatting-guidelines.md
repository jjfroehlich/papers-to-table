Please research the best implementation design for using existing filled spreadsheet cells as **format/style guidance only** in Paper Table Agent.

## Context

We do not want to use existing filled cells as free-form semantic few-shot examples by default.

However, we may want to use them to infer:
- expected output length
- numeric vs short categorical vs long text
- common formatting conventions
- unit style
- whether the column is usually terse or argumentative

We need a safer design that preserves these benefits while avoiding:
- hallucination
- anchoring bias
- copying irrelevant semantics
- Verify-mode evaluation leakage

## Research questions

1. What is the safest way to derive format/style guidance from existing entries?
2. Which field types are low-risk enough for this in MVP?
3. Should this guidance be:
   - heuristic/rule-based
   - LLM-generated summary
   - hybrid
4. How should Verify-mode leakage be prevented?
5. Should format/style guidance be disabled entirely for some field types, especially long free-text fields?

## Deliverables

Please produce a structured markdown report with:
- Executive summary
- Candidate implementation designs
- Risk comparison
- Recommended MVP approach
- Field-type-specific recommendations
- Leakage safeguards
- Open questions

## Constraints

- We want a practical design, not academic elegance only.
- Content must remain grounded in the current PDF.
- Please include citations/links where helpful.

I’m pulling together a practical design that stays grounded in the PDF while still getting style benefits from existing spreadsheet content. I’m checking both implementation-oriented sources and evaluation/data-leakage guidance so the recommendation is safe, not just elegant.

I’ve got the main shape of the recommendation now: a “format profile” approach is looking much safer than passing raw filled cells into the extraction prompt. I’m checking one more set of sources on output contracts and prompt separation so I can make the MVP recommendation concrete rather than hand-wavy.

Thought for 3m 2s
Paper Table Agent — format/style guidance from existing filled spreadsheet cells
Executive summary

The safest design is to treat existing filled cells as a source of a column format profile, not as in-context semantic examples. In practice, that means deriving a compact artifact such as “usually 1–2 tokens,” “fragment not sentence,” “1 decimal place,” “unit style = µM,” or “date format = YYYY-MM-DD,” then feeding that artifact into extraction as a bounded policy variable. This matches current prompt-engineering guidance to use clear structure, explicit scope, and small stable output contracts, and it avoids letting raw examples steer the model toward unintended patterns.

For MVP, the best choice is a heuristic-first hybrid: build the format profile with deterministic rules, keep extraction grounded only in the current PDF, and apply the profile mainly in a second formatting step after evidence-based extraction. Use LLM-generated style summaries only as an experimental extension, not as the default path. This keeps the system interpretable, easier to debug, and much easier to keep leakage-free in Verify mode.

In Verify mode, leakage prevention should follow the same discipline used in ML preprocessing: split first, fit the profile only on the non-eval subset, then transform the eval subset with the frozen profile artifact. Scikit-learn explicitly warns that learning preprocessing on all data, including the test set, creates optimistic bias; the same logic applies here.

Candidate implementation designs
1) Raw filled cells as few-shot examples in the extraction prompt

This is the highest-risk option. Few-shot examples are indeed powerful for steering format, tone, and structure, but they also create the strongest anchoring pressure, and Anthropic explicitly recommends examples be relevant, diverse, and structured so the model does not absorb unintended patterns. In your setting, the “unintended pattern” is exactly the problem: the model may copy column semantics, preferred phrasings, or default values rather than staying grounded in the PDF.

Verdict: do not use this as the default.

2) Rule-based column format profile

This design profiles filled cells with deterministic rules and emits a compact schema such as length bands, sentence-vs-fragment, capitalization, punctuation, numeric precision, unit spelling, list separator, date format, and boolean spelling. That is much safer because the artifact contains surface-form constraints, not semantic exemplars. It also aligns well with the recommendation to keep prompts and output contracts clear, structured, and stable.

Verdict: best MVP default.

3) LLM-generated style summary from existing entries

This can be useful later because an LLM can compress patterns that are awkward to hand-code, such as “usually terse, noun-phrase style, not argumentative.” But it is riskier because the model may smuggle semantics into the summary unless the summary is tightly schema-constrained. If you ever use this, it should output a small fixed JSON object rather than free prose, because structured outputs reduce formatting drift and make invalid fields detectable.

Verdict: promising future enhancement, not the safest MVP default.

4) Two-step extraction then formatting

This is the strongest overall design. First extract a canonical value plus evidence from the PDF with no semantic help from existing cells. Then run a second step that formats the already-extracted value according to the column format profile. This preserves grounding while still giving you style consistency. It also keeps failure modes legible: if the answer is wrong, the extractor failed; if the answer is right but rendered badly, the formatter failed.

Verdict: best recommended architecture.

Risk comparison
Design	Grounding risk	Leakage risk	Auditability	MVP complexity	Recommendation
Raw cell few-shot examples	High	High	Low	Low	Reject by default
Rule-based profile only	Low	Low	High	Low	Best MVP choice
LLM style summary only	Medium	Medium/High	Medium	Medium	Experimental only
Two-step extraction + formatting with rule-based profile	Low	Low	High	Medium	Best overall design
Two-step + optional LLM style formatter for select fields	Low/Medium	Medium	Medium	Medium/High	Later extension

The ranking above follows directly from three source-backed principles: examples are powerful but can transmit unintended patterns; prompt sections should be explicitly separated and scoped; and preprocessing-like transforms must not be fit on evaluation data.

Recommended MVP approach
A. Build a column_format_profile artifact, not example prompts

For each column, compute a small structured profile from eligible filled cells:

field_type_guess: numeric, numeric_with_unit, boolean, date, short_category, short_text, long_text, list_text

length_stats: median chars, median tokens, 10th/90th percentile

sentence_mode: fragment / single_sentence / multi_sentence

punctuation_style: trailing period yes/no, comma frequency, semicolon list yes/no

capitalization_style: lower / title / sentence / mixed

numeric_style: decimal places, percent style, range delimiter, thousands separator

unit_style: observed unit tokens and canonical spelling

date_style: ISO / DD.MM.YYYY / Month Year / year only

list_style: separator token, spaces after separator

guidance_strength: strong / weak / disabled

This is the right abstraction boundary: it captures formatting regularities without carrying example content into the extraction prompt. Data-profiling systems are commonly used precisely to surface structural patterns and validate how data behaves over time.

B. Keep extraction content-only and PDF-grounded

The extractor prompt should treat the PDF as the only truth source and the format profile as a post-hoc rendering constraint. Anthropic’s guidance for document-heavy tasks is especially relevant here: separate prompt components clearly, and ground the model in quoted evidence from the source documents before completing the task.

A good prompt structure is:

<instructions>
Extract the target value only from the current PDF.
Use <format_profile> only to choose surface form after you have determined the answer from evidence.
Do not infer facts from the format profile.
If the PDF does not support a value, return null.
If evidence conflicts with the format profile, evidence wins.
</instructions>

<format_profile>
...structured JSON-like profile...
</format_profile>

<pdf_evidence>
...retrieved text / page quote / figure context...
</pdf_evidence>

<output_contract>
{
  "canonical_value": "...",
  "formatted_value": "...",
  "evidence_quotes": [...],
  "confidence": 0-1
}
</output_contract>

This follows current guidance to separate instructions, context, and variable inputs with explicit structure, and to keep the output contract small and stable.

C. Apply the profile mainly in a second formatting step

For MVP, use a two-step pipeline:

Extractor: derive canonical_value from the PDF.

Formatter: render that value into the column’s preferred style.

For numeric, date, boolean, and controlled categorical fields, the formatter should usually be deterministic. Only short text fields may need a model-assisted formatter, and even there the formatter should operate on the extracted value, not on the PDF search process. This is the cleanest way to preserve grounding.

D. Use structured outputs everywhere the model writes guidance artifacts

If you later add an LLM-based style summarizer or formatter, force it to emit a JSON schema, not free prose. OpenAI’s Structured Outputs and Microsoft’s “small, stable output contract” guidance are directly applicable here.

What should and should not be derived from existing entries
Safe to derive

These are mostly surface-form features and are appropriate for MVP:

typical length band

fragment vs sentence vs paragraph

decimal precision

unit token spelling

percent/range/date formatting

boolean spellings (yes/no, true/false, +/-)

list separator conventions

trailing punctuation and capitalization conventions

These are formatting features, not semantic exemplars, and are the lowest-risk way to get style consistency.

Do not derive or pass through in MVP

These materially raise bias and leakage risk:

raw example cells

top n-grams or common phrases

full sample sentences

“most common answer” for a column

latent semantic summaries such as “usually says treatment improves viability”

any examples from the target row or Verify-mode eval subset

Those items blur style into content and make optimistic evaluation much more likely.

Field-type-specific recommendations
Field type	MVP guidance	How to implement	Recommendation
Numeric	Full guidance	deterministic precision, separators, sign handling	Enable
Numeric + unit	Full guidance	deterministic numeric formatting plus allowed unit spellings	Enable
Boolean	Full guidance	fixed spelling map	Enable
Date / year	Full guidance	deterministic date renderer	Enable
Short controlled categorical	Moderate guidance	normalize to allowed spellings; avoid learning “default class”	Enable
Short text labels / identifiers	Light guidance	only length, casing, punctuation; no semantic exemplars	Enable cautiously
List-like text	Moderate guidance	separator and spacing rules only	Enable cautiously
Long free text / narrative	Minimal or none	maybe only max length band or sentence-count cap	Disable by default
Argumentative / interpretive text	None	keep fully PDF-grounded and reviewer-edited	Disable
Derived/calculated text explanations	None for extraction; maybe light post-formatting	extract canonically, then lightly polish if needed	Mostly disable

The practical cutoff is simple: the more a field’s “style” is entangled with its meaning, the less suitable it is for style guidance. That is why numeric and date fields are low-risk, while long narrative fields are high-risk. This also aligns with the general recommendation to start with simpler, well-bounded flows before adding more complex model behavior.

Leakage safeguards
1. Split first, profile second

In Verify mode, first define the eval subset, then build format profiles only on the non-eval rows. This is the exact analogue of fitting preprocessing on train data only and transforming test data afterward.

2. Exclude the target row from profile generation

Even outside formal eval, never let the target row’s filled value contribute to its own profile. If rows correspond to papers, exclude at least the row; if multiple rows can come from the same paper, exclude by paper/document ID. This is the conservative boundary.

3. Freeze the profile artifact per run

A run should read a precomputed column_format_profile artifact, not recompute it on the fly from all current table contents. That makes runs reproducible and auditable.

4. No online learning during Verify-mode runs

Do not update profiles from accepted proposals or reviewer edits during the same evaluation run. Otherwise the system gradually “sees” the answers.

5. Keep style guidance separate from evidence

Use explicit prompt sections such as <format_profile> and <pdf_evidence>, and state that evidence overrides style. Clear separation of scope reduces misinterpretation.

6. Prefer deterministic guidance in Verify mode

If you include any LLM-based style summary later, keep it off in Verify mode initially. The cleanest eval baseline is deterministic profiling only.

7. Run ablations

Measure at least three settings: no guidance, heuristic profile only, and heuristic profile plus any experimental LLM summary. That will tell you whether style guidance is actually helping rather than just making outputs look more “on-brand.”

Recommended MVP decision

Use this product boundary:

Default behavior

Build a deterministic column_format_profile from existing filled cells.

Use it only as format/style guidance, never as semantic examples.

Apply it mainly in a post-extraction formatting step.

Enable it for numeric, date, boolean, and short controlled categorical columns.

Allow only very light guidance for short text.

Disable it for long free-text and argumentative fields.

Explicitly out of scope for MVP

raw example cells in prompts

free-prose LLM style summaries from existing content

guidance derived from the Verify-mode eval subset

style transfer for long narrative fields

That is the safest practical design for Paper Table Agent’s current goals.

Open questions

Where should the cutoff between “short text” and “long free text” sit in practice: token count, sentence count, or reviewer-configured per column?

Should some columns declare their allowed rendering rules directly in schema metadata, so no inference from filled cells is needed at all?

Is there enough UX benefit from an LLM-generated style summarizer to justify the added leakage and debugging risk for short-text columns?

Should accepted reviewer edits update column profiles outside evaluation runs, or should profiles remain static until explicitly rebuilt?

Would a dedicated formatter model materially improve user satisfaction over deterministic formatting for short text, or is reviewer editing sufficient?

The answer I would use for MVP is conservative: solve the high-confidence formatting wins first, and only add model-based style inference where deterministic profiling demonstrably falls short.