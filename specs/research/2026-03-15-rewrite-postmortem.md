# Paper Table Agent Rewrite Postmortem

Date: 2026-03-15

## Bottom Line

The old Paper Table Agent did succeed at one real job: take a table plus PDFs, match papers to rows, generate proposals with at least some evidence, and give the operator a review surface. That core loop is the part worth preserving.

Most of the engineering drag came from trying to make one runtime handle too many adaptive strategies at once: multiple parsing paths, multiple context modes, multiple retrieval backends, multiple evidence repair paths, provider capability probing, JSON salvage, and a LangGraph wrapper on top of a mostly sequential batch loop. The result was a system with a lot of defensive sophistication but weak operational clarity.

The strongest rewrite case is not that the product idea failed. It is that the implementation accumulated too many compensating layers around brittle LLM and PDF behavior, and those layers started to dominate the codebase.

## What Was Actually Useful

Not all features were equally valuable. The code, tests, and preserved run artifacts point to a fairly clear core.

### 1. Batch PDF-to-table proposal generation was the real product

The useful heart of the system was:

1. ingest a table and schema
2. match PDFs to rows
3. propose values for missing cells
4. attach evidence when possible
5. review and export

That product loop is visible consistently across the CLI, UI, tests, and run outputs:

- `paper_table_agent/cli.py` exposes `run`, `eval`, `export`, and `ui`
- `paper_table_agent/ui/app.py` is centered on Run and Review, not on fine-grained tuning
- `tests/test_integration.py` spends its energy on end-to-end proposal production, review rows, export, and eval artifacts

This is the part to carry forward intact.

### 2. Audit/eval was more valuable than most optional runtime sophistication

The repo eventually made audit-mode extraction and eval first-class, and that looks correct in hindsight.

Why it mattered:

- it created an internal quality loop without requiring a new benchmark corpus
- it forced the system to write measurable outputs instead of relying on anecdotes
- it made regressions legible at the run level

The preserved run shows why this was useful. In `runs/20260308_172426__MPRA_team - literature_MPRAs/exports/proposal_eval.md`, the system reports:

- 20 audited cells
- overall score 25%
- evidence coverage 100%
- anchorable quote rate 65.22%
- highlight OK rate 73.91%

That is exactly the kind of sobering but actionable signal a rewrite needs. The system was often able to produce something, but not often able to produce something correct.

### 3. Reviewable evidence was useful, even when imperfect

The old system was right to make evidence a first-class output instead of a hidden prompt artifact. Even though the evidence pipeline became too complicated, the product decision was sound.

Useful aspects:

- quote/page/chunk anchoring gave the reviewer something concrete to inspect
- highlightability and evidence-quality flags created practical triage cues
- preserving values while downgrading evidence quality was better than deleting proposals outright

This should stay in the rewrite, but with a much simpler contract.

### 4. Stub/mock end-to-end testing was high-value

The repo made a good strategic choice to support deterministic tests without live models. `tests/test_integration.py` and related tests show that the team understood the need for a hermetic baseline.

That is one of the best things to preserve.

## Architecture And Coupling

### The actual runtime architecture was much more centralized than the module layout suggested

At a glance, the repo looks modular: `graph/`, `retrieval/`, `pdf/`, `llm/`, `ui/`, `store/`. In practice, the central behavior was concentrated into a few oversized orchestration modules.

The most important coupling points were:

- `paper_table_agent/graph/workflow.py`
- `paper_table_agent/graph/runner.py`
- `paper_table_agent/graph/context_planner.py`
- `paper_table_agent/graph/extraction.py`
- `paper_table_agent/graph/evidence_finder.py`
- `paper_table_agent/llm/client.py`

### LangGraph added less architectural value than its presence implied

`paper_table_agent/graph/workflow.py` uses LangGraph, but the graph is essentially:

1. initialize state
2. process next PDF
3. loop until done

That is a checkpointed sequential loop, not a rich graph-shaped workflow. The abstraction cost appears higher than the value returned.

What it bought:

- resumability via checkpoints

What it did not obviously buy:

- simpler composition
- better stage isolation
- clearer failure handling

This is one of the clearest rewrite opportunities: keep resumability if needed, but remove the graph framework unless the new system genuinely needs branching graph semantics.

### `RunContext` became the gravity well of the system

`paper_table_agent/graph/runner.py` defines a large `RunContext` carrying config, store, table data, grouped schema, locks, row assignments, four LLM clients, embedding/reranker clients, retrieval config, example data, audit targets, caches, logger, and prompt metadata.

That is the architectural center of mass. Once a context object like that exists, every function tends to depend on everything.

Consequences:

- hidden stage dependencies
- hard-to-reason side effects
- awkward unit boundaries
- config changes ripple across unrelated stages
- storage and domain logic become fused

The rewrite should not reproduce this pattern.

### `runner.py` absorbed too many responsibilities

`paper_table_agent/graph/runner.py` is effectively the real application layer. It handles:

- config normalization and quality presets
- health checks and provider capability routing
- table/schema loading
- PDF enumeration
- parser/backend selection
- matching
- retrieval backend fallback
- context planning
- extraction retries
- evidence finding
- eval triggering
- run report events

That is too much for one module and too much for one stage coordinator. The module became the place where every exception, feature flag, compatibility special case, and artifact write ended up living.

### The code had modular pieces, but their contracts were porous

Examples:

- `context_planner.py` decides between fulltext, memory, and retrieval, but that decision is entangled with token estimation, prompt construction, model capability assumptions, and extraction batching
- `extraction.py` both builds prompts and validates evidence post hoc
- `evidence_finder.py` both repairs evidence and performs highlight recovery
- `llm/client.py` mixes transport, provider capability inference, prompt truncation, guided JSON routing, request recording, and repair behavior

The result is not just complexity; it is cross-contamination of concerns.

## Common Failure Modes

The tests, compounding notes, changelog, and preserved logs all point to the same recurring classes of failure.

### 1. LLM output formatting and provider compatibility failures

This repo spent a lot of energy compensating for model/backend mismatch.

Evidence:

- `paper_table_agent/llm/client.py` contains guided JSON routing, capability inference, prompt-only fallback, regex/schema stripping, HTTP 400 handling, timeout handling, and JSON repair behavior
- compounding notes include `2025-03-12-guided-json-fallback.md`, `2025-03-14-json-ingestion-and-capability-routing.md`, and `2025-03-13-lmstudio-compat-logging-and-budgets.md`
- `tests/test_llm_json_parsing.py` and `tests/test_llm_guided_json_fallback.py` exist because this was repeatedly painful

In the preserved run log, nearly every request runs in `constraint_mode: constraints_off`. That is a strong signal that the nominal structured-output path was not the reliable default in practice.

### 2. Retrieval quality was inconsistent enough that fallback modes dominated

The run report for the preserved MPRA run is especially revealing:

- 69 proposals total
- 64 inferred
- only 5 found
- 60 proposals marked `needs_more_evidence`
- 35 extraction batches
- 0 batches with chunks present
- 35 batches with chunks missing
- all shown batch examples use `context_mode: memory`

That is the single most important operational clue in the repo.

The architecture talked heavily about retrieval, reranking, dense embeddings, query expansion, HyDE, section windows, and chunk-aware evidence validation. But this real run indicates the system often fell back to memory-mode extraction without retrieved chunk context.

That does not mean retrieval was useless. It means the retrieval-heavy architecture was not reliably the dominant path when it mattered.

### 3. Evidence anchoring and highlighting were persistently brittle

This may be the clearest recurring pain area in the whole codebase.

Evidence:

- multiple compounding docs are specifically about evidence normalization, chunk ids, page ranges, whole-text anchors, evidence backfill, and highlight guardrails
- `paper_table_agent/graph/evidence_finder.py` is full of repair and salvage logic
- tests exist for evidence finder, evidence anchoring, highlight quality, layout regression, and verification support
- changelog entries repeatedly mention header/footer rejection, weak-evidence backfill, page inference, token salvage, normalized/dehyphenated highlight fallbacks, and found-to-inferred downgrades

The preserved run still reports only 73.91% highlight OK rate even after all that defensive work.

That suggests the system did improve this area, but never made it truly reliable.

### 4. Prompt budgets and retries caused secondary complexity explosions

The old repo accumulated substantial code around prompt budgeting, truncation, batching, whole-text eligibility, memory summaries, and retries.

This was not accidental complexity. It came from a real constraint: long papers plus many target columns do not fit comfortably into model budgets.

But the operational outcome was messy:

- fulltext was prepared
- memory summaries were also generated
- retrieval expansions were also attempted
- retries were used when proposals were unclear or evidence was weak

In the preserved run log, the system repeatedly issues `query_expand` and `hyde` calls, then extraction calls, then repair calls, with multiple timeouts along the way. That means the budget problem did not just affect model quality; it multiplied latency and moving parts.

### 5. Header extraction and matching needed repeated repair logic

Matching was central and useful, but it also needed layered safeguards:

- header text truncation
- repair prompts
- deterministic thresholds plus LLM adjudication
- duplicate handling
- DOI bonuses and year tolerance

This is a legitimate problem area, but less alarming than the evidence/provider issues. The preserved run matched 4 of 4 PDFs successfully, which suggests matching complexity may have ended in a relatively good place.

## Pain Points That Motivate A Rewrite

### 1. The system became a compensating machine for other unreliability

The old code increasingly exists to compensate for:

- inconsistent PDF structure
- inconsistent model JSON behavior
- inconsistent provider capabilities
- inconsistent retrieval quality
- inconsistent highlight recoverability

That does not make the code bad. It makes it the kind of codebase that becomes hard to evolve because every new improvement gets added beside old guardrails instead of replacing them.

### 2. The dominant product path was obscured by adaptive machinery

There was a relatively straightforward product underneath:

- parse enough text
- match the right paper
- ask focused questions per column
- provide evidence for review

But the implementation increasingly foregrounded runtime adaptation:

- fulltext vs memory vs retrieval
- dense vs sparse vs reranked retrieval
- guided JSON vs prompt-only vs constraints-off
- local parser vs GROBID variants vs OCR rescue
- initial extraction vs retry-on-unclear vs evidence backfill

The rewrite should restore a visible default path and make every deviation explicit and rare.

### 3. Runtime policy lived inside code instead of at clean boundaries

The repo had many config knobs, but the harder problem was that runtime policy was embedded across modules. Example decisions were scattered:

- when to disable guided JSON
- when to fall back to TF-IDF
- when to choose memory mode
- when to retry extraction
- when to downgrade evidence
- when to backfill weak evidence

This made behavior hard to predict from config alone.

### 4. Observability was strong, but clarity was weak

The old repo wrote many artifacts and diagnostics, which was good. But the system often needed those diagnostics because the runtime path was difficult to reason about directly.

The rewrite should preserve observability while reducing the number of things that need observing.

## Dead Complexity And Config Sprawl

Not all complexity was dead, but a meaningful amount looks low-yield or overextended.

### Likely low-yield architecture complexity

#### LangGraph wrapper

The workflow graph looks like a thin shell around a sequential loop. Unless checkpoint-resume is essential and cannot be implemented more simply, this should be removed.

#### Multiple provider-role clients with identical models

The config supports separate header/match/extract/query-helper models and separate fallback models for each role. In the preserved run, all primary roles used the same model. That suggests the role separation may be more notional than operational.

The rewrite can still support role-specific prompts, but it does not need a full matrix of model slots unless there is actual observed value.

#### Retrieval backend matrix

The old config supports:

- sparse retrieval
- optional dense embeddings
- optional reranker
- LM Studio embedding backend
- TF-IDF fallback
- stub/hash backends for testing

Some of this is legitimate. But the code also carries the branching burden of backend validation, health checks, fallback rewrites, and debug reporting. Given that the preserved run appears to lean on memory mode instead of retrieved chunks, the retrieval backend surface looks larger than its realized value.

#### Fulltext plus memory plus retrieval all in one runtime

This is the biggest conceptual sprawl point.

The old repo did not just support three context modes. It created planning and budgeting machinery for all three, and artifacts for both fulltext and memory were written per PDF in the preserved run. That is a lot of system for what should probably become a smaller number of clearly prioritized strategies.

### Config sprawl patterns

`paper_table_agent/config.py` grew into a large policy surface:

- provider settings
- fallback provider settings
- prompt limits and overrides
- matching thresholds and margins
- extraction grouping, batching, whole-text, memory, retries, thinking-model keywords
- retrieval top-k, rerank-k, context budgets, summaries, query expansion, HyDE, dense backend, reranker backend, cache sizes
- OCR thresholds
- GROBID settings
- output debug flags
- audit settings
- quality preset plus `max_success_mode`

Two specific smells stand out:

#### `quality_preset` plus `max_success_mode`

This is redundant policy language. The code in `RunConfig.apply_quality_preset()` effectively lets `max_success_mode` override the named preset. That is exactly the kind of config shape that confuses operators and future maintainers.

#### User-facing config and runtime tuning mixed together

Paths, schema choices, and table metadata live beside backend compatibility behavior, cache limits, and retrieval heuristics. Those are not the same category of configuration and should not be treated as one file of equal-status knobs.

## Lessons From Run Artifacts, Tests, And Evaluation Outputs

### The preserved run says the system was productive but not accurate enough

The strongest concrete lesson comes from the real run artifact, not the docs.

From `run_report.json` and `proposal_eval.md`:

- matching succeeded on all 4 PDFs
- proposal production was high: 69 proposals with values
- evidence was always attached in some form
- but only 5 proposals were `found`
- 64 were `inferred`
- 60 needed more evidence
- overall audited accuracy was 25%
- many columns had 0% match rate

Interpretation:

- the system was good at always producing an answer
- it was much less good at producing the right answer
- evidence attachment did not imply correctness
- the proposal-first philosophy made sense for usability, but it also risked hiding how uncertain the system really was

### The logs show auxiliary LLM work may have been too expensive relative to value

The preserved run log shows heavy use of:

- header extraction
- header repair
- paper memory generation
- query expansion
- HyDE
- extraction
- JSON repair

with repeated timeouts during helper-model calls.

This suggests the system may have been over-investing in preparatory and recovery calls before the final extraction quality justified that cost.

In a rewrite, every extra LLM call should have to earn its place.

### The test suite distribution is itself a postmortem

The repo has strong coverage, but what it covers is informative:

- evidence anchoring/highlighting
- JSON parsing and guided fallback
- context planning
- prompt budgeting
- retrieval
- parsing quality
- live LLM E2E behavior

That is not the profile of a system whose pain lived mainly in business logic. It is the profile of a system whose pain lived in brittle boundaries: models, documents, retrieval, and evidence anchoring.

That means the rewrite should spend design energy on boundary contracts first, not on adding more adaptive heuristics.

### The compounding notes show repeated local fixes to a few core problem families

The `docs/compounding/` directory is revealing. Many notes are clustered around:

- evidence finder and evidence normalization
- chunk ids and ID-based extraction
- JSON repair and ingestion
- prompt budgets and payload logging
- guided JSON fallback and capability routing
- whole-text anchors and span highlights
- audit eval harness

This pattern says the repo was not suffering from many independent issues. It was suffering from a few stubborn systemic ones, repeatedly.

## Concrete Recommendations

## Carry Forward

### 1. Keep the product loop

Carry forward the product shape:

1. table + schema ingestion
2. PDF matching
3. missing-cell proposal generation
4. evidence shown to humans
5. review + export

This was the right product boundary.

### 2. Keep audit/eval as a first-class built-in

Do not relegate evaluation to an afterthought. The old repo became much more honest once audit/eval artifacts were standard.

Carry forward:

- automatic eval when gold cells exist
- per-column metrics
- highlightability/anchorability metrics
- run-level summaries

### 3. Keep hermetic end-to-end tests with stub/mock providers

This is one of the strongest engineering choices in the old repo. Preserve deterministic offline testing and use it as the rewrite baseline.

### 4. Keep evidence as an operator-facing object

Do not regress to a system that only emits values. Preserve:

- quote text
- page reference
- evidence quality or confidence state
- review-time visibility

But simplify how evidence is generated and validated.

### 5. Keep matching heuristics, but make them a small standalone subsystem

Matching seems comparatively successful and conceptually coherent. Keep deterministic matching plus optional adjudication, but isolate it from the rest of the runtime.

## Re-simplify

### 1. Replace the graph runtime with a simple staged batch runner

Use explicit stages and persisted stage outputs if resumability matters. Do not keep LangGraph unless the new design truly requires branching workflows.

### 2. Separate user config from runtime policy

Have a small user config for:

- table path
- PDF folder
- schema source
- column/task selection
- model/provider choice

And a much smaller policy layer for:

- context strategy
- batch size
- retrieval on/off
- evidence mode

Do not expose dozens of equal-status knobs by default.

### 3. Collapse context strategy options

The old system had three major context modes. The rewrite should start with one primary path and one fallback, not three peers.

A plausible shape:

- default: focused retrieval-based extraction with small, explicit evidence units
- fallback: fulltext extraction for small papers or when retrieval is disabled

Only keep memory-mode summarization if it proves clearly better on measured outcomes.

### 4. Make evidence contracts narrower and stricter

The rewrite should define a smaller evidence object with a smaller number of allowed states. Prefer fewer but more trustworthy evidence outcomes over many salvage paths.

### 5. Move provider-specific behavior behind strategy adapters

`llm/client.py` currently carries too much policy. The rewrite should isolate provider quirks so the core extraction code is not constantly aware of structured-output compatibility, regex stripping, and fallback conditions.

### 6. Treat extra LLM helper passes as optional experiments, not baseline runtime

Query expansion, HyDE, memory summarization, repair passes, and similar helpers should be justified by measured lift. They should not all be baseline behavior.

## Discard Or Deprioritize

### 1. Discard the assumption that more adaptive routing is automatically better

The old repo often responded to brittleness by adding another fallback. That improved survival but hurt clarity. The rewrite should resist this reflex.

### 2. Discard low-signal config aliases and mode duplication

Examples:

- `max_success_mode` alongside `quality_preset`
- overlapping prompt limit controls without a clear precedence story for users
- too many backend-specific settings in the main run config

### 3. Deprioritize GROBID and alternate parser backends unless the rewrite proves structural gains

The old repo carried parser abstraction and GROBID support, but the preserved run artifacts are all from the local parser path. Keep parser contracts clean, but do not build a large parser matrix early in the rewrite.

### 4. Deprioritize dense retrieval and reranker complexity unless they measurably improve audited accuracy

These features may help, but the preserved run does not make a strong case that the current retrieval sophistication translated into strong accuracy. Do not assume that retrieval complexity is where the next major gain lies.

### 5. Discard broad salvage ladders as the first answer

If evidence anchoring is weak, the first question should be whether the extraction contract is too loose, not which additional salvage trick to add.

## Suggested Rewrite Shape

If the rewrite wants to stay ambitious while avoiding the old failure mode, a better architecture would likely look like:

1. `ingest`: table/schema normalization and PDF inventory
2. `parse`: one main parser, one normalized document contract
3. `match`: deterministic-first paper-to-row matching with optional adjudication
4. `extract`: a small number of explicit extraction strategies
5. `evidence`: one strict evidence validator and one simple locator path
6. `review`: operator UI over stored proposals and evidence
7. `eval`: always-on scoring when audit gold exists

And each stage should:

- read a clear input artifact
- write a clear output artifact
- avoid mutating shared mega-context wherever possible
- be replayable independently

## Final Assessment

The old repo was not overbuilt because the team was careless. It was overbuilt because the problem is genuinely adversarial: messy PDFs, long contexts, evolving models, and evidence requirements are all hard at once.

But the repo’s own artifacts now show where the engineering center drifted too far from the product center.

What to preserve is the product intent, the evaluation discipline, and the operator-facing evidence model.

What to rewrite is the runtime shape: fewer adaptive modes, fewer global knobs, fewer compensating fallbacks, stronger stage boundaries, and much stricter default contracts.

That is the main lesson of this codebase.