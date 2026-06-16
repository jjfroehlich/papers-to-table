You are working in the GitHub repo `jjfroehlich/papers-to-table`.

Goal:
Run an experimental implementation loop over selected ideas from `specs/improvement-ideas.md`. For each tested idea, create an isolated branch/worktree, implement the smallest useful testable change, run the appropriate checks/eval/dev-checks, and record the result in `specs/experiment-results.md`. Do not merge anything. The final output should let me inspect branches and read the results file to decide which ideas are worth deeper analysis, continuation, rejection, or combination.

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

   * Record experiment summaries and final updates in `specs/experiment-results.md` on `main`.
   * Do not merge experiment implementation branches back into `main`.
5. For each selected experiment, create a separate branch from the same base commit:

   * `exp/<YYYYMMDD>-<bundle-or-idea-slug>`
   * Use a separate git worktree for each branch if practical.
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

Suggested first loop:

* Bundle A1: Persistent Evidence Index retrieval-equivalent infrastructure
* Bundle A2: typed contextual retrieval text
* Bundle C1: uncertainty-gated recovery with current retrieval
* Bundle D2: targeted vision gate/planner/acceptance diagnostics
* one narrow Bundle E2 prompt-repair class only if it can be cleanly isolated
* optionally one Bundle F reliability/runtime experiment if it improves measurement quality for the above

Do not start with:

* Bundle B3 batch-then-verify
* large all-in-one retrieval + recovery + selector changes
* TurboVec or a new vector DB dependency
* broad model shopping
* broad prompt rewrites
* anything that makes results impossible to attribute

Model/config default:
Use the current local experimental default from `specs/improvement-ideas.md`, currently `google/gemma-4-12b`, unless the existing configs or latest specs clearly specify another default. If LM Studio/model availability prevents running a model-dependent experiment, record the branch as blocked and explain exactly what was missing.

Parallelism:

* You may use subagents or worktrees for implementation in parallel.
* Do not run multiple LM Studio/model-heavy benchmark/eval jobs concurrently unless the repo explicitly supports it safely. Prefer sequential execution for model calls so results are not confounded by resource contention.
* Lightweight code inspection, implementation, linting, and non-model tests can be parallelized.

For each experiment branch:

1. Read the relevant idea entry and bundle row in `specs/improvement-ideas.md`.
2. Define a single hypothesis in one sentence.
3. Define the smallest implementation that can test it.
4. Implement only that change.
5. Add config flags if needed so the experiment can be turned on/off.
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
* retrieval/index build overhead
* retrieval/evidence diagnostics
* recall-rescue eligibility/use/recovery counts
* vision trigger/skip/call/failure/no-hit/accepted evidence counts
* candidate hit rate / verified-use rate / rejection rate, where relevant
* tests passed/failed
* blockers
* interpretation

Result recording:
After each experiment, append a compact but useful result entry to `specs/experiment-results.md`.

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

Branch and commit behavior:

* Each experiment branch should contain its implementation and any branch-local result note if useful.
* Record aggregated experiment results in `specs/experiment-results.md` on `main`.
* Do not merge experiment branches.
* Do not delete branches.
* Do not open PRs unless explicitly useful; if you do, make them draft PRs and clearly label them as experiments.
* Do not change production defaults on `main`.
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

* Infrastructure-only experiments, such as Persistent Evidence Index A1, do not need immediate score improvement. Success means retrieval-output equivalence, stable runtime, clean diagnostics, and enabling later quality tests.
* Quality experiments, such as typed retrieval text or table-aware units, need score, hard-column, evidence-support, or score-per-minute improvement without broad regressions.
* Recovery and vision experiments must be judged by net score gain per added runtime/call and by recovered-correct versus recovered-wrong changes.
* Candidate-memory experiments must keep per-cell extraction authoritative and track candidate hit rate, verified-use rate, rejection rate, score, tokens, and runtime.
* Broad bundled improvements are not allowed in the first pass unless they follow the ablation order in `specs/improvement-ideas.md`.

Start by reading the repository docs and then propose a short loop plan before creating branches. After the plan, proceed with the loop unless something is truly blocked.
