/**
 * T085 — Proposal detail pane.
 *
 * Shows row context, target column definition, current value (Verify mode),
 * proposed value, support label, rationale, calculation, warning/status flags,
 * and primary/secondary evidence.
 */
import type { ProposalDetail } from '../types'
import { supportLabelDisplay, flagDisplay, proposalStateDisplay } from './proposalFormatters'

interface Props {
  proposal: ProposalDetail
  verifyMode: boolean
}

export function ProposalDetailPane({ proposal, verifyMode }: Props) {
  const colDef = proposal.column_definition as Record<string, string>
  const rowCtx = proposal.row_context as Record<string, string>

  return (
    <div className="proposal-detail-pane">
      <div className="detail-header">
        <div className="detail-title">
          <span className="column-name">{proposal.column_name}</span>
          <span className="row-id muted"> — {proposal.row_id}</span>
        </div>
        <div className="detail-badges">
          <span className={`state-badge state-${proposal.proposal_state}`}>
            {proposalStateDisplay(proposal.proposal_state)}
          </span>
          <span className={`support-badge support-${proposal.support_label}`}>
            {supportLabelDisplay(proposal.support_label)}
          </span>
        </div>
      </div>

      {proposal.status_flags.length > 0 && (
        <div className="flag-list">
          {proposal.status_flags.map((f) => (
            <span key={f} className={`flag flag-${f}`}>{flagDisplay(f)}</span>
          ))}
        </div>
      )}

      {colDef.description && (
        <div className="column-definition">
          <strong>Column:</strong> {colDef.description}
          {colDef.unit && <span className="unit"> ({colDef.unit})</span>}
        </div>
      )}

      <div className="values-grid">
        {verifyMode && proposal.current_cell_value != null && (
          <div className="value-block">
            <span className="value-label">Current value</span>
            <span className="value-content current-value">{proposal.current_cell_value}</span>
          </div>
        )}
        <div className="value-block">
          <span className="value-label">Proposed value</span>
          <span className={`value-content proposed-value ${!proposal.proposed_value ? 'muted' : ''}`}>
            {proposal.proposed_value ?? '—'}
          </span>
        </div>
      </div>

      {proposal.rationale && (
        <div className="rationale-block">
          <strong>Rationale:</strong>
          <p>{proposal.rationale}</p>
        </div>
      )}

      {proposal.calculation && (
        <div className="calculation-block">
          <strong>Calculation:</strong>
          <pre className="calculation-text">{proposal.calculation}</pre>
        </div>
      )}

      {proposal.needs_more_evidence && (
        <p className="warning-text">⚠ Model indicated more evidence is needed.</p>
      )}

      {Object.keys(rowCtx).length > 0 && (
        <details className="row-context-details">
          <summary>Row context</summary>
          <dl className="kv-list">
            {Object.entries(rowCtx)
              .filter(([k]) => k !== 'row_id')
              .slice(0, 12)
              .map(([k, v]) => (
                <div key={k} className="kv-row">
                  <dt>{k}</dt>
                  <dd>{String(v ?? '—')}</dd>
                </div>
              ))}
          </dl>
        </details>
      )}
    </div>
  )
}
