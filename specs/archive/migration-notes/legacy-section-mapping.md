# Legacy Section Mapping

## Purpose

This file records the disposition of every major section or content block from the legacy spec stack.

Disposition values:

- moved to new normative spec file
- moved to archive file
- duplicated intentionally with canonical owner identified
- removed as exact duplicate or noise, with justification

## Main app legacy `specs/spec.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Summary | duplicated intentionally with canonical owner identified | `../../product/overview.md` and `../../archive/main-app/legacy-spec.md` | Current product summary is normative in `product/overview.md`; full legacy wording remains archived. |
| Document role | moved to archive file | `../../archive/main-app/legacy-spec.md` | Document-role mechanics are historical and no longer needed in the normative body. |
| End-to-end workflow | moved to new normative spec file | `../../product/main-app.md` | Current workflow is normative there; detailed original wording remains archived. |
| Operator-visible run states | moved to new normative spec file | `../../product/main-app.md` | Archived wording remains preserved for historical detail. |
| Config authority and operator surface | moved to new normative spec file | `../../product/main-app.md` | Normative owner is current main-app spec; full original wording archived. |
| Provider contract, readiness, and mode truth | moved to new normative spec file | `../../product/main-app.md` | Detailed legacy wording also preserved in archive. |
| Problem statement | moved to new normative spec file | `../../product/overview.md` | |
| Goals | moved to new normative spec file | `../../product/overview.md` | |
| Non-goals | moved to new normative spec file | `../../product/overview.md` | |
| Actors | moved to new normative spec file | `../../product/overview.md` | |
| Product principles | moved to archive file | `../../archive/main-app/legacy-spec.md` | Principles are informative but not a separate normative owner now. |
| Product quality bar | moved to new normative spec file | `../../product/main-app.md` | Preserved more concisely as current quality expectations; legacy depth archived. |
| User stories | moved to archive file | `../../archive/main-app/legacy-spec.md` | Useful context preserved, but not duplicated into current normative files. |
| Scope | moved to new normative spec file | `../../product/overview.md` | |
| Inputs | moved to new normative spec file | `../../product/main-app.md` | |
| Outputs | moved to new normative spec file | `../../product/main-app.md` and `../../contracts/run-bundle.md` | Shared artifact rules centralized in `contracts/run-bundle.md`. |
| Proposal/review terminology | moved to archive file | `../../archive/main-app/legacy-spec.md` | Terminology block preserved for reference. |
| Functional requirements FR-1..FR-14 | duplicated intentionally with canonical owner identified | `../../product/main-app.md`, `../../product/review-workflow.md`, and `../../archive/main-app/legacy-spec.md` | Current requirements are normative in the split product files; the full FR matrix is archived intact. |
| Review and trust requirements TR-1..TR-4 | duplicated intentionally with canonical owner identified | `../../product/review-workflow.md` and `../../archive/main-app/legacy-spec.md` | Current trust workflow is normative in `review-workflow.md`; original detailed trust requirements preserved. |
| Non-functional requirements NFR-1..NFR-9 | moved to archive file | `../../archive/main-app/legacy-spec.md` | NFR detail remains future-useful but is not restated in full as current normative text. |
| Key behavioral rules | duplicated intentionally with canonical owner identified | `../../product/main-app.md`, `../../contracts/run-bundle.md`, `../../contracts/proposals-and-evidence.md`, and `../../archive/main-app/legacy-spec.md` | Shared rules are centralized normatively; legacy integrated wording preserved. |
| Acceptance criteria AC-1..AC-19 | duplicated intentionally with canonical owner identified | `../../product/main-app.md`, `../../product/overview.md`, and `../../archive/main-app/legacy-spec.md` | Current acceptance criteria are normative; full prior list preserved. |
| MVP boundary | moved to new normative spec file | `../../product/overview.md` | |
| Success metrics | moved to new normative spec file | `../../product/overview.md` | |
| Assumptions | moved to new normative spec file | `../../product/overview.md` | |
| Future extensions | moved to new normative spec file | `../../product/overview.md` | Current file keeps the boundary; full exploratory detail remains archived. |
| Relationship to `plan.md` | moved to archive file | `../../archive/main-app/legacy-spec.md` | Historical document-stack note. |
| Appendix | moved to archive file | `../../archive/main-app/legacy-spec.md` | Historical supporting material preserved. |

## Main app legacy `specs/plan.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Purpose | duplicated intentionally with canonical owner identified | `../../plan.md` and `../../archive/main-app/legacy-plan.md` | Current plan remains supportive; original preserved. |
| Relationship to other documents | moved to archive file | `../../archive/main-app/legacy-plan.md` | Historical stack description preserved. |
| Implementation handoff rules | moved to archive file | `../../archive/main-app/legacy-plan.md` | Useful for history, not normative current behavior. |
| Definition of done | moved to archive file | `../../archive/main-app/legacy-plan.md` | Historical planning context preserved. |
| Constraints and non-goals | moved to archive file | `../../archive/main-app/legacy-plan.md` | |
| Technical decisions TD-1..TD-11 | moved to archive file | `../../archive/main-app/legacy-plan.md` | Key conclusions also summarized in `../../plan.md`; full decision detail preserved here. |
| Alternatives considered | moved to archive file | `../../archive/main-app/legacy-plan.md` | |
| Supporting notes | moved to archive file | `../../archive/main-app/legacy-plan.md` | |
| System architecture | moved to new normative spec file | `../../architecture/integration.md` and `../../archive/main-app/legacy-plan.md` | Current integration boundaries are normative; fuller architecture wording archived. |
| High-level architecture | moved to new normative spec file | `../../architecture/monorepo-layout.md` and `../../archive/main-app/legacy-plan.md` | |
| MVP stack | moved to archive file | `../../archive/main-app/legacy-plan.md` | Historical technical direction retained. |
| One-config-file model | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Pipeline stages | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Traceability | moved to archive file | `../../archive/main-app/legacy-plan.md` | Migration traceability now lives separately in this `migration-notes/` directory. |
| UI architecture | moved to archive file | `../../archive/main-app/legacy-plan.md` | Informative historical technical design. |
| API and service architecture | moved to archive file | `../../archive/main-app/legacy-plan.md` | |
| Parser strategy | moved to archive file | `../../archive/main-app/legacy-plan.md` | Summarized in `../../plan.md`; full detail archived. |
| Matching | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Retrieval | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Extraction | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Run modes | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Style-profile preprocessing | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Evidence strategy | moved to new normative spec file | `../../contracts/proposals-and-evidence.md` and `../../archive/main-app/legacy-plan.md` | Shared semantics centralized; full detail archived. |
| Validation and recovery | moved to archive file | `../../archive/main-app/legacy-plan.md` | Detailed technical rationale preserved. |
| Table and figure handling | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Evaluation boundary | moved to archive file | `../../archive/main-app/legacy-plan.md` | Benchmark boundary detail preserved. |
| Export strategy | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Persistence | moved to new normative spec file | `../../contracts/run-bundle.md` and `../../archive/main-app/legacy-plan.md` | |
| Runtime and background jobs | moved to archive file | `../../archive/main-app/legacy-plan.md` | |
| Model and provider strategy | moved to new normative spec file | `../../product/main-app.md` and `../../archive/main-app/legacy-plan.md` | |
| Evaluation and measurement strategy | moved to archive file | `../../archive/main-app/legacy-plan.md` | Useful detail, not current normative owner. |
| Testing strategy | moved to new normative spec file | `../../process/testing-strategy.md` and `../../archive/main-app/legacy-plan.md` | |
| Risks and mitigations R-1..R-7 | duplicated intentionally with canonical owner identified | `../../plan.md` and `../../archive/main-app/legacy-plan.md` | Current high-level risks are summarized in `plan.md`; original detail preserved here. |
| Open technical questions | duplicated intentionally with canonical owner identified | `../../plan.md` and `../../archive/main-app/legacy-plan.md` | |
| Concise summary | moved to archive file | `../../archive/main-app/legacy-plan.md` | |

## Main app legacy `specs/research.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Purpose | moved to archive file | `../../archive/main-app/legacy-research.md` | |
| How to use this document | moved to archive file | `../../archive/main-app/legacy-research.md` | |
| Confidence levels | moved to archive file | `../../archive/main-app/legacy-research.md` | |
| Research questions | moved to archive file | `../../archive/main-app/legacy-research.md` | |
| Executive summary | moved to archive file | `../../archive/main-app/legacy-research.md` | |
| Research topics 0..16 | moved to archive file | `../../archive/main-app/legacy-research.md` | These topics contain rationale, alternatives, and implementation detail that should be preserved, not re-compressed into current normative docs. Selected conclusions are summarized in `../../plan.md` and current normative owners. |
| Open questions | duplicated intentionally with canonical owner identified | `../../plan.md` and `../../archive/main-app/legacy-research.md` | Current open questions are summarized in `plan.md`; detailed research framing remains archived. |
| Rejected alternatives | moved to archive file | `../../archive/main-app/legacy-research.md` | |
| Recommendations | moved to archive file | `../../archive/main-app/legacy-research.md` | |
| Summary | moved to archive file | `../../archive/main-app/legacy-research.md` | |

## Eval legacy `tools/eval/specs/spec.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Purpose | moved to new normative spec file | `../../tools/eval.md` | Legacy wording preserved in archive. |
| Product surface | moved to new normative spec file | `../../tools/eval.md` | |
| Supported inputs | moved to new normative spec file | `../../tools/eval.md` and `../../contracts/run-bundle.md` | |
| Run bundle contract | duplicated intentionally with canonical owner identified | `../../contracts/run-bundle.md` and `../../archive/eval/legacy-spec.md` | Shared contract owner is `run-bundle.md`. |
| Eval-mode provenance | moved to new normative spec file | `../../contracts/run-bundle.md` | |
| Gold input contract | moved to archive file | `../../archive/eval/legacy-spec.md` | Detailed eval-only input detail preserved in archive for now. |
| Scoring behavior | moved to new normative spec file | `../../tools/eval.md`, `../../contracts/eval-summary.md` | |
| Evidence behavior | moved to new normative spec file | `../../contracts/proposals-and-evidence.md` and `../../tools/eval.md` | |
| Outputs | moved to new normative spec file | `../../contracts/eval-summary.md` and `../../tools/eval.md` | |
| Reported metrics | moved to new normative spec file | `../../contracts/eval-summary.md` | |
| Non-goals | moved to new normative spec file | `../../tools/eval.md` | |
| Acceptance criteria | moved to archive file | `../../archive/eval/legacy-spec.md` | Preserved verbatim; not fully restated in current concise tool spec. |

## Eval legacy `tools/eval/specs/plan.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Purpose | moved to archive file | `../../archive/eval/legacy-plan.md` | |
| Architecture constraints | moved to archive file | `../../archive/eval/legacy-plan.md` | |
| Canonical module layout | moved to archive file | `../../archive/eval/legacy-plan.md` | Detailed implementation direction preserved. |
| CLI direction | moved to archive file | `../../archive/eval/legacy-plan.md` | |
| Data boundaries | moved to archive file | `../../archive/eval/legacy-plan.md` | |
| Loading and contract validation direction | moved to new normative spec file | `../../contracts/run-bundle.md` and `../../archive/eval/legacy-plan.md` | Shared contract rules centralized; execution detail archived. |
| Scoring pipeline direction | moved to archive file | `../../archive/eval/legacy-plan.md` | Useful implementation detail preserved. |
| Field resolution direction | moved to archive file | `../../archive/eval/legacy-plan.md` | |
| Evidence direction | moved to new normative spec file | `../../contracts/proposals-and-evidence.md` and `../../archive/eval/legacy-plan.md` | |
| Output architecture | moved to new normative spec file | `../../contracts/eval-summary.md` and `../../archive/eval/legacy-plan.md` | |
| Judge integration direction | moved to archive file | `../../archive/eval/legacy-plan.md` | |
| Verification direction | moved to new normative spec file | `../../process/testing-strategy.md` and `../../archive/eval/legacy-plan.md` | |
| Deliberately excluded architecture | moved to archive file | `../../archive/eval/legacy-plan.md` | |

## Eval legacy `tools/eval/specs/research.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| All rationale sections beginning with `Why ...` | moved to archive file | `../../archive/eval/legacy-research.md` | These are still informative and should stay available without being treated as current normative truth. |
| Open questions | duplicated intentionally with canonical owner identified | `../../plan.md` and `../../archive/eval/legacy-research.md` | |
| Deferred items | moved to archive file | `../../archive/eval/legacy-research.md` | |

## Eval legacy `tools/eval/specs/tasks.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| All implementation-task sections | duplicated intentionally with canonical owner identified | `../../tasks.md` and `../../archive/eval/legacy-tasks.md` | Root `tasks.md` is the canonical owner; tool-local task history remains archived. |
| Retired batch framing appendix | moved to archive file | `../../archive/eval/legacy-tasks.md` | Historical only. |

## Optimizer legacy `tools/optimizer/specs/spec.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Purpose | moved to new normative spec file | `../../tools/optimizer.md` | |
| Product behavior | moved to new normative spec file | `../../tools/optimizer.md` | |
| Study modes | moved to new normative spec file | `../../tools/optimizer.md` | |
| Benchmark policy | moved to new normative spec file | `../../tools/optimizer.md` | |
| Candidate bundle contract | moved to new normative spec file | `../../contracts/optimizer-candidate.md` | |
| Acceptance contract | moved to new normative spec file | `../../contracts/optimizer-candidate.md` | |
| Artifact contract | moved to new normative spec file | `../../contracts/optimizer-candidate.md` and `../../contracts/eval-summary.md` | |
| Reporting contract | moved to archive file | `../../archive/optimizer/legacy-spec.md` | Detailed report semantics preserved for future reference. |
| Non-goals | moved to new normative spec file | `../../tools/optimizer.md` | |
| Acceptance criteria | moved to archive file | `../../archive/optimizer/legacy-spec.md` | Preserved verbatim. |

## Optimizer legacy `tools/optimizer/specs/plan.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Technical direction | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| Implementation principles | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| CLI architecture | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| Module map | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| Data flow | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| Compare flow | moved to new normative spec file | `../../tools/optimizer.md` and `../../archive/optimizer/legacy-plan.md` | |
| Optimize flow | moved to new normative spec file | `../../tools/optimizer.md` and `../../archive/optimizer/legacy-plan.md` | |
| Preflight flow | moved to new normative spec file | `../../tools/optimizer.md` and `../../archive/optimizer/legacy-plan.md` | |
| Holdout validation flow | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| Summarize flow | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| Integration contracts | moved to new normative spec file | `../../architecture/integration.md`, `../../contracts/eval-summary.md`, `../../contracts/optimizer-candidate.md` | |
| Persistence contract | moved to new normative spec file | `../../contracts/optimizer-candidate.md` | |
| Current architecture limits | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |
| Quality expectations | moved to archive file | `../../archive/optimizer/legacy-plan.md` | |

## Optimizer legacy `tools/optimizer/specs/research.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| Why this product shape | moved to archive file | `../../archive/optimizer/legacy-research.md` | |
| Key rationale | moved to archive file | `../../archive/optimizer/legacy-research.md` | |
| Tradeoffs | moved to archive file | `../../archive/optimizer/legacy-research.md` | |
| Open questions | duplicated intentionally with canonical owner identified | `../../plan.md` and `../../archive/optimizer/legacy-research.md` | |
| Deferred items | moved to archive file | `../../archive/optimizer/legacy-research.md` | |
| Historical implementation framing appendix | moved to archive file | `../../archive/optimizer/legacy-research.md` | |

## Optimizer legacy `tools/optimizer/specs/tasks.md`

| Legacy section | Disposition | Destination | Notes |
| --- | --- | --- | --- |
| All implementation-task sections | duplicated intentionally with canonical owner identified | `../../tasks.md` and `../../archive/optimizer/legacy-tasks.md` | Root `tasks.md` is canonical; tool-local history stays archived. |

## Exact duplicate and noise removals

| Legacy content block | Disposition | Justification |
| --- | --- | --- |
| Repeated shared run-bundle contract wording across main app and eval specs | removed as exact duplicate or noise, with justification | Canonical owner is `../../contracts/run-bundle.md`; repeated copies would reintroduce drift. |
| Repeated proposal and evidence taxonomy wording across main app and eval materials | removed as exact duplicate or noise, with justification | Canonical owner is `../../contracts/proposals-and-evidence.md`. |
| Repeated optimizer consumption wording that duplicated eval-summary field definitions | removed as exact duplicate or noise, with justification | Canonical owner is `../../contracts/eval-summary.md`. |
| Separate per-tool task trackers as current status owners | removed as exact duplicate or noise, with justification | Canonical owner is `../../tasks.md`; archived task files preserve history. |