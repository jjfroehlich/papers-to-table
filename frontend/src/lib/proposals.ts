import type { ProposalRecord } from './types'

export const proposalFilters = ['all', 'pending', 'figure', 'needs_evidence'] as const

export type ProposalFilter = (typeof proposalFilters)[number]

export const nonActionableProposalStates = ['blocked', 'error', 'skipped'] as const

export function isActionableProposal(proposal: ProposalRecord): boolean {
  return Boolean(proposal.proposed_value) && !nonActionableProposalStates.includes(proposal.proposal_state as 'blocked' | 'error' | 'skipped')
}

export function filterProposals(proposals: ProposalRecord[], filter: ProposalFilter): ProposalRecord[] {
  if (filter === 'pending') return proposals.filter((proposal) => proposal.review_decision === 'no_decision')
  if (filter === 'figure') return proposals.filter((proposal) => proposal.source_mode === 'vision')
  if (filter === 'needs_evidence') return proposals.filter((proposal) => proposal.needs_more_evidence)
  return proposals
}
