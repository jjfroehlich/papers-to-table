# Proposals And Evidence Contract

- Status: Canonical contract
- Owner: Shared Contracts
- Consumed by: `app/backend/src/backend/app/`, `app/frontend/src/`, `tools/eval/`, `tools/optimizer/`

## Purpose

This file defines the canonical proposal, evidence, review-bucket, and diagnostic semantics used across the monorepo.

The proposal contract is canonical-only. Current runtime paths, artifacts, APIs, frontend types, eval, optimizer, and export diagnostics must not use legacy `ProposalState`, `SupportLabel`, persisted `state`, or persisted `support`.

## Canonical Proposal Fields

Each persisted proposal record uses these semantic fields:

| Field | Allowed values | Meaning |
|---|---|---|
| `proposal_status` | `value_proposed`, `no_data`, `unresolved`, `not_applicable`, `not_attempted`, `error` | What happened for the target cell. |
| `evidence_status` | `direct_strong`, `direct_weak`, `inferred_strong`, `inferred_weak`, `no_evidence`, `not_applicable` | How the proposal is supported by evidence. |
| `review_bucket` | `review`, `attention`, `diagnostic` | Where the proposal belongs in review surfaces. Serialized for convenience, but derived semantics are authoritative. |
| `reason_codes` | `list[str]` | Specific explanatory codes such as `retrieval_empty`, `anchor_fallback`, or `provider_error`. JSON accepts arbitrary strings for forward compatibility; backend-generated codes should use known constants where practical. |

`derive_review_bucket(proposal_status, evidence_status, reason_codes)` is the source of truth for `review_bucket`. Proposal creation must validate that serialized `review_bucket` matches the derived value.

Review APIs must not expose `review_bucket=diagnostic` records in `reviewable_only=true` responses. Cell-level unresolved target-cell outcomes with useful rationale, reason codes, retrieval diagnostics, candidate context, or manual-edit value should be classified as `review_bucket=attention`, not `diagnostic`. Global or pre-cell diagnostics such as unmatched PDFs, unmatched rows, duplicate-row conflicts, or pure `retrieval_empty` records remain in diagnostics rather than the default queue.

Main review rows and cards should use only the review decision marker, proposal-status dot, and evidence-status dot as compact status signals. The review UI does not show a separate proposal-level warning icon by default. The visible Attention filter is the set of proposals where either compact dot is not green: proposal status is not `value_proposed`, evidence status is not `direct_strong` or `inferred_strong`, or anchor fallback makes the evidence dot yellow. Figure or vision evidence is provenance, not a warning and not a separate row/card icon; it remains visible in evidence source labels and evidence detail.

## Proposal Status Values

| `proposal_status` | Meaning | Review interpretation |
|---|---|---|
| `value_proposed` | The extraction system proposes a concrete value for the table cell. | Normal review or attention depending on evidence. |
| `no_data` | The field applies, but the paper appears not to report the requested information. | Reviewable if evidence supports absence; attention if inferred or weak. |
| `unresolved` | The system could not determine a value or absence. | Attention if there is inspectable evidence/candidate text; diagnostic if no useful evidence exists. |
| `not_applicable` | The field/cell truly does not apply. | Diagnostic only. |
| `not_attempted` | A selected eligible target cell was intentionally not attempted. | Diagnostic only. |
| `error` | A technical or process error prevented a usable cell-level result. | Diagnostic only. |

## Evidence Status Values

| `evidence_status` | Meaning | Review interpretation |
|---|---|---|
| `direct_strong` | Direct evidence clearly supports the proposal. | High trust, normal review. |
| `direct_weak` | Directly relevant evidence exists but is ambiguous, incomplete, conflicting, or poorly anchored. | Needs attention. |
| `inferred_strong` | The proposal is inferred or calculated from good evidence. | Normal review, but label as inferred. |
| `inferred_weak` | The inference is plausible but under-supported. | Needs attention. |
| `no_evidence` | No usable supporting evidence exists. | Usually diagnostic unless there is still inspectable candidate text. |
| `not_applicable` | Evidence quality does not apply to this outcome. | Diagnostic/non-reviewable outcome. |

## Review Bucket Values

| `review_bucket` | Meaning | Review UI behavior |
|---|---|---|
| `review` | Normal review-surface item. | Appears in Pending and All reviewable views. |
| `attention` | Reviewable or inspectable, but should be checked carefully. | Appears in Attention and reviewable views. |
| `diagnostic` | Not a normal review item. | Hidden from the default review queue, but visible in diagnostics, summaries, and eval/export accounting. |

The serialized `review_bucket` remains the canonical routing field for APIs and artifacts. The review UI Attention filter is intentionally broader and visual: it includes any review-surface proposal whose proposal/evidence dots are not both green.

## Valid Proposal/Evidence Combinations

| `proposal_status` | `evidence_status` | `review_bucket` | Meaning | Example |
|---|---|---|---|---|
| `value_proposed` | `direct_strong` | `review` | Best case: concrete value directly supported by strong evidence. | Paper states “48 samples were analyzed.” |
| `value_proposed` | `direct_weak` | `attention` | Concrete value found, but direct evidence has a weakness. | Table has two possible sample-size columns; quote is ambiguous. |
| `value_proposed` | `inferred_strong` | `review` | Concrete value inferred or calculated from strong evidence. | Value derived from reported percentages and total `n`. |
| `value_proposed` | `inferred_weak` | `attention` | Concrete value inferred, but inference is uncertain. | Agent infers treatment group from figure caption but wording is vague. |
| `value_proposed` | `no_evidence` | `attention` or invalid | A value exists without usable evidence; this should normally be prevented or flagged. | Model proposed a value but no quote/evidence survived validation. |
| `value_proposed` | `not_applicable` | invalid | A value proposal must not have `evidence_status=not_applicable`. | Must fail validation. |
| `no_data` | `direct_strong` | `review` | Paper explicitly says the information was not measured or not reported. | “Sex was not recorded.” |
| `no_data` | `direct_weak` | `attention` | Direct text suggests absence, but not conclusively. | “Not assessed in this study” appears in a limited context. |
| `no_data` | `inferred_strong` | `review` or `attention` | Absence/not-reported status is inferred from strong context. | Methods clearly lack the assay required for the field. |
| `no_data` | `inferred_weak` | `attention` | Absence is plausible but under-supported. | No mention found in relevant sections, but retrieval was incomplete. |
| `no_data` | `no_evidence` | `attention` only when deliberate search was meaningful; otherwise avoid | A no-data conclusion without evidence is risky. | Allowed only with explicit `not_reported`/search diagnostics. |
| `no_data` | `not_applicable` | invalid | If the field does not apply, use `proposal_status=not_applicable`, not `no_data`. | Must fail validation. |
| `unresolved` | `direct_weak` | `attention` | Evidence exists, but the answer cannot be determined. | Conflicting values in text and table. |
| `unresolved` | `inferred_weak` | `attention` | Inference was attempted but remains uncertain. | Figure suggests a value, but axis/units are unclear. |
| `unresolved` | `no_evidence` | `attention` or `diagnostic` | Attention when a target-cell outcome has useful rationale, candidate text, ambiguity/conflict context, or reviewer-edit value; diagnostic for pure retrieval-empty/no-context cases. | Useful absence rationale versus retrieval returned nothing useful. |
| `unresolved` | `direct_strong` | unusual / usually invalid | Strong direct evidence should usually produce `value_proposed` or `no_data`; unresolved requires an explicit conflict/ambiguity reason. | Only allowed with `conflicting_evidence` or similar. |
| `unresolved` | `inferred_strong` | unusual / usually invalid | Strong inference should usually produce a proposal; unresolved requires an explicit conflict/ambiguity reason. | Only allowed with `conflicting_evidence` or similar. |
| `unresolved` | `not_applicable` | invalid | Evidence is not applicable only for diagnostic/process outcomes. | Must fail validation. |
| `not_applicable` | `not_applicable` | `diagnostic` | Field/cell truly does not apply. | Column only applies to in vivo studies; paper is in vitro. |
| `not_applicable` | anything else | invalid | Not-applicable outcomes must not carry evidence strength. | Must fail validation. |
| `not_attempted` | `not_applicable` | `diagnostic` | Cell was selected/eligible but intentionally not attempted. | Excluded by config or already handled elsewhere. |
| `not_attempted` | anything else | invalid | Not-attempted means no evidence evaluation happened. | Must fail validation. |
| `error` | `not_applicable` | `diagnostic` | Technical failure at cell level. | Provider timeout, parser failure, invalid structured output. |
| `error` | anything else | invalid | Error outcomes must not claim evidence support. | Must fail validation. |

## Review Bucket Derivation Rules

`derive_review_bucket(proposal_status, evidence_status, reason_codes)` must follow these rules. Earlier diagnostic rules take priority over attention/review rules.

| Condition | Derived `review_bucket` |
|---|---|
| `proposal_status in {error, not_attempted, not_applicable}` | `diagnostic` |
| `proposal_status=unresolved`, `evidence_status=no_evidence`, and reason codes are limited to diagnostic pre-cell/no-evidence causes such as `retrieval_empty`, `pdf_unmatched`, `row_unmatched`, or `duplicate_row_conflict` | `diagnostic` |
| `proposal_status=unresolved` and `evidence_status=no_evidence` with `insufficient_evidence`, `ambiguous_evidence`, `conflicting_evidence`, or other review-useful reason/context | `attention` |
| `evidence_status in {direct_weak, inferred_weak}` | `attention` |
| `reason_codes` contains `anchor_fallback`, `approximate_anchor`, `insufficient_evidence`, `ambiguous_evidence`, or `conflicting_evidence` | `attention`, unless already `diagnostic` |
| `proposal_status=value_proposed` and `evidence_status in {direct_strong, inferred_strong}` | `review` |
| `proposal_status=no_data` and `evidence_status=direct_strong` | `review` |
| `proposal_status=no_data` and `evidence_status in {direct_weak, inferred_weak, no_evidence}` | `attention` |

## Reason Codes

Known backend-generated reason codes should be centralized as constants. JSON schema should still accept arbitrary strings in `reason_codes` for forward compatibility.

Suggested known reason codes:

| Reason code | Meaning |
|---|---|
| `explicitly_not_reported` | The paper explicitly says the requested value was not measured/reported. |
| `not_reported` | The system concludes the value is not reported, but absence is not directly quoted. |
| `retrieval_empty` | Retrieval found no useful candidate text/evidence. |
| `insufficient_evidence` | Evidence exists, but does not support a confident answer. |
| `ambiguous_evidence` | Evidence is ambiguous. |
| `conflicting_evidence` | Multiple evidence items conflict. |
| `anchor_fallback` | Evidence exists, but exact anchoring failed and a degraded anchor was used. |
| `approximate_anchor` | Evidence anchor is approximate rather than exact. |
| `calculation` | The proposal required a calculation or derivation. |
| `schema_not_applicable` | Field/cell does not apply under the schema. |
| `cell_not_targeted` | Cell was not selected as an extraction target. |
| `column_excluded` | Column was excluded by configuration or scope. |
| `pdf_unmatched` | PDF could not be matched to a table row. |
| `row_unmatched` | Row could not be matched to a PDF. |
| `duplicate_row_conflict` | Matching produced a duplicate-row conflict. |
| `provider_error` | LLM/provider failed or returned unusable output. |
| `parser_error` | PDF parsing failed or produced unusable content. |
| `invalid_model_output` | Model output could not be parsed or validated. |

## Record Emission Policy

Canonical proposal records are emitted for target cells that entered the extraction/review pipeline and reached a cell-level semantic outcome.

- Emit a proposal record when a target cell was attempted and produced `value_proposed`, `no_data`, `unresolved`, or `error`.
- Emit a proposal record when a selected eligible target cell was intentionally not attempted, with `proposal_status=not_attempted` and a specific reason code.
- Prefer run/matching diagnostics, not proposal records, for failures before meaningful target-cell materialization: PDF unmatched, row unmatched, duplicate row conflict, or global configuration exclusion.
- Diagnostics must remain counted and visible even when they are not proposal records.
- Eval can consume run/matching diagnostics for accounting, but should not require synthetic proposal records for global pre-cell failures.

## Evidence Rules

Evidence is attached to proposals and remains inspectable.

Each proposal may carry multiple evidence items when useful, but one item is primary. Evidence ranking must be determined by source authority and field relevance, not by model-return order.

Direct text support should normally outrank weaker inferred support when both exist for the same field, unless the field definition explicitly requires reasoning or calculation to interpret the paper correctly.

Fallback evidence must be represented via `reason_codes` such as `anchor_fallback` or `approximate_anchor`, not as an `evidence_status`.

The main review UI should not use proposal-level warning icons as a primary signal. Attention and caution must be explained through proposal/evidence dots, `review_bucket`, `evidence_status`, and visible `reason_codes`. Operational warnings may still be persisted in run/diagnostic artifacts, but normal run and review screens do not need warning count badges.

## Evidence Types

Evidence items must distinguish at least:

- direct quote evidence
- inferred reasoning
- calculation-based justification
- approximate highlight evidence
- quote-plus-page evidence
- caption-grounded figure evidence
- visual-interpretation figure evidence

Figure-derived evidence must remain distinct from text-derived evidence even when both support the same proposal.

Conflicting figure-derived evidence should be persisted as competing evidence rather than discarded before final selection.

## Retrieval Evidence

Retrieval chunks include normal text/table/caption units plus `figure` chunks. A `figure` chunk represents one parsed figure with its figure reference, page, caption text, crop path, full-page path, bounding box, and nearby/section context when available.

The contract intentionally stays at whole-figure chunk granularity. Panel-level reasoning may happen inside the vision prompt over a whole figure crop, but persisted retrieval evidence remains figure-level.

## Anchor Validation

Persisted evidence, quote text, page references, and compatible source-text artifacts must remain available in the run bundle so eval can distinguish:

- `anchor_valid`
- `evidence_present_but_unvalidated`
- `anchor_invalid`
- `missing_evidence`

Anchor-validation outcomes are eval/diagnostic outcomes, not replacements for `evidence_status`.
