# Automated Evaluation Metric for a Scientific Paper-to-Table Extraction App

## Executive summary

A trustworthy automated eval for your app should **separate “answer correctness” from “evidence quality”** rather than folding them into a single score. The research on citation/attribution in retrieval-augmented systems shows that an answer can be correct while the cited evidence is not actually faithful or supportive (and vice‑versa), so combining them obscures failure modes and can create misleading improvements. citeturn11search0turn11search7turn0search2

The simplest practical design that still supports rigorous A/B comparisons is a **two-axis, mostly deterministic pipeline**:

- **Answer correctness (reference-based):** score the proposed cell value against the existing spreadsheet value using **type-aware normalization + deterministic comparators** (booleans, categorical, numeric). This matches how document parsing and extraction benchmarks typically rely on explicit ground truth comparisons and transparent metrics (precision/recall/F1 or exact/structured similarity), because they are debuggable and stable across runs. citeturn3search5turn3search0turn0search4turn4search3  
- **Evidence quality (reference-to-source):** avoid “big faithfulness frameworks” initially; implement (1) **anchor validity** (evidence quote is findable in the parsed PDF output) and (2) a **lightweight “support” proxy** that is deterministic for extractive-friendly fields (especially numbers). This mirrors the broader attribution literature: stronger notions like AIS/AutoAIS exist, but they add complexity and model-dependence; for a product eval you can start with minimal but inspectable checks. citeturn4search25turn11search16turn11search5  

Treat **retrieval recall/sufficiency as diagnostics**, not part of the core score. Many RAG eval frameworks explicitly keep retrieval metrics separate (e.g., context recall/precision) precisely because they explain *why* the generator succeeded or failed, but are not the same thing as end-task correctness. citeturn0search1turn0search5turn11search30  

Finally, be adversarial about the “verify mode” benchmark: if your proposal model can see the existing cell value (directly or indirectly), you can get artificially high “accuracy” that does not measure extraction skill. Your eval design should assume and detect potential **gold leakage** by requiring evidence anchored in the PDF output. citeturn11search0turn4search25  

## Strongest candidate eval designs

Below are the strongest designs, ranked for **best practical plan under strong simplicity and trust constraints**, with explicit critiques of your current hypothesis.

**Top candidate: Two-axis deterministic core with evidence anchoring (recommended baseline)**  
This is: (1) deterministic scoring for booleans/categorical/numeric; (2) evidence anchor validity + a narrow “support” proxy for extractive fields; (3) retrieval diagnostics kept separate. It aligns with the way mature document-parsing/table-extraction benchmarks emphasize **transparent ground-truth comparison** and **component-level analysis** (subtasks and end-to-end). citeturn3search0turn0search4turn4search3turn0search1  

**Second candidate: Deterministic core + selective semantic judging only for “hard residuals”**  
Same as above, but add an **optional semantic judge** step only when deterministic scoring cannot decide (typically free-text fields, or categorical synonyms not in a curated alias list). If you do this, you must treat the judge as a potentially biased, attackable component and apply guardrails: fixed judge model, temperature 0, strict JSON schema, swap-order checks, and isolation from untrusted document text to mitigate prompt-injection and biases documented in LLM-as-judge research. citeturn0search3turn5search6turn5search1turn5search0  

**Third candidate: “LLM-as-a-judge for everything”**  
This is attractive because it’s “one prompt, one number,” and some work shows LLM-based semantic evaluation can correlate better with humans than rule-based metrics in specific settings (e.g., semantic table evaluation benchmarks). citeturn8view2turn7view1  
But adversarially, this option is the easiest to fool and hardest to trust: LLM judges show position/verbosity/self-preference biases, and recent work documents prompt‑injection vulnerabilities that can directly manipulate judge outputs. citeturn0search3turn5search6turn5search0turn5search1  

**Fourth candidate: Import table-structure metrics like TEDS/GriTS into your eval**  
TEDS and GriTS are real, well-motivated metrics for **table structure recognition** and end-to-end table extraction evaluation, and are widely used in table recognition benchmarks. citeturn0search4turn4search3turn9view0  
However, they are largely misaligned with your product’s core objective: you are not trying to reconstruct whole tables; you are extracting **specific schema-aligned facts into a spreadsheet**. Using these metrics would add engineering cost without directly answering “is this cell correct?” and would complicate attribution to retrieval vs. extraction vs. row-PDF matching. citeturn3search0turn9view0  

## Recommended simplest good design

This section intentionally attacks the weak points of your current hypothesis and proposes a simpler, more robust alternative while keeping the parts that are genuinely high-leverage.

**What your current hypothesis gets right**  
Type-aware deterministic scoring for structured fields (boolean/categorical/numeric) is the backbone of most reliable extraction evals because it is reproducible, cheap, and debuggable—properties emphasized in evaluation frameworks for document parsing and IE. citeturn3search5turn3search0  

**Where your current hypothesis is too complicated (or mis-targeted)**  

1) **Over-investing in nuanced numeric partial credit early can hide systematic errors.**  
If you give lots of “medium scores” for being “close,” you can mask failures that matter to scientists (wrong unit, wrong cohort, wrong measurement timepoint). Table extraction work highlights that purely string/structure similarity can miss semantic correctness, and vice versa; partial credit needs careful calibration and error decomposition, otherwise it becomes a metric people optimize without improving usability. citeturn7view0turn8view1turn9view0  

2) **Evidence scoring is at risk of becoming a “mini faithfulness research project.”**  
Once you attempt “support / contradiction” at scale, you are doing a form of fact verification / attribution evaluation. There is extensive literature (AIS/AutoAIS; NLI-based support; LLM prompting) precisely because this is hard and can fail in subtle ways. citeturn4search25turn11search16turn11search5turn4search0  
That doesn’t mean “don’t do evidence”; it means start with **anchor validity + extractive checks** and report richer support judgments as optional.

3) **Retrieval recall should not be part of the main metric.**  
RAG evaluation practice commonly separates retrieval diagnostics (context recall/precision) from answer correctness because retrieval can be “good” yet the generator fails, or retrieval can be “bad” yet the model answers from parametric knowledge. citeturn0search1turn0search5turn11search30  
If you bake retrieval into the core score, you risk double-counting, confusing regressions, and making it harder to interpret whether a change improved parsing, retrieval, or generation.

4) **LLM judging is riskier than your draft implies, even if limited to text.**  
LLM-as-judge can correlate with humans in some benchmarks, but documented biases (position/verbosity) and security vulnerabilities (prompt-injection attacks on judges) mean it is not automatically “trustworthy enough” for scientific-quality claims without guardrails. citeturn0search3turn5search6turn5search1turn5search0  

**The simplest good design (minimum viable but meaningful)**  

Implement three layers, where only the third is optional:

- **Layer 1: Deterministic cell correctness (core scoreboard).**  
  - Score **booleans, categorical, numeric** deterministically after normalization.  
  - Treat free-text columns as **separate** from the main scoreboard at first (report them, but do not let them dominate comparisons).

- **Layer 2: Deterministic evidence checks (trust hooks).**  
  - **Evidence anchor validity** (quote exists, with stable location in parsed output).  
  - **Answer-in-evidence** for numeric/categorical when feasible (extractive support proxy).  
  - Report these separately from correctness, and also report their conjunction: “correct *and* anchored.”

- **Layer 3 (optional): Selective semantic judging only on residuals.**  
  - Only for: free-text fields, or categorical mismatches where an alias list is incomplete.  
  - Only when: evidence anchor is valid (to reduce judge hallucination and gold leakage).  
  - Use strong guardrails (detailed later). citeturn5search6turn5search1turn5search0turn0search3  

## Concrete metric definitions

This section defines metrics in a way that is implementable, inspectable, and resistant to common gaming strategies.

### Core unit of evaluation

Define one evaluation instance as a **(run_id, row_id, col_id, pdf_id)** “cell proposal record,” containing:

- gold cell value (existing spreadsheet content)  
- proposed value (model output)  
- field type and config (tolerance, unit, allowed values, etc.)  
- evidence list (quotes/spans)  

Score each instance with **two primary outputs**:

- **CorrectnessScore ∈ [0,1]** (reference-based)  
- **EvidenceScore ∈ {0,1}** (source-anchoring based; optionally extended)  

Aggregate by micro-average across cells and per-column.

### Correctness metrics: overall design choices

**Use separate aggregates rather than one blended score.**  
Define:

- **StructuredAccuracy** = mean(CorrectnessScore) over boolean/categorical/numeric fields  
- **TextScore** = mean(TextCorrectnessScore) over text fields (if you score them)  
- **AllFieldsScore** = reported but not used as the only headline (because it can be dominated by text scoring ambiguity)

This resembles the separation of dimensions in RAG evaluation (retrieval vs generation vs groundedness) and addresses the empirical point that correctness and faithfulness/attribution are not the same construct. citeturn0search2turn11search0turn0search1  

### Field-type scoring logic

The key simplification versus your hypothesis: don’t treat scoring as a zoo of special rules; treat it as **normalize → canonical representation → comparator**.

#### Boolean fields

**Canonical representation**  
Map both gold and predicted into one of: `{TRUE, FALSE, EMPTY, INVALID}`.

- Accept common surface forms (“true/false”, “yes/no”, “1/0”) via deterministic normalization.

**CorrectnessScore**  
- If gold = EMPTY:  
  - pred = EMPTY → score 1 (correct abstention)  
  - pred ∈ {TRUE,FALSE} → score 0 (false fill / hallucinated fill)  
- If gold ∈ {TRUE,FALSE}:  
  - pred = gold → score 1  
  - pred ∈ {TRUE,FALSE} and pred ≠ gold → score 0  
  - pred = EMPTY → score 0 (false abstention)

Also report these rates explicitly:

- **FalseFillRate_bool** = P(pred ∈ {TRUE,FALSE} | gold=EMPTY)  
- **FalseAbstainRate_bool** = P(pred=EMPTY | gold ∈ {TRUE,FALSE})

This “answerable vs unanswerable” framing is standard in QA-style evaluation setups where “no answer” is meaningful and separately scored. citeturn12search25turn12search2  

#### Categorical fields

**Canonical representation**  
Use a column-specific mapping:

- `allowed_values`: list of canonical category IDs (strings)  
- `aliases`: mapping of surface forms → canonical ID  

Avoid automatic thesaurus expansion initially; in scientific data extraction, naive synonym expansion can silently introduce incorrect equivalences (a trust-killer).

**CorrectnessScore**  
- Normalize gold and prediction into canonical IDs or EMPTY/INVALID.  
- Score as exact match on canonical ID, with the same EMPTY handling as boolean.

**Diagnostics**  
- Confusion matrix per column (top confusions).  
- “Invalid category rate” (prediction not in allowed set).

#### Numeric fields

Numeric extraction from papers can involve scalars, ranges, inequalities, units, and (sometimes) estimates from plots. A robust design should normalize these into a unified structure.

**Canonical representation**  
Convert gold and predicted to a normalized numeric object:

- `value_type ∈ {SCALAR, INTERVAL, ONE_SIDED, EMPTY, INVALID}`  
- `interval = [lo, hi]` where scalar is `[v, v]`  
- `unit` (optional, but strongly recommended when your schemas include them)

If units are present, convert to a configured canonical unit (e.g., mg/L). (Unit normalization is a large source of silent mismatch in scientific extraction, so treating it explicitly is high leverage.)

**CorrectnessScore (simple but trustworthy)**  
Use **binary thresholding for the headline**, and keep **error magnitude** as a diagnostic distribution (median absolute/relative error). This is simpler and harder to game than multi-level “medium score” rules.

- If both scalars:
  - Compute absolute error `ae = |p − g|` and relative error `re = ae / max(|g|, ε)`.  
  - Mark correct if `ae ≤ tol_abs OR re ≤ tol_rel` (tolerances are per column).
- If one or both are intervals:
  - Compute overlap ratio `overlap = length(intersection) / length(gold_interval)` (treat as 0 if disjoint).  
  - Mark correct if `overlap ≥ overlap_min` (e.g., 0.8), plus optional midpoint check.

**Optional partial score (secondary, not headline)**  
If you still want a [0,1] score, use a monotone function of error:

- For scalars: `score = max(0, 1 − re / tol_rel)` clipped to [0,1], but report it separately from binary accuracy.

Why this design: table extraction research repeatedly notes that purely syntactic similarity can miss semantic correctness; in numeric extraction, unit errors and context mixups are *semantic* and your eval should make them visible via explicit error diagnostics rather than burying them under partial credit. citeturn7view0turn9view0turn8view1  

#### Text fields

This is where your hypothesis is most vulnerable: “LLM judge only here” sounds simple, but it imports judge bias/security risk. citeturn5search6turn5search1turn0search3  

**Minimum viable scoring (deterministic, debuggable)**  
Score text fields with **two reported metrics**, not one:

- **ExactMatch_text (strict):** normalized string exact match (lowercase, whitespace collapse, punctuation trim)  
- **TokenF1_text (soft):** token overlap F1 (SQuAD-style), which is easy to implement and widely used for span-like answer comparisons. citeturn12search2turn12search25  

Then, *crucially*, treat free-text metrics as **secondary** and keep them out of the primary “structured extraction accuracy” headline. Token-F1 is known to be imperfect (some answers require semantic equivalence beyond overlap), so you should expect it to be noisy. citeturn12search22turn12search2  

**Optional semantic rescue (if needed)**  
If text fields matter to your product, use a judge only for cases where:

- ExactMatch_text = 0 and TokenF1_text is in a “gray band” (e.g., 0.3–0.8), and  
- evidence anchor is valid.

This reduces judge calls and focuses it on genuinely ambiguous cases.

### Evidence metrics

Evidence metrics should be **separate from correctness** because correctness and faithfulness/attribution can diverge; this is established both empirically and conceptually in the RAG attribution literature. citeturn11search0turn11search7turn4search25  

Define a small, robust ladder:

**EvidenceAnchorValid (binary, required)**  
For each evidence item, verify:

- it contains a snippet `quote_text`  
- it has an anchor `(pdf_id, page, char_start, char_end)` or equivalent stable locator  
- when you re-render the parsed PDF text for that page, the substring at that span matches (or fuzzy-matches within a tiny threshold) the stored quote

Aggregate:

- **AnchorValidRate** = fraction of proposals with ≥1 valid evidence anchor  
- **AnchorMissingRate** = fraction with no evidence / invalid anchors

This is aligned with the general motivation of attribution frameworks: claims should be verifiable against provided sources. citeturn4search25turn11search5  

**EvidenceContainsAnswer (binary, recommended for numeric/categorical)**  
A simple support proxy:

- For numeric: parse numbers (and units) out of the quote; check whether at least one extracted numeric matches the proposed numeric within tolerance.  
- For categorical: check whether a canonicalized category label (or alias) appears in the quote.

Aggregate:

- **ExtractiveSupportRate_structured** = fraction of structured-field proposals where EvidenceContainsAnswer is true.

This is intentionally **not** full semantic entailment; it’s a lightweight, inspectable proxy that strongly discourages “post-rationalized” citations (answer from memory + unrelated quote). The need to distinguish correctness from faithful citation is a central finding in attribution evaluation work. citeturn11search0turn11search7  

**Optional SupportJudge (3-class) as a separate report line**  
If you decide you need semantic support, use a 3-way label inspired by fact verification setups:

- `SUPPORTED / CONTRADICTED / NOT_ENOUGH_INFO`

This structure is used in fact verification datasets where evidence is explicitly tied to labels. citeturn4search0turn4search4  

But do **not** make this the MVP unless you accept judge complexity (LLM or NLI). There is a large body of work precisely because this is hard to do robustly. citeturn11search5turn11search16turn4search25  

### Retrieval diagnostics (optional, not core)

These should not change the “main score,” but they are invaluable to debug regressions.

- **GoldInRetrievedContextRate:** for gold-present cells, does any retrieved chunk contain the gold value (normalized)?  
- **GoldInDocumentRate:** does the gold value occur anywhere in the parsed PDF text/tables?  

These parallel “context recall” / “sufficiency” concepts in RAG evaluation frameworks. citeturn0search1turn0search5turn11search26  

The second metric is especially adversarially useful: if GoldInDocumentRate is low for a column, then your “verify mode gold” is not fully grounded in the PDFs, and your automated correctness score will penalize models for failing to extract information that is not there (or not parseable). The difficulty of reliably extracting text from PDFs is well documented, so separating “not in parse” from “model failed” matters for trust. citeturn3search19turn3search5  

## Concrete implementation plan

This is a code-level plan focused on minimal moving parts, strong reproducibility, and debuggability.

### Repository layout

Use a small, explicit evaluation package (Python suggested, but the structure applies in any language):

- `eval/`
  - `schemas.py` — schema parsing + column configs
  - `normalize/`
    - `base.py` — common normalization utilities
    - `bool_norm.py`
    - `cat_norm.py`
    - `num_norm.py`
    - `text_norm.py`
  - `compare/`
    - `bool_cmp.py`
    - `cat_cmp.py`
    - `num_cmp.py`
    - `text_cmp.py`
  - `evidence/`
    - `anchor_validate.py`
    - `support_proxy.py`
    - `judge_optional.py` (optional)
  - `diagnostics/`
    - `retrieval_recall.py`
    - `gold_in_doc.py`
  - `pipeline.py` — orchestrates scoring of a run
  - `report.py` — aggregation + run comparison
  - `cli.py` — `eval run`, `eval compare`, `eval explain`

### Data flow

**Inputs**
- `schema.yaml` (or JSON): column definitions (type, allowed values, tolerances, units, normalization hints)
- `gold_table.csv` (or your spreadsheet export)
- `run_outputs.jsonl` (one record per proposed cell; includes evidence pointers)

**Outputs**
- `cell_scores.parquet` (or JSONL): one record per scored cell with detailed fields
- `run_summary.json`: aggregate metrics + per-column metrics
- `run_report.md`: human-readable summary with top error categories
- optional: `run_compare.md`: diffs between runs

### Scoring pipeline (deterministic core)

For each cell record:

1) **Resolve field config** from schema (type, unit, tolerances).  
2) **Load gold value** and predicted value.  
3) **Normalize gold and pred** into canonical representations.  
4) **Correctness comparator** returns:
   - `correctness_score ∈ [0,1]`
   - `match_method` (e.g., `exact`, `alias`, `within_tol`, `range_overlap`, `token_f1`)
   - `error_features` (e.g., `abs_err`, `rel_err`, `unit_mismatch`, `invalid_parse`)
5) **Evidence anchor validation** returns:
   - `anchor_valid` (bool)
   - `bad_anchor_reason` (if false)
6) **Evidence support proxy** (only for appropriate types) returns:
   - `evidence_contains_answer` (bool / null if not applicable)
7) **Optional judge step** runs only if configured and gated.

Store all intermediate artifacts per cell to enable “click-to-debug” style workflows.

### Where deterministic scoring happens vs optional judging

**Deterministic always-on**
- normalization + comparison for boolean/categorical/numeric  
- text: at least ExactMatch_text and TokenF1_text  
- evidence anchor validity  
- evidence “contains answer” proxy for numeric (+ optionally categorical)

**Optional (off by default)**
- text semantic equivalence judge  
- boolean/categorical semantic support judge  
- contradiction detection

This matches the practical lesson from table evaluation research: rule-based metrics are stable but can miss semantic nuance; LLM-based semantic evaluation can correlate better with humans but should be layered on top, not replace the deterministic backbone. citeturn8view2turn7view0turn0search3  

### Run comparison

Implement `eval compare runA runB` that prints:

- headline deltas for:
  - StructuredAccuracy (and per-type accuracy)
  - FalseFillRate / FalseAbstainRate
  - AnchorValidRate
  - ExtractiveSupportRate_structured
  - GoldInRetrievedContextRate (diagnostic)

Include two “adversarial sanity checks”:

- **Evidence regression check:** if StructuredAccuracy improves but ExtractiveSupportRate drops, flag it (possible “answer from memory” or evidence quality regression). citeturn11search0turn11search7  
- **Leakage suspicion check:** if StructuredAccuracy is extremely high yet AnchorValidRate is low, flag it (possible gold leakage or non-grounded answering).

Optionally add bootstrap confidence intervals later; don’t block MVP on significance testing.

## Minimal artifact and output changes needed

Your proposed artifacts are close; the biggest missing pieces are those that make evidence checks reproducible and that protect against benchmark leakage.

### Keep (good and sufficient as a base)

- `field_type`  
- `gold_value_raw` (or original cell)  
- `proposal_value_raw`  
- `proposal_value_normalized` (or enough to recompute)  
- `match_method`  
- `run_id`, `model_id`, `prompt_version`  

### Add the minimal extra fields that make eval “clean” and debuggable

**Stable cell identity**
- `row_id` (stable key)  
- `col_id` (stable key)  
- `cell_id = hash(row_id, col_id)`  

**PDF identity and versioning**
- `pdf_id` (filename or internal ID)  
- `pdf_hash` (content hash)  
- `parser_version` (so evidence anchors remain interpretable across parser changes)

This matters because PDF parsing can change substantially with tool versions, and PDF text extraction quality is known to vary widely; without versioning you can misattribute regressions. citeturn3search19turn3search5  

**Evidence anchoring fields (required for trustworthy evidence metrics)**
For each evidence item (store as list):
- `page`  
- `char_start`, `char_end` (or token offsets)  
- `quote_text` (verbatim snippet you expect at that anchor)  
- optional (if you have it): bounding box coordinates  

This enables deterministic anchor validation.

**Abstention representation**
- `pred_is_empty` (boolean) + `abstain_reason` (short enum)  
This is needed to compute false fill / false abstain robustly.

**Schema version**
- `schema_hash` or `schema_version`  
So you can compare runs meaningfully when schema evolves.

### Explicitly do not store (or do not require) in MVP

- Full “judge reasoning” chains (they increase storage, privacy risk, and can leak prompt injection artifacts)  
- Complex claim graphs or sentence-level IE structures (these turn your eval into a research project)

If you later add a judge, store only:
- `judge_model_id`, `judge_prompt_version`, `judge_verdict`, `judge_confidence` (if provided), and `judge_input_hash`.

## Risks and failure modes

This section is intentionally adversarial: it lists how your eval can lie to you.

### Gold leakage in verify mode

If the generation model can see the existing spreadsheet value (directly in the prompt, or indirectly via a “row context” that includes it), your automated correctness metric becomes meaningless: the model can copy the answer. Evidence anchoring mitigates this if (and only if) you require evidence to be **findable in the PDF parse** and (ideally) to contain the answer for structured fields. This aligns with attribution motivations: verifiability against provided sources is essential. citeturn4search25turn11search0turn11search7  

### Spreadsheet “gold” may not be extractable from PDFs

Your benchmark assumes the spreadsheet value is the gold reference derived from the paper. In practice, humans may have filled values from:
- supplemental materials not in the PDF
- external databases
- domain knowledge / calculations

Without accounting for this, you will penalize models for failing to extract non-present information. The “GoldInDocumentRate” diagnostic is a non-manual way to detect this. The broader PDF extraction literature emphasizes that parsing itself is difficult and tool-dependent, so distinguishing absence from extraction failure is central to trustworthy evaluation. citeturn3search19turn3search5  

### Metric gaming via partial credit

Overly generous numeric partial scoring can reward wrong-but-close answers and incentivize “safe guessing.” Prefer binary thresholds for the headline plus explicit error distributions; this is simpler and exposes systematic mistakes (wrong unit, wrong subgroup) that matter scientifically. citeturn7view0turn9view0  

### LLM judge reliability and security

If you use an LLM judge, you inherit three classes of problems documented in the literature:

- **Bias and instability:** position bias and other systematic biases can change rankings when response order changes; this can be exploited. citeturn5search6turn5search22  
- **Vulnerability to prompt injection:** multiple papers show judge architectures can be manipulated by injected sequences to force desired verdicts. citeturn5search1turn5search0turn5search9  
- **Domain and grounding issues:** recent work continues to question judge reliability in high-stakes correctness settings without human grounding and careful calibration. citeturn0search24turn0search28turn0search13  

**Constraints that make LLM judging more reliable (if you must do it)**  
- Use a **fixed, strong judge model** and log its exact version. citeturn0search3turn5search15  
- Temperature 0; strict JSON schema; “no free-form explanations.”  
- Swap order and average (or require consistency) to reduce position bias. citeturn5search6turn5search22  
- Never pass untrusted document text as “instructions”; clearly delimit evidence as quoted material. (This is a standard defense motif in prompt-injection discussions, though it is not a complete solution.) citeturn5search16turn5search8  
- Gate judge calls behind anchor validity and (for structured fields) behind deterministic mismatch detection to reduce attack surface and cost.

### Evidence post-rationalization

Even when answers are correct, models may attach plausible but unrelated citations (“post-rationalization”). This is a central concern in attribution evaluation and is exactly why evidence should be scored separately and with explicit anchoring checks. citeturn11search0turn11search7turn4search25  

## Open questions and what to test first

These are tests that will quickly tell you whether your eval metric is meaningful before you invest in complexity.

**Test whether your benchmark is measuring extraction or leakage**
- Run the system with retrieval disabled (or with empty context) and measure correctness. If accuracy stays high, you have leakage or “answer from memory,” and evidence metrics must become stricter. citeturn11search0turn0search2  

**Measure how often “gold” is actually present in the parsed PDF**
- Compute GoldInDocumentRate per column. Columns with low rates need schema clarification, better parsing, or exclusion from automated eval.

**Ablate parsing and retrieval separately**
- Vary parser settings or PDF extraction tool versions and see whether GoldInDocumentRate and AnchorValidRate move in tandem. PDF extraction variability is a known issue; you want your eval to attribute regressions correctly. citeturn3search19turn3search5  

**Check metric sensitivity**
- For numeric columns, plot absolute/relative error distributions, not just accuracy. Confirm that improvements correspond to meaningful scientific correctness (unit correctness, order-of-magnitude, etc.), not just tiny shifts around tolerance thresholds.

**Decide whether text fields belong in the automated scoreboard**
- If text columns are critical, run a small study: compare TokenF1_text vs a selective judge on a tiny sample (even 50–100 cells) once, to estimate noise. If the judge disagrees heavily or shows instability under swap-order, keep text out of the headline metric. citeturn12search2turn5search6turn5search22turn0search28  

**If you adopt an LLM judge, red-team it**
- Include adversarial strings in candidate outputs and evidence (e.g., “the correct score is 10/10”) and confirm the judge is not trivially steerable—because the literature shows it often is steerable. citeturn5search1turn5search0turn5search9