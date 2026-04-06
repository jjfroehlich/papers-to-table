# Extract Structured Info from Papers Optimizer - research.md

## Status

Initial rationale and tradeoff record for the optimizer MVP.

## Purpose

This document explains why the optimizer is shaped as a narrow benchmark-driven orchestration tool, why the MVP is deterministic-first, why promotion is gated, and which ideas are explicitly deferred.

---

## Why this is benchmark-driven optimization rather than autonomous code editing

The target problem is parameter and prompt optimization over an existing extraction system, not open-ended software improvement.

The optimizer only needs to answer a bounded question:

- which explicit prompt, model, and config bundle performs best on a fixed benchmark under explicit guardrails?

Autonomous code editing would widen the surface too far:

- it would blur responsibility between optimizer, main app, and eval app
- it would make provenance and rollback much harder
- it would mix architecture changes with prompt or config tuning
- it would make small benchmark results harder to interpret

The cleaner MVP shape is a harness that changes only an explicit search surface and evaluates those changes against a fixed benchmark.

---

## Why deterministic-first MVP is preferred

The first shipping optimizer should maximize reproducibility and auditability.

Deterministic-first behavior is preferable because it:

- makes candidate generation easier to inspect
- reduces run-to-run variance not caused by the model under test
- keeps failure analysis simpler
- avoids premature dependence on a meta-LLM proposer
- makes it easier to explain why one candidate was generated and promoted

An unrestricted LLM-based proposer would introduce several problems too early:

- search behavior would become harder to bound
- candidate duplication and low-value prompt churn would increase
- audit trails would need much richer provenance immediately
- the optimizer could look more capable than it actually is

The MVP should first prove value on explicit candidate generation. LLM assistance can come later only if it stays bounded and measurable.

---

## Why the search surface should stay narrow

The search surface must stay explicit and small because the benchmark loop is expensive.

Each candidate requires:

- a main-app benchmark run
- an eval-app scoring pass
- result recording and comparison

If the mutation surface is too broad, several issues appear quickly:

- the search space becomes too large to explore meaningfully
- accepted improvements become harder to attribute to any one change
- more candidate failures come from invalid or unstable configurations
- the optimizer starts depending on hidden knowledge of main-app internals

The narrow surface is a feature, not a limitation. It forces the optimizer to change only the dimensions that are likely to matter and safe to compare.

---

## Why the optimizer must remain orchestration-only

The three repos have intentionally separate responsibilities.

- The main app executes extraction.
- The eval app scores outputs.
- The optimizer coordinates search, launching, and promotion.

Keeping those boundaries matters because it:

- avoids duplicated logic across repos
- keeps scoring changes out of optimization code
- keeps extraction changes out of the optimizer
- makes artifacts and contracts the integration surface
- allows each repo to evolve without collapsing into one tightly coupled system

If the optimizer starts re-implementing scoring or extraction behavior, comparisons become less trustworthy and maintenance cost increases.

---

## Why dev versus holdout split is necessary

Optimization without a holdout split invites benchmark overfitting.

Even with a small explicit search surface, repeated rounds against one benchmark can produce candidates that exploit quirks of the dev set rather than improving general extraction behavior.

The dev versus holdout split is therefore mandatory:

- dev is used to drive search and promotion
- holdout is used only to validate whether the promoted best candidate generalizes

Holdout must stay outside the main search loop. If holdout results influence candidate promotion round by round, it stops being a holdout.

---

## Why gated acceptance is necessary

A single blind scalar is not enough for this domain.

If promotion optimizes only one headline score, the optimizer can drift toward pathological behavior such as:

- better correctness with much worse evidence quality
- better score with unacceptable runtime cost
- better score by increasing null or failure behavior elsewhere
- fragile candidates that pass numerically but break deterministic expectations

The gated rule is a better fit because it preserves distinct metric roles:

- primary metrics decide whether the candidate is meaningfully better
- guardrail metrics block harmful regressions
- diagnostic metrics explain behavior without silently affecting promotion

This keeps promotion logic explicit and easier to audit later.

---

## Why immutable candidate bundles are necessary

The optimizer must never mutate the live baseline in place.

Immutable candidate bundles provide several benefits:

- exact reproducibility of promoted winners
- easier debugging when a candidate behaves unexpectedly
- clear lineage from baseline to winner
- safer comparison across rounds
- easier summary regeneration and plot rebuilding

Without immutable bundles, the system becomes harder to reason about because the same candidate id could mean different actual settings over time.

---

## Why CLI-first is the right MVP shape

The optimizer is primarily an orchestration tool.

Its core work is:

- loading definitions
- launching runs
- recording metrics
- producing summaries and plots

A UI would add significant surface area without improving the essential contract. CLI-first is the smallest honest product shape for MVP and keeps the repo focused on its real job.

---

## Likely failure modes

### Contract drift between repos

The optimizer depends on stable automation surfaces and stable machine-readable outputs from the main app and eval app. If those contracts drift silently, optimization runs can fail or become misleading.

### Benchmark overfitting

A candidate may improve on dev by exploiting a narrow benchmark quirk. That is why holdout validation is required.

### Runtime explosion

Even a small candidate batch can become expensive when the benchmark is slow. Batch size, round count, and search width must remain controlled.

### Search-space sprawl

If too many config knobs are added, the optimizer becomes harder to use, harder to interpret, and less likely to produce meaningful improvements.

### Candidate provenance loss

If prompt snapshots, config overlays, or hashes are not persisted per candidate, later analysis of promoted winners becomes unreliable.

### Noisy promotion decisions

If promotion logic does not distinguish primary metrics from guardrails, the optimizer may accept candidates that are numerically better but operationally worse.

### Hidden nondeterminism

If candidate generation, benchmark selection, or run orchestration contains uncontrolled randomness, it becomes harder to interpret score movement across rounds.

### Over-coupling to main-app internals

If the optimizer needs deep imports or internal helper reuse from the main app, the repo boundary weakens and maintenance cost rises.

---

## Deferred items

The following are intentionally deferred beyond the narrow MVP:

- unrestricted LLM-based prompt rewriting
- code mutation or autonomous repo editing
- optimizer-driven eval-metric mutation
- optimizer-driven benchmark mutation
- broad parallel or distributed scheduling systems
- a GUI or dashboard product surface
- advanced search strategies such as Bayesian optimization or evolutionary search beyond the bounded initial loop
- automatic PR creation or repo-management workflows

These may become reasonable later only if the bounded MVP proves useful and the auditability story stays strong.

---

## Recommended MVP posture

The optimizer should first be good at one thing:

- compare a small number of explicit candidate bundles on a fixed benchmark and promote improvements under clear gates

That posture keeps the repo understandable, keeps the benchmark results interpretable, and preserves the architectural separation between execution, scoring, and optimization.