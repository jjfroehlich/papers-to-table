Please research how Paper Table Agent should monitor and evaluate the quality of figure-derived proposals separately from text/table-derived proposals.

## Context

Current product direction includes:
- figure-aware fallback in MVP
- all figure types are in scope
- figure-derived proposals remain subject to human review
- we want to know whether figure fallback is actually helping

We need a way to measure and monitor figure-derived proposals separately.

## Research questions

1. What metrics should we track separately for figure-derived proposals?
2. How should figure-derived proposal quality be compared against text/table-derived proposals?
3. What human-review metrics would be most useful here?
4. Should figure classes (chart, diagram, microscopy, etc.) be tracked separately?
5. What warning signals would show that broad figure scope is too ambitious for MVP?

## Deliverables

Please produce a structured markdown report with:
- Executive summary
- Candidate metrics
- Recommended MVP monitoring design
- Recommended breakdown by figure type if relevant
- Warning thresholds or red flags
- Later improvements
- Open questions

## Constraints

- We care about practical product monitoring, not only model benchmarking.
- We already rely on human review, so reviewer outcome metrics are acceptable.
- Please include citations/links where possible.

I’m pulling together a practical monitoring scheme rather than a research-benchmark scheme: outcome rates, reviewer burden, abstention behavior, and failure segmentation by figure class.

I have enough to make this concrete. The main pattern emerging is: treat figure-derived proposals as a separate “assistance lane” with its own acceptance, edit-burden, and reviewer-friction metrics, and compare it to text/table proposals only after stratifying by difficulty.

Thought for 2m 15s
Paper Table Agent — Monitoring figure-derived proposal quality
Executive summary

Yes — Paper Table Agent should monitor figure-derived proposals as a distinct lane from day one, rather than folding them into overall extraction metrics. The right MVP question is not “How accurate is vision?” in the abstract, but “When the system falls back to figures, does that create enough accepted, low-friction, reviewer-trustworthy proposals to justify the extra complexity?” Human review is an appropriate primary signal for this, especially early on: deployed agentic systems still rely heavily on human verification, and major vendors explicitly recommend using confidence/history-based routing plus human review for uncertain cases or random samples.

For MVP, the core metrics should be reviewer-outcome and reviewer-effort metrics, tracked separately for figure, text/table, and mixed evidence modes. The most useful ones are: accept-as-is rate, accept-with-edit rate, reject rate, defer/manual-only rate, median review time, evidence-open rate, and edit burden. These tell you not only whether figure fallback is “right,” but whether it is cheap enough to review to be worth keeping.

Comparisons against text/table-derived proposals should not rely mainly on raw global averages, because figure fallback will usually be used on harder cells. The best MVP comparison is twofold: first, compare within matched slices such as column type and proposal difficulty; second, measure the incremental yield of figure fallback on cells that text/table extraction did not fill. That gives you both a quality view and a product-value view. This is an inference from the product setup, but it fits the broader recommendation to evaluate systems against task-specific objectives rather than generic benchmarks.

Yes, figure classes should be tracked separately, but the MVP taxonomy should stay small. That is because “figure understanding” is not one problem: current multimodal systems show different capabilities on charts, scientific diagrams, and microscopy-like imagery, and the research ecosystem now benchmarks these as distinct tasks.

Candidate metrics
1) Volume and coverage metrics

These answer: How often is figure fallback being used, and where?

figure_proposal_count

figure_proposal_share = figure-derived proposals / all proposals

figure_reviewed_share

figure_only_fill_count = accepted figure proposals for cells that otherwise had no accepted text/table proposal

figure_no_proposal_rate on cells where figure fallback was attempted

figure_mixed_evidence_share for proposals using figure + caption/text together

These are useful because figure fallback can be high effort but low value. If it produces few accepted fills, it may be too ambitious for MVP.

2) Reviewer outcome metrics

These should be the primary MVP quality signals.

accept_as_is_rate

accept_with_edit_rate

reject_rate

defer_or_manual_only_rate

withdrawn_before_review_rate if the system suppresses weak proposals later

Human validation is a sensible primary grader early in production, and agent eval guidance from OpenAI and Anthropic explicitly treats human grading as part of practical evaluation.

3) Reviewer effort / friction metrics

These answer: Even if figure proposals are useful, are they too expensive to review?

median_review_time_sec

p90_review_time_sec

evidence_open_rate = reviewer opened figure crop/full page/caption

multi_navigation_rate = reviewer had to jump across multiple pages/panels

reopen_rate = reviewer revisited proposal after initial decision

bulk_accept_eligibility_rate for figure proposals, if ever allowed later

This matters because oversight quality is not just about approval chains; it depends on giving users trustworthy visibility and simple intervention.

4) Edit-burden metrics

These are especially important because a proposal that is usually “close but not right” can look good in simple acceptance stats.

Track by field type:

For short text / categorical fields:

edited_accept_share

normalized string edit distance

For numeric fields:

absolute delta

relative delta

unit_correction_rate

decimal_or_scale_fix_rate

For long text:

major_rewrite_rate rather than character distance

A healthy figure lane should not just be accepted; it should avoid frequent unit fixes, scale fixes, and major rewrites.

5) Evidence quality / failure-tag metrics

For every rejected or heavily edited figure proposal, require one reviewer-selected failure code:

wrong figure chosen

wrong panel within figure

crop unusable

caption/context insufficient

visual interpretation wrong

OCR/text-in-figure wrong

units/legend misread

value inferred too aggressively

evidence exists only in text/table, not figure

unsupported / hallucinated

This gives you operational diagnosis, not just scorekeeping. It also aligns with the general recommendation to use human oversight to uncover edge cases and improve the eval loop.

6) Audit metrics on sampled accepted proposals

Do not rely only on first-pass reviewer outcomes. Sample a subset of accepted figure-derived proposals for second review.

Track:

audited precision on accepted figure proposals

second-review overturn rate

reviewer agreement on accept/reject

agreement on failure tags

For agreement, use Cohen’s kappa or another proper inter-annotator agreement metric rather than raw percent agreement alone. Percent agreement is easy to understand, but kappa adjusts for chance agreement and is generally more robust.

7) Calibration / triage metrics

If the system exposes a confidence score for figure proposals, track:

confidence bucket vs actual accept rate

confidence bucket vs reject rate

confidence bucket vs major-edit rate

confidence bucket vs review time

Cloud guidance is consistent here: thresholds for bypassing or routing to review should be set from historical error behavior on your own data, not guessed upfront. Low-confidence and random-sample review are both recommended patterns.

Recommended MVP monitoring design
Recommended evidence-mode taxonomy

Every proposal should carry:

evidence_mode: text_table | figure | mixed

fallback_stage: primary | fallback

figure_class: nullable

review_outcome

review_time_sec

edit_burden

failure_code

confidence if available

The important product distinction is not only “came from a figure,” but also whether the figure was fallback after text/table failed.

Recommended dashboards
A. Figure lane health dashboard

Track weekly:

proposal count

accept-as-is / accept-with-edit / reject / defer

review time median and p90

edit-burden distribution

top failure codes

share of all accepted fills contributed by figures

B. Comparative dashboard

Show figure, text_table, and mixed side by side for:

accept rate

edited-accept rate

review time

evidence-open rate

sampled audited precision

C. Incremental value dashboard

This is the most product-relevant view:

cells newly filled only because of figure fallback

share of those accepted

reviewer time spent per accepted figure-only fill

That last metric is especially valuable for deciding whether broad figure scope is worth it.

Comparison method: do not compare only raw averages

Use three views:

Raw global comparison
Good for trend monitoring, but not decision-making.

Matched-slice comparison
Compare figure vs text/table within the same:

column

field type

paper/source cohort

proposal complexity bucket

Incremental fallback comparison
On cells where text/table produced nothing usable, measure whether figure fallback adds accepted value at acceptable review cost.

This is the fairest way to judge figure fallback, because otherwise it gets penalized for handling harder cases.

Sampling policy

Route to review:

all figure-derived proposals in MVP

plus a random audit sample of accepted figure proposals for second review

That mirrors standard human-review guidance from document-AI systems, which recommend review for low-confidence cases and random sampling for QA.

Reviewer UI instrumentation to add in MVP

Log these quietly in the review UI:

opened crop?

opened full page?

opened caption/context?

changed value?

changed units?

changed evidence type?

selected failure code?

requested manual extraction?

Without this instrumentation, you will know outcomes but not why the figure lane is expensive or weak.

Recommended breakdown by figure type

Yes, track figure classes separately. Keep the first taxonomy small:

MVP figure classes

Chart / quantitative plot
Bar, line, scatter, box, Kaplan–Meier, heatmap with quantitative reading, etc.

Diagram / schematic
Mechanistic cartoons, workflows, pathway diagrams, annotated schematics.

Image-based scientific figure
Microscopy, pathology, photos, imaging panels.

Composite / mixed / other
Multi-panel figures with heterogeneous content, or cases the classifier cannot place confidently.

Optional life-science extension

If Paper Table Agent is used heavily on biology papers, add later:

gel_blot_assay

microscopy

chart_quantitative

schematic

composite

Why split at all? Because current multimodal scientific understanding is heterogeneous: charts are now treated as a distinct benchmark family; microscopy requires specialist reasoning; and broader scientific-image understanding remains difficult for current models.

Recommended rule

Do not start with 10+ figure classes. Start with 4 broad buckets, then split only when:

one bucket has enough volume, and

its failure modes are meaningfully distinct.

Warning thresholds and red flags

These are starting thresholds, not universal truths. They should be tuned with local history, as official guidance recommends.

Strong red flags

Figure accept rate is >20 percentage points below matched text/table accept rate for two consecutive review windows.

More than half of accepted figure proposals require edits.

Median figure review time is >2× text/table review time in matched slices.

Wrong figure / wrong panel / unsupported inference accounts for >25% of figure rejections.

Figure fallback contributes <10% of accepted fills but consumes >25% of review time.

Second-review overturn rate on accepted figure proposals exceeds ~10%.

One figure class is responsible for most figure rejects and near-zero accepted fills.

Reviewers frequently open full-page evidence because crops are insufficient, suggesting evidence presentation is broken rather than model quality alone.

Strategic red flags for “broad figure scope is too ambitious”

The proposal mix shifts heavily toward mixed or figure, but accepted output does not rise.

Failure tags cluster around “visual interpretation wrong” rather than “minor formatting,” meaning the model is not just noisy but fundamentally misreading figures.

Reviewer trust drops: many proposals are rejected after evidence inspection, or reviewers increasingly bypass figure proposals.

Audit samples reveal that first-pass acceptance is too optimistic.

A useful decision rule

If figure fallback does not produce a meaningful number of accepted figure-only fills at a reasonable reviewer-time cost after an initial pilot, narrow scope quickly to the best-performing figure classes rather than keeping “all figures” equally enabled.

Later improvements
1) Small gold-set offline eval for figures

After MVP, build a small audited set of cells whose truth comes primarily from figures. Then measure field-type-aware accuracy offline. OpenAI recommends use-case-specific evals over generic benchmarks, and recent extraction work is moving toward structured PDF-to-JSON evaluation frameworks.

2) Multi-grader evaluation

Anthropic’s guidance is to combine code-based, model-based, and human graders. For Paper Table Agent, that could become:

code-based checks for units/ranges/schema validity

model-based evidence checks on sampled cases

human review as final arbiter

3) Figure-specific confidence calibration

Maintain separate calibration curves for figure and text_table. Do not assume a shared confidence scale is meaningful.

4) Better reviewer-quality measurement

Use double review on a small sample and report kappa, not only acceptance rates.

5) Competitive overlap testing

Create a special evaluation set where both text/table and figure evidence are available, then compare which lane produces better proposals for the same cells.

6) Class-specific handling

Use specialized logic for charts before attempting broader scientific-image interpretation. This is justified by the very different benchmark/task structure emerging for charts vs microscopy vs general scientific figures.

7) Bias-resistant review workflows

Be careful with assisted-review designs. Research shows reviewers can anchor strongly on model suggestions, which can distort evaluation and make systems look better than they are.

Open questions

What exactly counts as figure-derived?
If the system uses the figure plus its caption plus nearby body text, should that be figure or mixed? I recommend keeping mixed as a first-class label.

Should the reviewer see the model proposal immediately, or first inspect evidence?
There is a tradeoff between speed and anchoring bias. The literature suggests suggestion exposure can distort human labels.

What review-time premium is acceptable?
This is a product decision, not just a model-quality decision. For example, a slower figure lane may still be worth it if it uniquely fills high-value cells.

Should bulk acceptance ever be allowed for figures?
My recommendation for MVP is no, unless limited to a very strong sub-class with excellent audited precision.

How should difficulty be estimated for matched comparisons?
Column type and fallback stage are easy. A better later proxy might include whether text/table evidence was absent, ambiguous, or conflicting.

Recommended MVP decision

Adopt this rule set:

Track figure-derived proposals separately from day one.

Use reviewer outcomes + reviewer effort + sampled audit precision as the MVP monitoring backbone.

Compare figure vs text/table within matched slices, not just globally.

Track a small figure taxonomy from the start.

Judge success primarily by incremental accepted fills per reviewer minute, not by raw proposal count.

That gives Paper Table Agent a realistic way to learn whether figure fallback is helping, where it helps, and when to narrow scope.