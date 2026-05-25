import type { EvidenceSourceType, EvidenceStatus, ProposalStatus, ReviewDecision } from '../types'

type Tone = 'slate' | 'green' | 'amber' | 'orange' | 'red' | 'violet' | 'teal' | 'sky'
type Size = 'xs' | 'sm'
type Light = 'green' | 'yellow' | 'red'

const toneClass: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
  green: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  amber: 'bg-amber-100 text-amber-800 ring-amber-200',
  orange: 'bg-orange-100 text-orange-800 ring-orange-200',
  red: 'bg-rose-100 text-rose-800 ring-rose-200',
  violet: 'bg-violet-100 text-violet-800 ring-violet-200',
  teal: 'bg-teal-100 text-teal-800 ring-teal-200',
  sky: 'bg-sky-100 text-sky-800 ring-sky-200',
}

function words(value: string) {
  return value.replace(/_/g, ' ')
}

function indicatorBoxClass(size: Size) {
  return size === 'xs' ? 'h-4 w-4' : 'h-5 w-5'
}

function markerSizeClass(size: Size) {
  return size === 'xs' ? 'h-2 w-2' : 'h-2.5 w-2.5'
}

export function ReviewTag({
  category,
  value,
  tone = 'slate',
  size = 'sm',
}: {
  category: string
  value: string
  tone?: Tone
  size?: Size
}) {
  return (
    <span
      className={`inline-flex max-w-full items-center rounded-md px-2 py-1 font-semibold ring-1 ring-inset ${toneClass[tone]} ${
        size === 'xs' ? 'text-[9px]' : 'text-[11px]'
      }`}
      title={`${category}: ${value}`}
    >
      <span className="mr-1 text-current opacity-65">{category}:</span>
      <span className="truncate">{value}</span>
    </span>
  )
}

export function ReviewStatusTag({ decision, size = 'sm' }: { decision: ReviewDecision | null | undefined; size?: Size }) {
  if (!decision) return <ReviewTag category="Review" value="pending" tone="sky" size={size} />
  const map: Record<ReviewDecision, { value: string; tone: Tone }> = {
    accepted: { value: 'accepted', tone: 'green' },
    accepted_with_edit: { value: 'edited', tone: 'teal' },
    confirmed_no_data: { value: 'no data', tone: 'violet' },
    rejected: { value: 'rejected', tone: 'slate' },
  }
  const info = map[decision]
  return <ReviewTag category="Review" value={info.value} tone={info.tone} size={size} />
}

export function ReviewStatusIndicator({
  decision,
  size = 'sm',
}: {
  decision: ReviewDecision | null | undefined
  size?: Size
}) {
  const decided = !!decision
  const title = decided ? `Review: ${decision.replace(/_/g, ' ')}` : 'Review: pending'
  return (
    <span
      className={`inline-flex ${indicatorBoxClass(size)} items-center justify-center text-emerald-600`}
      title={title}
      aria-label={title}
    >
      {decided ? (
        <svg className={markerSizeClass(size)} viewBox="0 0 12 12" fill="none" aria-hidden="true">
          <path d="M2.25 6.2 4.8 8.75 9.75 3.25" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <span className={`${markerSizeClass(size)} rounded-full border border-slate-400 bg-transparent`} />
      )}
    </span>
  )
}

function SignalDot({ active, label, size = 'sm' }: { active: Light; label: string; size?: Size }) {
  const activeClass: Record<Light, string> = {
    green: 'bg-emerald-500',
    yellow: 'bg-amber-400',
    red: 'bg-rose-500',
  }
  return (
    <span className={`inline-flex ${indicatorBoxClass(size)} items-center justify-center`} title={label} aria-label={label}>
      <span className={`${markerSizeClass(size)} rounded-full ${activeClass[active]}`} />
    </span>
  )
}

export function ProposalStatusIndicator({ status, size = 'sm' }: { status: ProposalStatus; size?: Size }) {
  const light: Record<ProposalStatus, Light> = {
    value_proposed: 'green',
    no_data: 'yellow',
    unresolved: 'yellow',
    not_applicable: 'red',
    not_attempted: 'red',
    error: 'red',
  }
  return <SignalDot active={light[status] ?? 'yellow'} label={`Proposal: ${words(status)}`} size={size} />
}

export function isGreenProposalStatus(status: ProposalStatus): boolean {
  return status === 'value_proposed'
}

export function ProposalStatusTag({ status, size = 'sm' }: { status: ProposalStatus; size?: Size }) {
  const tone: Record<ProposalStatus, Tone> = {
    value_proposed: 'green',
    no_data: 'violet',
    unresolved: 'orange',
    not_applicable: 'slate',
    not_attempted: 'slate',
    error: 'red',
  }
  return <ReviewTag category="Proposal" value={words(status)} tone={tone[status] ?? 'slate'} size={size} />
}

export function EvidenceStatusIndicator({
  evidenceStatus,
  isFallback,
  size = 'sm',
}: {
  evidenceStatus: EvidenceStatus
  isFallback?: boolean
  size?: Size
}) {
  const light: Record<EvidenceStatus, Light> = {
    direct_strong: 'green',
    inferred_strong: 'green',
    direct_weak: 'yellow',
    inferred_weak: 'yellow',
    no_evidence: 'red',
    not_applicable: 'red',
  }
  const label = isFallback ? 'Evidence: anchor fallback' : `Evidence: ${words(evidenceStatus)}`
  return <SignalDot active={isFallback ? 'yellow' : light[evidenceStatus] ?? 'yellow'} label={label} size={size} />
}

export function isGreenEvidenceStatus(evidenceStatus: EvidenceStatus, isFallback?: boolean): boolean {
  return !isFallback && (evidenceStatus === 'direct_strong' || evidenceStatus === 'inferred_strong')
}

export function EvidenceStatusTag({
  evidenceStatus,
  isFallback,
  size = 'sm',
}: {
  evidenceStatus: EvidenceStatus
  isFallback?: boolean
  size?: Size
}) {
  if (isFallback) return <ReviewTag category="Evidence" value="anchor fallback" tone="orange" size={size} />
  const map: Record<EvidenceStatus, { value: string; tone: Tone }> = {
    direct_strong: { value: 'direct strong', tone: 'green' },
    direct_weak: { value: 'direct weak', tone: 'orange' },
    inferred_strong: { value: 'inferred strong', tone: 'green' },
    inferred_weak: { value: 'inferred weak', tone: 'orange' },
    no_evidence: { value: 'no evidence', tone: 'red' },
    not_applicable: { value: 'not applicable', tone: 'slate' },
  }
  const info = map[evidenceStatus]
  return <ReviewTag category="Evidence" value={info.value} tone={info.tone} size={size} />
}

export function EvidenceSourceTag({ sourceType, size = 'sm' }: { sourceType: EvidenceSourceType | string; size?: Size }) {
  const source = String(sourceType)
  const label = `Evidence: ${words(source)}`
  return (
    <span className={`${size === 'xs' ? 'text-[10px]' : 'text-[11px]'} font-medium text-slate-500`} title={label}>
      {label}
    </span>
  )
}
