import { describe, expect, it } from 'vitest'
import { formatReasonCode, proposalConclusionLabel } from './proposalDisplay'
import type { EnrichedProposal } from '../types'

const baseProposal: Pick<EnrichedProposal, 'proposal_status' | 'proposed_value'> = {
  proposal_status: 'value_proposed',
  proposed_value: 'candidate',
}

describe('proposalDisplay', () => {
  it.each([
    ['value_proposed', 'candidate', 'candidate'],
    ['value_proposed', null, 'No value proposed'],
    ['no_data', null, 'No data reported'],
    ['unresolved', null, 'No value proposed'],
    ['unresolved', 'unclear', 'No value proposed'],
    ['unresolved', 'candidate under review', 'candidate under review'],
    ['not_applicable', null, 'Not applicable'],
    ['not_attempted', null, 'Not attempted'],
    ['error', null, 'Extraction error'],
  ] as const)('renders %s / %s as %s', (proposalStatus, proposedValue, expected) => {
    expect(
      proposalConclusionLabel({
        ...baseProposal,
        proposal_status: proposalStatus,
        proposed_value: proposedValue,
      })
    ).toBe(expected)
  })

  it.each([
    ['insufficient_evidence', 'Insufficient evidence'],
    ['conflicting_evidence', 'Conflicting evidence'],
    ['ambiguous_evidence', 'Ambiguous evidence'],
    ['approximate_anchor', 'Approximate anchor'],
    ['anchor_fallback', 'Anchor fallback'],
    ['retrieval_empty', 'Retrieval empty'],
    ['explicitly_not_reported', 'Explicitly not reported'],
    ['not_reported', 'Not reported'],
    ['schema_not_applicable', 'Not applicable by schema'],
    ['provider_error', 'Provider error'],
    ['parser_error', 'Parser error'],
    ['invalid_model_output', 'Invalid model output'],
    ['future_reason_code', 'future reason code'],
  ])('formats reason code %s', (code, expected) => {
    expect(formatReasonCode(code).label).toBe(expected)
  })
})
