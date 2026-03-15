Please research the best background-job/runtime library for Paper Table Agent’s MVP.

## Context

Paper Table Agent is a local-first single-user app with a staged workflow:
- ingest
- parse
- match
- retrieve
- extract
- evidence recovery
- export
- evaluation

We want:
- a deterministic staged runner
- background execution for longer stages
- resumability/checkpoints if practical
- no graph-first orchestration unless truly needed

## Research questions

1. Which background job/runtime libraries are best suited for a local-first single-user app?
2. How do the main candidates compare for:
   - simplicity
   - local deployment
   - reliability
   - visibility of job progress
   - checkpoint/resume support
   - maintenance burden
3. What is the best fit for MVP?

## Deliverables

Please produce a structured markdown report with:
- Executive summary
- Candidate libraries
- Comparison table
- Recommended MVP choice
- Recommended architecture fit
- Open questions

## Constraints

- We want to keep the runtime simple.
- We do not want heavyweight distributed infrastructure for MVP.
- Please include citations/links.

I’m comparing lightweight local-first job runtimes against heavier orchestrators and looking specifically for durability, resume behavior, and MVP maintenance cost.

I’ve narrowed it down to “queue libraries” versus “workflow/orchestration systems.” For this MVP, the biggest tradeoff is whether you want zero extra infrastructure or stronger built-in durability.

Thought for 4m 18s
Paper Table Agent — background job/runtime library research
Executive summary

For Paper Table Agent’s MVP, the best default choice is Huey, specifically a code-owned staged runner plus Huey with SqliteHuey for background execution. Huey is unusually well aligned with your constraints: it is a real task queue, supports SQLite / filesystem / Redis backends, supports thread / process / greenlet workers, and gives you retries, scheduling, task revocation, rescheduling, locks, and consumer signals without requiring Redis, RabbitMQ, or a separate orchestration server.

The key architectural recommendation is: do not let the queue library own your workflow. Keep the Paper Table Agent pipeline as an explicit deterministic stage machine in your own code and database (ingest → parse → match → retrieve → extract → evidence recovery → export → evaluation), and use the background-job library only to run one stage at a time in the background. That keeps the runtime simple, preserves deterministic behavior, and avoids graph-first orchestration. This also matches the broader advice to prefer simpler, code-first orchestration before introducing graph-heavy systems.

If you are already comfortable shipping a local Redis alongside the app, RQ is the strongest alternative because it stays simple while offering better built-in job visibility via statuses, metadata, dependencies/groups, results, and a lightweight dashboard. If you need true durable workflow replay across crashes, long-lived workflows, or fine-grained mid-run resume semantics, the lightweight queue class is no longer enough; that is when Temporal becomes the right tool, with Prefect as a middle ground for richer orchestration and UI.

Candidate libraries
1) Huey

Huey is a lightweight Python task queue with Redis, SQLite, filesystem, or in-memory storage; it supports multi-process, multi-thread, and greenlet execution, scheduled and recurring tasks, task priorities, retries, result handles, revocation/rescheduling, task locks, and synchronous consumer signals. SqliteHuey only requires Python’s standard-library sqlite3, and it supports durable writes via fsync=True.

2) RQ

RQ is a simple Redis-backed queue with a low barrier to entry. It has explicit job statuses, custom job metadata, dependencies, groups, callbacks, execution results/history, and a lightweight separate dashboard for monitoring. Workers are simple background Python processes.

3) Dramatiq

Dramatiq is a background task library focused on simplicity, reliability, and performance. It supports Redis or RabbitMQ brokers, automatic retries with exponential backoff, dead letters, time limits, groups/pipelines, optional Prometheus middleware, and optional result storage. It is stronger than RQ on execution controls, but requires more infrastructure and more custom work for app-facing progress/state UX.

4) Prefect

Prefect is full workflow orchestration, not just a queue. It has explicit flow/task states, a self-hosted server backed by a database and UI, workers/work pools, and a background-task architecture for web apps. It is much richer operationally, but it introduces a real orchestration layer and more moving parts than your MVP appears to want.

5) Temporal

Temporal is the strongest option for durable execution. Its workflow executions are durable, reliable, replayable from event history, and resumable after failures; but it requires a Temporal Service plus workers, and self-hosting production Temporal has substantial engineering overhead. Excellent system, wrong default for this MVP unless resumability is a top-tier requirement from day one.

6) APScheduler

APScheduler is best understood as a scheduler for “run this later / on a schedule”, not as the primary runtime for a multi-stage document-processing pipeline. It has persistent job stores and event hooks, but its model is about scheduled jobs plus executors, not durable staged workflow execution. It is useful for periodic maintenance jobs in Paper Table Agent, but not as the main runner.

Comparison table
Library	Simplicity	Local deployment	Reliability	Progress visibility	Checkpoint / resume	Maintenance burden	MVP fit	Sources
Huey	High	Excellent — can run with SQLite only	Medium-high for single-user/local	Medium — signals + result handles, but app UI should own progress	Medium if you implement stage-boundary checkpoints in your DB; not true mid-function replay	Low	Best default	
RQ	High	Good, but needs Redis/Valkey	Medium-high	High — statuses, meta, groups, results, dashboard	Medium with app-owned stage checkpoints	Low-medium	Strong alternative if Redis is acceptable	
Dramatiq	Medium	Good, but needs Redis or RabbitMQ	High among lightweight queues	Medium — middleware/metrics exist, but UX is more DIY	Medium with app-owned stage checkpoints	Medium	Good, but slightly more infra/ops than MVP needs	
Prefect	Medium-low	Medium — local server is easy, but it is a real orchestration stack	High	High — states + UI + server APIs	Higher than queue libs	High	Too much orchestration for current MVP	
Temporal	Low	Low-medium — dev server exists, production setup is substantial	Very high	High	Very high — durable replay/resume from event history	Very high	Overkill unless durable workflow replay is a core requirement now	
APScheduler	High	High	Medium for scheduled jobs	Low-medium — event listeners	Low for this use case	Low	Use only for cron-like side jobs	
Recommended MVP choice
Choose: Huey + app-owned staged runner

That combination best matches all of these at once:

Local-first, single-user

Deterministic staged pipeline

No graph-first orchestration

Background execution for longer stages

Reasonable resumability without heavy infrastructure

Huey is the only serious candidate in this set that gives you a real queue/consumer model while also letting you stay on SQLite only if you want. It supports the execution patterns you will likely need for Paper Table Agent: background workers, retries, scheduling, reschedule/revoke, locks, and signals, plus process workers for CPU-heavy stages.

Why not RQ as the default?

RQ is excellent and may actually be the better operator experience if you are happy to ship Redis. Its job model is clearer and its visibility story is better out of the box. But Redis is still an extra runtime dependency, and your stated goal is to keep the runtime simple. For a local-first MVP, that tips the balance toward Huey.

Why not Dramatiq?

Dramatiq is probably the most robust “pure queue library” of the Redis/RabbitMQ class here, but it still requires extra infrastructure and its result/progress story is intentionally secondary to “update your real database instead.” That is a sane philosophy, but it does not beat Huey on MVP simplicity.

Why not Prefect or Temporal?

Because they solve a bigger problem than you currently need solved. Prefect introduces a server/UI/orchestration layer; Temporal introduces a full durable workflow system with a service and workers. Both are valuable, but both move you away from “simple local runtime” and toward platform engineering.

Recommended architecture fit
1) Keep the workflow deterministic in your own code

Define the pipeline as an explicit ordered stage list in Python, not as a library-native graph:

ingest → parse → match → retrieve → extract → evidence_recovery → export → evaluation

The queue library should run one stage job at a time for a given run. It should not decide stage ordering. This keeps behavior deterministic and easy to reason about.

2) Persist run state in the app database

Use a small runtime schema such as:

pipeline_run

stage_run

artifact

attempt

event_log

For each stage, store:

status

attempt count

started/finished timestamps

input artifact refs

output artifact refs

error payload

percent / step progress

worker/runtime metadata

That gives you app-level observability independent of the queue library.

3) Define “resume” as resume from the last committed stage boundary

This is the most important MVP scoping decision.

Lightweight queue libraries do not give you Temporal-style durable replay of arbitrary in-flight Python execution. Temporal does; that is one of its defining features. So for MVP, the practical and honest design is:

stage functions are idempotent

stage outputs are written to disk/db

stage completion is committed atomically

after restart, you look for the first incomplete stage and enqueue that next

That is usually enough for document-processing pipelines and is much cheaper than adopting Temporal now.

4) Use Huey features only for execution concerns

For Huey specifically, the fit is:

SqliteHuey backend for single-machine persistence

process workers for CPU-heavy parse/extract steps

thread workers for I/O-heavy retrieval steps

retries for transient network/model failures

task locks where duplicate execution would be harmful

consumer signals to mirror queue events into your own run/event tables

5) Keep progress in your own app model

Even if the queue library exposes status, your UI will be much better if the app owns progress semantics such as:

current stage

completed stages / total stages

item-level progress within a stage

retry count

human-readable error reason

cancel requested / canceled / resumed

Huey signals and result handles are enough to support this, but the truth should live in your app DB, not in queue internals.

6) Use APScheduler only for side jobs

APScheduler is still useful for tasks like:

cleanup of old artifacts

periodic reindexing

nightly verification sweeps

backup jobs

But not as the main pipeline runtime.

Open questions

Do you want to ship zero extra services?
If yes, Huey stays the best answer. If no, RQ becomes more attractive because Redis buys you better visibility and ecosystem support.

How important is step-level resume inside a long-running stage?
If “very,” you are already drifting toward Temporal territory.

Will runs stay single-machine for the foreseeable MVP?
If yes, SQLite-backed local execution is a feature, not a bug. If you expect multi-worker or remote execution soon, Redis-backed RQ or Dramatiq may age more gracefully.

Do you want a built-in operations UI now?
If yes, Prefect gives the richest built-in experience, but with a real orchestration stack; RQ gives a lighter middle ground with rq-dashboard.

Will you need human pause/resume and inspection inside a running workflow, not just between stages?
If yes, Prefect or Temporal may become justified earlier.

My concrete MVP recommendation is:

Use Huey with SqliteHuey, but make Paper Table Agent’s own SQLite runtime tables the source of truth for stage ordering, progress, retries, artifacts, and resume.