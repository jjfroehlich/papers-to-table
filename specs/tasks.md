# Current status and backlog

## Verified current status

- [x] Main app has one central repo-level command surface for install, review startup, preflight, and headless use
- [x] Headless mode supports explicit `--accept-all` and rejects unattended export when review is still pending
- [x] Headless auto-accept is recorded in decision artifacts and reviewer summaries
- [x] Eval is packaged as an installable companion CLI
- [x] Optimizer has an explicit canonical `optimize_one_model.json` preset alongside compare and overnight presets
- [x] README and docs now expose one clear install/run/navigation path
- [x] Integrated current truth now exists in `specs/spec.md`
- [x] `specs/spec.md`, `specs/plan.md`, and `specs/tasks.md` are the canonical markdown truth files
- [x] Docs are now buildable as a local/static MkDocs Material manual
- [x] Repo command surface includes docs serve/build wrappers
- [x] Reusable headless agent skill exists under `agent-skills/papers-to-table/`
- [x] Main-app LM Studio provider has configurable request, vision request, model load, model unload, and lock wait timeouts
- [x] Main-app LM Studio provider serializes load, unload, probe, text completion, and vision completion calls through a shared lock by default
- [x] Eval LM Studio judge serializes model load, model unload, and completion calls through the same shared lock by default
- [x] Eval remains judge-major for text judging: deterministic scoring first, then grouped judge/model/settings batches
- [x] Optimizer suite/replicate execution keeps reports, plots, trust caveats, recommended default, and raw winner outputs explicit
- [x] Main-app architecture Mermaid rendering is configured and labels are Mermaid-safe
- [x] Manual pages explain backend extraction, eval judging, and optimizer proposal-before-judging phases
- [x] Spec governance no longer treats scattered subfolder markdown as normative truth

## Current backlog

- [ ] Continue removing personal-path assumptions from real benchmark preset examples
- [ ] Refresh screenshots when the next visible UI workflow change lands
- [ ] Pointer-replace or move older compatibility markdown under `specs/product/`, `specs/tools/`, `specs/contracts/`, `specs/architecture/`, and `specs/process/` into `specs/archive/` after downstream links are updated
- [x] Add optimizer benchmark suite config validation
- [x] Add optimizer replicate config validation
- [x] Add optimizer suite and replicate orchestration
- [x] Add optimizer aggregation artifacts for benchmark-level and suite-level summaries
- [x] Update optimizer reports and plots with replicate caveats and `n=1` warnings
- [x] Replace old optimizer one-benchmark execution branches with canonical suite and replicate execution
- [x] Migrate checked-in optimizer configs to explicit benchmark suites and replicate settings
