
Research how other projects evaluate LLM-based extraction systems and propose a recommendation for Paper Table Agent’s **verify-mode evaluation score**.

Please research how other projects evaluate LLM-based extraction systems and propose a recommendation for Paper Table Agent’s **verify-mode evaluation score**.

## Context

Paper Table Agent extracts structured information from scientific PDFs into spreadsheet cells. In “Verify mode”, it also generates proposals for cells that already contain existing values. These verified cells are then used to evaluate how well the app performed on that run.

The challenge is that our target columns can contain:
- free text
- numeric values
- categorical values
- booleans
- ranges
- values derived through reasoning or calculation
- partially correct answers
- answers that are semantically similar but not string-identical

We want:
- one **overall run score**
- per-column scores
- useful submetrics
- a method that is reasonably trustworthy and interpretable
- a recommendation that is realistic for MVP and extensible later

## Research questions

1. How do existing LLM evaluation systems score structured extraction or answer quality when exact string match is insufficient?
2. How do established projects handle:
   - partial credit
   - numeric tolerance
   - semantic similarity
   - reasoning-derived answers
   - ranges and units
   - free-text fields
3. What evaluation methods are used in:
   - LLM extraction systems
   - information extraction / document extraction tools
   - model evaluation frameworks
   - RAG evaluation systems
   - structured prediction benchmarks
4. When do projects use:
   - exact match
   - normalized match
   - fuzzy/semantic similarity
   - LLM-as-judge
   - task-specific scoring rules
   - hybrid scoring pipelines
5. What are the known failure modes or risks of:
   - LLM-as-judge scoring
   - semantic scoring for extraction
   - collapsing many heterogeneous field types into one overall score
6. What would be the best scoring design for Paper Table Agent’s Verify mode?

## Deliverables

Please produce a report with:

### 1. Short executive summary
- recommended evaluation design for our app
- what should be MVP
- what can be deferred

### 2. Survey of existing approaches
Include concrete examples from current tools, libraries, frameworks, papers, or benchmarks.
For each approach, explain:
- how it works
- what kinds of outputs it suits
- pros/cons
- whether it is appropriate for our use case

### 3. Recommended scoring framework for Paper Table Agent
Please recommend a concrete design for:
- numeric fields
- categorical/boolean fields
- ranges
- free-text fields
- reasoning/calculation-derived fields

Also recommend:
- how to compute per-column scores
- how to aggregate into one overall score
- what auxiliary metrics should be shown alongside the overall score

### 4. Leakage and fairness considerations
Explain how to avoid biased or inflated evaluation, especially when:
- existing table entries may have been used as prompt examples
- the scoring model is also an LLM
- fields vary widely in difficulty

### 5. MVP recommendation
Give a practical MVP recommendation with minimal complexity.

### 6. Later-phase recommendation
Give a better but more complex version for later.

## Constraints

- We are building a local-first human-review app for scientific papers.
- We need a recommendation that is practical, not just academically elegant.
- We want the answer to clearly separate:
  - what is proven or commonly used
  - what is experimental or risky
- Please include concrete citations/links.
- Be explicit when something still needs more research.

## Output format

Return a structured markdown report with headings:
- Executive summary
- Existing evaluation approaches
- Risks and tradeoffs
- Recommended Verify-mode scoring design
- MVP recommendation
- Later improvements
- Open questions

I’m pulling together both benchmark-style metrics and production-oriented evaluation practices, then I’ll turn that into a concrete scoring design for Verify mode.

I’ve got the main families now: exact/overlap metrics from QA, ANLS and entity-F1 from document extraction, semantic/factual metrics from RAG frameworks, and LLM-as-judge from current eval practice. Next I’m filling in the edge cases most relevant to your app: numerics, units, ranges, and partial credit.

Thought for 7m 48s
Executive summary

The best Verify-mode score for Paper Table Agent is a hybrid, type-aware scoring pipeline: use deterministic scorers first for numerics, booleans, categories, ranges, and short extractive text; use LLM-as-judge only for the subset of fields that are genuinely open-ended, such as longer free-text or reasoning-heavy textual outputs. That matches what established systems do in practice: exact match for known labels, precision/recall/F1 for structured extraction, ANLS or similar fuzzy string metrics for OCR/noisy short text, tolerance-based accuracy for numerics, and rubric-based LLM judging only when deterministic matching is insufficient.

For MVP, I would not make an uncalibrated LLM judge part of the headline score. Use a deterministic score for all auto-scorable columns, compute per-column scores, then aggregate those into one weighted macro overall score. Show supporting metrics beside it: micro-average over cells, strict pass rate, parse failure rate, and counts by field type. This is much more trustworthy and interpretable than one universal fuzzy metric or a judge-only score.

What can wait until later is a grounded rubric judge for long free-text and difficult reasoning-derived fields, calibrated on a small human-reviewed set. Current research and framework docs support that direction, but they also show clear risks: position bias, length bias, superficial-style bias, inconsistency between scoring modes, overfitting of fine-tuned judges, and reproducibility/privacy issues with black-box judges.

Existing evaluation approaches
Exact match and overlap metrics

How it works: compare prediction and reference directly, either as exact string equality or as overlap-based metrics such as token F1. SQuAD is the classic example: it reports Exact Match and F1 overlap rather than only exact equality. LangSmith likewise presents exact match as appropriate for known labels and also supports simple code evaluators that do exact equality checks.

What it suits: booleans, enums, closed-label categories, normalized short fields, and many spreadsheet columns where the canonical answer space is small.

Pros: cheap, stable, reproducible, easy to explain.
Cons: brittle for semantically equivalent wording, OCR noise, units, formatting differences, and partial correctness.
Fit for Paper Table Agent: excellent for booleans and canonical categories; only acceptable for text after normalization.

Precision/recall/F1 for structured extraction

How it works: treat extracted fields/entities as predictions and compare them against labeled fields/entities, producing precision, recall, and F1. Google Document AI exposes this style directly for document extraction, both overall and per label, and explicitly notes that plain “accuracy” is often less meaningful when fields are optional or multi-occurrence. In visually rich document benchmarks, FUNSD, SROIE, and CORD are commonly reported with F1, while DocVQA uses ANLS.

What it suits: key-value extraction, repeated fields, multi-occurrence fields, invoice/receipt/form extraction. Google also distinguishes single-occurrence and multi-occurrence labels in matching logic.

Pros: handles missing vs extra predictions cleanly; easy per-label reporting; good for structured extraction.
Cons: less natural for one-cell-one-answer grading unless you still want to track abstentions, extras, or repeated values.
Fit for Paper Table Agent: useful as a supporting metric family for run analysis, especially if Verify mode ever allows abstain/no-answer or multiple candidate values.

Fuzzy string metrics for OCR-like variation

How it works: measure closeness between short strings instead of demanding identity. In DocVQA, the standard metric is ANLS. The common ANLS implementation penalizes OCR-like misspellings softly and uses a threshold at 0.5, below which the match is treated as wrong. Google Document AI also supports exact vs fuzzy matching, with fuzzy rules such as case-folding, whitespace normalization, punctuation trimming, and money-symbol stripping.

What it suits: short extractive text such as assay names, species names, journal abbreviations, short methods, or short field values copied from a PDF.

Pros: better than exact match for OCR noise and formatting variance.
Cons: can over-credit near-matches that are materially wrong; poor for numbers and long text. Google explicitly notes that fuzzy matching does not solve numeric normalization like 1 vs 1.00.
Fit for Paper Table Agent: very good for short free-text fields, but it should not be the only scorer for numerics or long answers.

Numeric-tolerant and reasoning-aware metrics

How it works: use task-specific rules for numeric answers. ChartQA-style evaluation uses Relaxed Accuracy: allow a small numeric error window (commonly 5%) but require exact match for non-numeric answers. ChartQA follow-up work describes this explicitly. TAT-QA uses Exact Match and numeracy-focused F1, and the dataset itself includes scale and derivation alongside answers. ChartQAPro goes further with a hybrid metric: keep a 5% margin for numerics, require exact match for years, and use ANLS for textual answers.

What it suits: measured values, percentages, p-values, fold changes, date-like values, and answers derived by calculation.

Pros: reflects how people judge scientific extraction more realistically than exact string match.
Cons: tolerance choice is domain-dependent; a single tolerance is not valid for every field; fuzzy numeric scoring can hide critical errors.
Fit for Paper Table Agent: essential. Numerics should be scored with column-specific tolerance and unit normalization, not with raw strings.

Semantic, factual, and rubric-based scoring

How it works: score meaning rather than raw surface form. Ragas’ Answer Correctness combines semantic similarity with factual similarity, where factual overlap is computed from TP/FP/FN-style claim comparison. Ragas also exposes separate Semantic Similarity, Factual Correctness, and rubric-based metrics with domain-specific or instance-specific rubrics. LangSmith documents both exact match and reference-based LLM judges for correctness/hallucination-style evaluation. DeepEval’s G-Eval documentation recommends custom criteria for task-specific correctness.

What it suits: longer free text, semantically equivalent paraphrases, rubric-based grading, and answers where factual completeness matters more than wording.

Pros: captures semantic equivalence and partial correctness better than exact string rules.
Cons: embeddings can miss critical scientific errors; LLM judges introduce bias, variance, and calibration work.
Fit for Paper Table Agent: good for a later-phase judge for hard free-text fields, but too risky as the default scorer for all columns.

LLM-as-judge in production systems

How it works: ask a strong model to grade an output against a rubric. G-Eval is a canonical example: it uses CoT-style decomposition and form-filling to improve alignment with human judgments. Anthropic reports using an LLM judge for research outputs with rubric dimensions such as factual accuracy, citation accuracy, completeness, source quality, and tool efficiency; they found that a single LLM call with a single prompt returning 0.0–1.0 scores plus pass/fail aligned best with human judgments in that setting.

What it suits: open-ended outputs with no single exact answer.
Pros: scalable and flexible.
Cons: current research shows position bias, length bias, inconsistency between pointwise and pairwise protocols, superficial-quality bias, and poor robustness of some fine-tuned judges outside their training regime. JudgeBench shows strong judges can still struggle badly on hard judge-specific benchmarks.

Fit for Paper Table Agent: useful only as a restricted fallback for fields that deterministic scorers cannot handle well.

Risks and tradeoffs

A single universal scorer is the wrong shape for your problem. Existing benchmarks already split by answer type: SQuAD uses EM/F1, DocVQA uses ANLS, document IE uses F1, ChartQA uses relaxed accuracy, TAT-QA uses EM plus numeracy-focused F1, and ChartQAPro mixes numeric tolerance, exact-year matching, and ANLS. That pattern strongly suggests Paper Table Agent should also use field-type-specific scoring rules, not one metric for everything.

Semantic scoring can look good while being scientifically wrong. A response can be semantically similar yet flip a species, a sign, a year, a dose, or a unit. Google’s own extraction evaluation docs show that fuzzy matching helps formatting noise but is explicitly unsuitable for numeric normalization like 1 vs 1.00; that is a good reminder that numerics need dedicated parsing and canonicalization.

LLM-as-judge has real reliability risks. Recent work documents position bias, length bias, and broader judge inconsistency; other work finds fine-tuned judges can overfit, favor superficial fluency/verbosity, and fail on aspect-specific evaluation. Closed-source judges also raise reproducibility and privacy concerns. LangSmith’s own guidance therefore includes an explicit alignment loop with human feedback for judge prompts.

Collapsing everything into one overall number can mislead. Google Document AI explicitly notes that plain accuracy is often less meaningful when labels are optional or multi-occurrence, and its metrics are therefore framed through precision/recall/F1. For Paper Table Agent, I infer a related risk: a cell-weighted average can be dominated by easy, frequent columns and hide failures in rare but important fields.

Recommended Verify-mode scoring design
1) Core principle

Use a three-stage scoring pipeline for every verified cell:

Canonicalize prediction and gold.

Dispatch to a type-specific scorer.

Return a normalized cell score in [0,1], plus metadata:

match_type

judge_used

parse_failed

details (for debugging)

This is the design I recommend as the default.

2) Field-type scorers
Numeric fields

Recommended design:

Parse number, sign, scientific notation, percent, and unit.

Convert to a column-level canonical unit where possible.

Compare on the normalized numeric value, not raw string.

Support two thresholds:

strict_tolerance

soft_tolerance

Suggested scoring:

1.0 if equal after normalization or within strict tolerance.

Partial credit between strict and soft tolerance.

0 beyond soft tolerance.

If units are non-convertible or contradictory, score 0.

Keep value correctness and unit correctness visible separately in debug output. This is consistent with the fact that document systems often normalize values before matching, and that chart/table QA benchmarks use answer-type-specific numeric tolerances rather than raw-string equality.

Categorical and boolean fields

Recommended design:

Map both prediction and gold through a column-specific canonical label map.

Support aliases such as yes/true/present/positive or controlled vocab synonyms.

Score 1 for the same canonical label, else 0.

This is where exact or normalized match is strongest and most trustworthy.

Range fields

Recommended design:

Parse lower bound, upper bound, inclusivity, and unit.

Normalize units first.

Score using interval overlap:

exact same normalized interval = 1

otherwise use overlap / union as partial credit

For point-vs-range comparisons, give full credit if the point falls inside the gold range; otherwise use distance to nearest bound.

This is more interpretable than fuzzy string similarity and mirrors how type-specific benchmark metrics handle answer structure.

Free-text fields

Split these into two classes.

Short extractive text
Examples: species, assay, tissue, strain, compound name, short method phrase.

Recommended design:

normalize case, whitespace, punctuation, and optionally domain-specific aliases

then score with an ANLS-style short-string similarity

keep a threshold so near-random strings do not receive credit

This follows the role ANLS plays in DocVQA-like settings.

Longer free text
Examples: reasoned description, effect summary, eligibility text, derived narrative answer.

Recommended design:

use a reference-based, grounded rubric judge

rubric dimensions:

factual equivalence to gold

completeness

no material contradiction / no wrong extra fact

score on a small discrete scale, then normalize to [0,1]

This is where Ragas-style factual + semantic comparison or G-Eval-style rubric judging is appropriate, but only after calibration.

Reasoning / calculation-derived fields

Recommended design:

score the final answer, not the prose reasoning.

if the final answer is numeric, use the numeric scorer.

if categorical, use the category scorer.

if long textual explanation is required, use the grounded rubric judge.

Separately, keep an optional non-headline metric called derivation_support that checks whether the system’s cited evidence or trace supports the answer. TAT-QA’s inclusion of derivation and scale is a good reminder that answer correctness and derivation are related but separable artifacts.

3) Per-column scores

For each column:

column_score = mean(cell_scores for verified cells in that column)

Also store:

n_verified

n_scored

strict_pass_rate

mean_score

score_by_type

judge_usage_rate

parse_failure_rate

This preserves interpretability and lets you see which columns are failing for which reason. It also matches how production tools expose per-label or per-field metrics.

4) One overall run score

I recommend the headline score be:

overall_run_score = weighted mean(per-column scores)

with default equal column weights, plus optional product-defined weights later.

Why this should be the headline:

it avoids easy high-volume columns dominating the score

it is more interpretable to product teams

it respects heterogeneous field difficulty better than a pure micro-average

Alongside it, show a secondary micro-average over cells:
micro_cell_score = mean(all scored verified cells)

That gives you both a stable headline and a volume-sensitive operational metric. The choice of equal column weighting is partly an inference from the same issue Google flags for document extraction: raw accuracy can be misleading when fields differ in frequency and structure.

5) Auxiliary metrics to show beside the score

Show these every run:

verified cells scored / total verified cells

per-column score

overall macro score

overall micro score

strict pass rate

non-empty proposal rate / abstention rate

parse failure rate

judge-invoked rate

mean score by field type

disagreement bucket counts:

exact fail

parse fail

tolerance miss

semantic mismatch

judge fail

This makes the score auditable, not magical.

MVP recommendation

For MVP, keep it simple and conservative:

Use only deterministic scorers in the headline score.

numerics: normalized exact or within column tolerance

booleans/categories: canonical exact

ranges: normalized interval comparison

short text: normalized exact plus ANLS-style short-text similarity

Do not use general LLM judging for the headline score yet.

For long free-text columns, either:

exclude them from the headline score and report them separately, or

mark them “manual-review only” in MVP.

Compute the headline overall as weighted macro over columns, default weight 1 per column.

Show micro-average and strict pass rate alongside the headline.

Predeclare normalization and tolerance rules per column in config, not ad hoc at runtime.

That is the smallest design that is still trustworthy. It is also consistent with the most established evaluation practices: deterministic where possible, typed scoring rules for numerics/text, and no LLM judge unless needed.

Later improvements

Later, I would add a second layer:

a grounded LLM judge for long free-text and difficult reasoning-derived text fields, using gold answer + paper evidence + rubric

a human-calibration loop for that judge, similar to LangSmith’s alignment workflow

judge version pinning and stored prompts for reproducibility

optional repeat judging / ensemble judging only on ambiguous cases

bootstrap confidence intervals for per-column and overall scores

per-column difficulty weights if product priorities require them

separate metrics for answer correctness vs evidence support vs format compliance.

Open questions

Default numeric tolerances still need product-specific calibration. Benchmarks show tolerance is useful, but they also show it must be task-specific. A blanket 5% rule is probably too coarse for scientific extraction.

Which free-text columns belong in the headline score needs a product decision. Short extractive phrases are fine; long scientific summaries likely need a calibrated judge or manual review.

Column weighting should be decided explicitly: equal per column is the best default for interpretability, but product-critical fields may deserve higher weights later. This is a design choice, not something the literature settles for you.

Judge calibration on your own domain still needs empirical work. Current frameworks support it, and current judge research makes it clear it matters.

My recommendation in one sentence: build Verify-mode around deterministic, type-aware cell scorers first; aggregate by column for the headline score; treat LLM judging as a later, calibrated fallback for the small set of fields that truly need it.

Okay, it seems that any form of automated quantitative eval score would require a lot of extra work and complex setup. Maybe it is better to keep this for a future possible feature. For now we could maybe simply have a statistic of how many of the proposals the human reviewer accepted, this should provide a good metric comparing the app's performance with a human expert reviewer. 

I’m checking whether “accepted by the human reviewer” is a solid product metric in comparable AI systems, and what blind spots it has so we can turn it into a sane MVP definition.

Thought for 1m 7s

Yes — that is a much better MVP metric.

A simple human-review acceptance metric is practical, interpretable, and directly tied to product value. In other AI products, acceptance rate is commonly used as a usefulness/trust signal: GitHub documents acceptance rate as how often users accept suggestions, interpreting it as a measure of relevance and trust/usefulness, while also warning that workflow friction can affect it. Human-in-the-loop document systems also commonly center review workflows around approve / reject / correct actions and report approval rates, review counts, and processing time.

The important nuance is this:

Acceptance rate is a great product metric, but not a pure accuracy metric.
It tells you how often the system produced something a reviewer was willing to keep, not whether the model was objectively “correct.” That is still very useful for Paper Table Agent.

What I would recommend

Do not use just one “accepted proposals / all proposals” number.

Instead, track these separately:

Accepted as-is rate = accepted without changes / reviewed proposals

Accepted with edit rate = accepted after reviewer changed something / reviewed proposals

Rejected rate = rejected / reviewed proposals

Median review time per proposal

Coverage = how many cells received a proposal at all

This matters because acceptance alone can be misleading if reviewers often “accept” proposals only after heavy editing. GitLab makes exactly this criticism for AI acceptance metrics: a suggestion may be accepted initially but still require substantial rewrite, so raw acceptance alone is only a proxy.

For your app, I would define the main MVP KPI as

Accepted as-is rate

and show beside it:

accepted with edit

rejected

median review time

That gives you a clean interpretation:

accepted as-is = the app was genuinely right/useful

accepted with edit = the app was helpful but imperfect

rejected = not useful

review time = cost to the expert reviewer

Why this is better than an automated Verify score for now

Because it is:

cheap to implement

easy to explain

grounded in actual expert judgment

useful across heterogeneous field types

not blocked on numeric tolerances, semantic scoring, or LLM-as-judge calibration

Important caveats

You should treat this as a workflow-performance metric, not a scientific benchmark.

It can be biased by:

reviewer strictness

UI design

whether “accept with edit” is easier than reject

proposal type mix

field difficulty mix

So for fair comparisons, compare runs only when the setup is similar:

same reviewer or reviewer pool

same schema/column mix

same app version/UI

similar paper set

One extra thing I strongly recommend

Break the metrics down by:

column

field type (numeric, categorical, free text)

support type (directly supported vs inferred)

evidence source (text vs figure)

That will make the metric actually actionable.

For example, you might learn:

numeric direct text proposals are accepted as-is 88%

inferred free-text proposals are accepted as-is 32%

figure-derived values are mostly accepted with edit

That is much more useful than one global number.

My practical recommendation

For MVP, use this dashboard:

Accepted as-is

Accepted with edit

Rejected

Median review time

Per-column breakdown

And label the headline clearly as something like:

Reviewer acceptance metrics
not
Model accuracy

I think that is the right decision for where the product is now.