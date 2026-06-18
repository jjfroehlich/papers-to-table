import type { EnrichedProposal } from '../types'

export const REASON_CODE_LABELS: Record<string, { label: string; title: string }> = {
  insufficient_evidence: {
    label: 'Insufficient evidence',
    title: 'The system found context, but not enough decisive support for a value.',
  },
  conflicting_evidence: {
    label: 'Conflicting evidence',
    title: 'The system found competing or inconsistent candidates.',
  },
  ambiguous_evidence: {
    label: 'Ambiguous evidence',
    title: 'The available context was relevant but ambiguous.',
  },
  approximate_anchor: {
    label: 'Approximate anchor',
    title: 'The evidence location was approximate rather than an exact text anchor.',
  },
  anchor_fallback: {
    label: 'Anchor fallback',
    title: 'The system used a fallback evidence location when exact anchoring was unavailable.',
  },
  retrieval_empty: {
    label: 'Retrieval empty',
    title: 'Retrieval returned no useful candidate context for this target cell.',
  },
  explicitly_not_reported: {
    label: 'Explicitly not reported',
    title: 'The paper directly says this information was not measured or not reported.',
  },
  not_reported: {
    label: 'Not reported',
    title: 'The model concluded the applicable field is not reported in the paper.',
  },
  schema_not_applicable: {
    label: 'Not applicable by schema',
    title: 'This field or cell does not apply to the paper.',
  },
  provider_error: {
    label: 'Provider error',
    title: 'A model provider or runtime failure prevented a usable extraction.',
  },
  parser_error: {
    label: 'Parser error',
    title: 'A parser failure prevented a usable extraction.',
  },
  invalid_model_output: {
    label: 'Invalid model output',
    title: 'The model response could not be parsed into the expected structure.',
  },
}

export function formatReasonCode(code: string): { label: string; title: string } {
  return REASON_CODE_LABELS[code] ?? { label: code.replace(/_/g, ' '), title: code }
}

export function isPlaceholderValue(value: unknown): boolean {
  if (value === null || value === undefined) return true
  const normalized = String(value).trim().toLowerCase()
  return normalized === '' || normalized === 'unclear' || normalized === 'no value proposed'
}

export function proposalConclusionLabel(proposal: Pick<EnrichedProposal, 'proposal_status' | 'proposed_value'>): string {
  switch (proposal.proposal_status) {
    case 'no_data':
      return 'No data reported'
    case 'not_applicable':
      return 'Not applicable'
    case 'not_attempted':
      return 'Not attempted'
    case 'error':
      return 'Extraction error'
    case 'unresolved':
      return isPlaceholderValue(proposal.proposed_value) ? 'No value proposed' : String(proposal.proposed_value)
    case 'value_proposed':
    default:
      return proposal.proposed_value ?? 'No value proposed'
  }
}
