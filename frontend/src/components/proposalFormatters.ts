/**
 * Shared display formatters for proposal state, support label, and warning flags.
 */
import type { ProposalState, SupportLabel, WarningStatusCategory } from '../types'

export function proposalStateDisplay(state: ProposalState): string {
  switch (state) {
    case 'actionable': return 'Actionable'
    case 'blocked': return 'Blocked'
    case 'unclear': return 'Unclear'
    case 'skipped': return 'Skipped'
    case 'error': return 'Error'
    default: return state
  }
}

export function supportLabelDisplay(label: SupportLabel): string {
  switch (label) {
    case 'strong_evidence': return 'Strong evidence'
    case 'moderate_evidence': return 'Moderate evidence'
    case 'weak_evidence': return 'Weak evidence'
    case 'no_evidence': return 'No evidence'
    default: return label
  }
}

export function flagDisplay(flag: WarningStatusCategory): string {
  switch (flag) {
    case 'ambiguous_match': return '⚠ Ambiguous match'
    case 'duplicate_row_conflict': return '⚠ Duplicate row conflict'
    case 'weak_evidence': return '⚠ Weak evidence'
    case 'quote_page_fallback': return 'ℹ Quote+page fallback'
    case 'figure_derived': return 'ℹ Figure-derived'
    case 'no_reviewed_verified_cells': return 'ℹ No reviewed verified cells'
    case 'completed_with_warnings': return '⚠ Completed with warnings'
    default: return flag
  }
}
