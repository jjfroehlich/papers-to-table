You are working in the GitHub repo `jjfroehlich/papers-to-table`.

Goal:
Run an experimental implementation loop over selected ideas from `specs/improvement-ideas.md`. For each tested idea, create an isolated branch/worktree from current `main`, implement the smallest useful testable change, and run the appropriate checks/eval/dev-checks. Do not merge experiment code into `main` during the loop. After all selected experiment branches finish, switch back to `main`, summarize the results in `specs/experiment-results.md` and `specs/improvement-ideas.md`, then give the chat summary. The final output should let me inspect branches and read the main-branch specs to decide which ideas are worth deeper analysis, rejection, combination, or a later explicit merge/port task.

Important:
This is an experiment loop, not a production implementation sprint. Prefer small, interpretable experiments over large bundled changes. Use the experiment bundles and ablation ladders in `specs/improvement-ideas.md` to choose the right unit of testing.

Repository context to inspect first:

* `README.md`
* `AGENTS.md`
* `specs/improvement-ideas.md`
* `specs/experiment-results.md`
* `specs/spec.md`
* `specs/eval-and-optimizer.md`
* `docs/main-app/architecture.md`
* `app/config.example.json`
* `tools/optimizer/`
* `tools/eval/`
* relevant backend files under `app/backend/src/backend/app/`

High-level workflow:

1. Start from latest `main`.
2. Confirm the working tree is clean. If not clean, stop and report.
3. Read `specs/improvement-ideas.md` and identify candidate experiments.
4. Use `main` as the aggregation point for documentation and experiment tracking:

   * Keep implementation code isolated to experiment branches while tests/dev-checks run.
   * After all selected experiment checks finish, switch back to `main` and record consolidated summaries in `specs/experiment-results.md`.
   * Update `specs/improvement-ideas.md` on `main` to remove, reprioritize, or add retest boundaries for decided ideas.
   * Do not merge experiment implementation branches back into `main` unless the user explicitly starts a separate merge/port task.
5. For each selected experiment, create a separate branch from the same base commit:

   * `exp/<YYYYMMDD>-<bundle-or-idea-slug>`
   * Use a separate git worktree for each branch if practical. Put worktrees under an ignored `.tmp/` path or an external sibling directory, not under a visible top-level `w/` folder.
6. A subagent may work on each branch, but the primary agent remains responsible for:

   * selecting experiments
   * ensuring isolation
   * checking results are comparable
   * collecting result summaries
   * updating `specs/experiment-results.md` on `main`
   * final synthesis

Experiment selection:
Do not blindly implement every idea. First create a short experiment plan from `specs/improvement-ideas.md`.

Prioritize experiments that are:

* low or moderate scope
* testable by dev-check or existing optimizer/eval infrastructure
* interpretable as a single ablation step
* aligned with the current `Current Priorities`
* not dependent on unimplemented prerequisite layers unless explicitly testing that prerequisite

Suggested loop:

Current main already includes the A1 prepared retrieval index substrate, a safer partial A2 prompt-header orientation change, D2 figure-review ROI diagnostics, A2b typed retrieval scoring without page-number tokens, A4 evidence-aware reranking, and F excluded-column join diagnostics as default behavior. The 2026-06-17 wave-2 branch dev-checks also tested A3, A4, A2b, and B1 against a matched `google/gemma-4-e4b` current-main baseline. Use those results before picking new work: A2b is current main behavior and the later A2b rechecks did not prove a regression; A4 is now a canonical deterministic reranking support layer after a post-port dev-check scored 0.56 with evidence quality 0.82; A3 is neutral with a large runtime penalty; B1 is a score/evidence regression.

The 2026-06-17 next-batch loop tested C2, D3, E2, and F from current main `da2ead2`. Use those results before picking new work: C2 prepared-index recovery, D3 figure value acceptance, and E2 max/best prompt guidance all had nominal score lifts but unacceptable evidence-quality regressions, so do not retest those exact implementations unchanged. F is now current eval/reporting behavior because it split intentionally excluded metadata proposals from true join failures.

Recommended starting points:

* Evidence-anchor and artifact-diff analysis for the C2/D3/E2 guardrail collapse before another prompt, recovery, or vision value-acceptance dev-check.
* Bundle F reliability/runtime work that does not change extraction values, such as structured-output replay/repair, judge calibration/adjudication reporting, or lazy rendering.
* Bundle B1b only as an offline/artifact candidate hit-rate audit or verifier/selector-gated candidate-memory test; do not inject mined candidates into every prompt unchanged.
* Optional D follow-up as shared page/figure batching or diagnostic-only accepted-correct analysis that preserves current value acceptance until evidence-anchor behavior is understood.
* Optional retrieval follow-up only if artifact diffs suggest a new parser-structured table/figure unit, schema-conditioned query, or retrieval diagnostic can explain hard-column misses beyond current A2b/A4 behavior.

Do not start with:

* A1 prepared-index infrastructure, exact A2 broad typed retrieval text, or D2 diagnostics-only instrumentation, because those have already been integrated or partially integrated into current main
* A2b typed retrieval scoring as a standalone branch, because it is now current main behavior
* A4 evidence-aware reranking as a standalone branch, because it is now current main behavior
* the rejected A3 line-based table-unit implementation unchanged
* the rejected B1 prompt-injected advisory candidate census unchanged
* broad current-retrieval recall rescue, because C1 was rejected
* the rejected C2 prepared-index recall-rescue gate unchanged
* the rejected D3 figure value-override policy unchanged
* the rejected E2 max/best scoped prompt block unchanged
* the F excluded-column join diagnostics experiment unchanged, because it is now current eval behavior
* Bundle B3 batch-then-verify
* large all-in-one retrieval + recovery + selector changes
* TurboVec or a new vector DB dependency
* broad model shopping
* broad prompt rewrites
* anything that makes results impossible to attribute

Model/config default:
Use the current local experimental default from `specs/improvement-ideas.md`, currently `google/gemma-4-e4b`, unless the existing configs or latest specs clearly specify another default. If LM Studio/model availability prevents running a model-dependent experiment, record the branch as blocked and explain exactly what was missing.

Parallelism:

* You may use subagents or worktrees for implementation in parallel.
* Do not run multiple LM Studio/model-heavy benchmark/eval jobs concurrently unless the repo explicitly supports it safely. Prefer sequential execution for model calls so results are not confounded by resource contention.
* Lightweight code inspection, implementation, linting, and non-model tests can be parallelized.

For each experiment branch:

1. Read the relevant idea entry and bundle row in `specs/improvement-ideas.md`.
2. Define a single hypothesis in one sentence.
3. Define the smallest implementation that can test it.
4. Implement only that change.
5. Add branch-local config flags only when needed to isolate an experiment; do not merge flags into main unless they are a deliberate durable operator control. Prefer merging proven improvements as canonical behavior when the decision is clear.
6. Preserve default app behavior unless the branch is explicitly testing a changed default.
7. Add or update tests where practical.
8. Run the relevant checks.

Minimum checks:

* Run the repo’s standard dev-checks from the docs.
* At minimum try:

  * `python scripts/papers_to_table.py optimizer dev-check`
* Also run any faster targeted unit tests or backend/frontend checks that the repo documents.
* If a benchmark/eval preset exists for this class of change, run the smallest useful matched comparison.
* If a full benchmark is too expensive, run a documented smoke/dev comparison and clearly label the result as not decisive.

Baseline/comparison rules:

* Use the same base commit, model, config, dataset, and scoring settings wherever possible.
* For worktree dev-checks that modify backend, eval, or optimizer code, make sure the branch source paths are actually used by subprocesses. For backend-code branches, run with `PYTHONPATH=<branch>/app/backend/src;<branch>/tools/eval;<branch>/tools/optimizer` or an equivalent wrapper fix. A backend experiment run without branch `app/backend/src` on the main-app subprocess import path is invalid for backend-code decisions.
* If a baseline run from the same base/config already exists in `specs/experiment-results.md`, reuse it only if it is clearly comparable.
* Otherwise run or identify a matched baseline.
* Do not claim an idea improved the app unless it beats a comparable baseline on relevant metrics.
* Dev-check passing alone means “implementation is viable enough for further testing,” not “idea improves extraction.”

Metrics to capture when available:

* branch name
* commit SHA
* exact commands run
* config/preset names
* model/provider
* dataset/benchmark
* run bundle path(s)
* eval output path(s)
* aggregate score
* hard-column accuracy or notable column changes
* score-per-minute or runtime
* token usage if available
* structured-output errors/retries/repairs
* prepared retrieval index source counts (`built`, `disk`, `memory`) and build/load overhead
* retrieval/evidence diagnostics
* recall-rescue eligibility/use/recovery counts
* vision trigger/skip/call/failure/no-hit/dropped-reason/accepted-hit/accepted-evidence counts
* candidate hit rate / verified-use rate / rejection rate, where relevant
* tests passed/failed
* blockers
* interpretation

Result recording:
During branch work, collect enough result facts to avoid losing run ids, commits, metrics, and caveats. After the selected experiment batch completes, switch back to `main` and append compact but useful result entries to `specs/experiment-results.md`. Avoid leaving the only result summary inside an experiment branch.

Use a consistent format like:

```markdown
### YYYY-MM-DD: <experiment name>

| Field | Details |
|---|---|
| **Branch** | `<branch>` at `<commit_sha>` |
| **Idea / bundle** | `<idea heading>` / `<bundle step, e.g. A2>` |
| **Hypothesis** |  |
| **Implementation** |  |
| **Baseline** |  |
| **Commands** |  |
| **Metrics** |  |
| **Outcome** | `promising` / `neutral` / `regression` / `blocked` / `inconclusive` |
| **Interpretation** |  |
| **Next step** |  |
```

Keep results honest:

* `promising`: measurable improvement or clear diagnostic value without serious regression
* `neutral`: works but no meaningful improvement
* `regression`: worse score/runtime/reliability or unacceptable side effects
* `blocked`: could not run because of missing model/data/config/tooling
* `inconclusive`: implementation ran, but comparison was too weak to decide

If an experiment is clearly rejected or completed, update `specs/improvement-ideas.md` only if appropriate under its own rules. Otherwise leave the idea active and record only the experiment result.
Rejected exact implementations must get an explicit retest boundary in `specs/experiment-results.md` so future loops do not rerun the same idea blindly. If a broader idea remains promising, keep the broader idea active in `specs/improvement-ideas.md` with the rejected exact variant called out.

Branch and commit behavior:

* Each experiment branch should contain its implementation and any branch-local result note if useful.
* Record aggregated experiment results in `specs/experiment-results.md` on `main`.
* Do not merge experiment branches.
* Do not delete branches.
* Do not open PRs unless explicitly useful; if you do, make them draft PRs and clearly label them as experiments.
* Do not change production defaults on `main` during an experiment loop. Accepted improvements are merged or ported to `main` only in a later explicit merge task.
* Do not introduce large new dependencies unless the idea explicitly requires it and the experiment plan justifies it.

Failure handling:

* If an experiment gets too large, stop that branch and record it as blocked or split-needed.
* If a branch fails dev-check, try to fix normal implementation mistakes.
* Do not spend unlimited time rescuing a bad idea.
* If the implementation requires unrelated refactors, stop and record why.
* If results are noisy or judge disagreement is high, mark the conclusion as inconclusive rather than overclaiming.

Final synthesis:
After the loop, produce a final summary on `main` and in your response:

1. Experiments attempted.
2. Branches created.
3. Checks/evals run.
4. Results by outcome category.
5. Best candidate branches for deeper review.
6. Branches that should probably be abandoned.
7. Ideas that should be combined in the next loop.
8. Any updates made to `specs/experiment-results.md`.
9. Any ideas that should be moved, reprioritized, or clarified in `specs/improvement-ideas.md`.

Important interpretation rules:

* Current prepared-index behavior is baseline infrastructure. New infrastructure experiments still do not need immediate score improvement, but they must preserve retrieval-output equivalence, stable runtime, clean diagnostics, and enabling value for later quality tests.
* Quality experiments, such as table-aware units, evidence-aware reranking, typed retrieval-scoring ablations, or prompt repair, need score, hard-column, evidence-support, or score-per-minute improvement without broad regressions.
* Recovery and vision experiments must be judged by net score gain per added runtime/call and by recovered-correct versus recovered-wrong changes.
* Candidate-memory experiments must keep per-cell extraction authoritative and track candidate hit rate, verified-use rate, rejection rate, score, tokens, and runtime.
* Broad bundled improvements are not allowed in the first pass unless they follow the ablation order in `specs/improvement-ideas.md`.

Start by reading the repository docs and then propose a short loop plan before creating branches. After the plan, proceed with the loop unless something is truly blocked.
