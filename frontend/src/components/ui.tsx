import type { ReactNode } from 'react'

/** Risk level / prediction badge with consistent colours everywhere. */
export function Badge({ value, kind }: { value: string | null | undefined; kind?: 'auto' | 'status' }) {
  if (!value) return <span className="badge neutral">-</span>
  const v = value.toUpperCase()
  let cls = 'neutral'
  if (kind === 'status') {
    if (['OK', 'COMPLETED', 'UP', 'EVALUATED', 'TRAINED'].includes(v)) cls = 'ok'
    else if (['RUNNING', 'PENDING', 'INSPECTED', 'UPLOADED', 'PROCESSED', 'MODEL_MISSING', 'SKIPPED', 'NOT_TRAINED', 'SEED_DEMO'].includes(v)) cls = 'warn'
    else if (['FAILED', 'DOWN'].includes(v)) cls = 'danger'
    else cls = 'info'
  } else {
    if (['CRITICAL', 'HIGH', 'PHISHING'].includes(v)) cls = 'danger'
    else if (['MEDIUM', 'SUSPICIOUS'].includes(v)) cls = 'warn'
    else if (['LOW', 'LEGITIMATE'].includes(v)) cls = 'ok'
    else cls = 'neutral'
  }
  return <span className={`badge ${cls}`}>{value}</span>
}

export function StatCard({ label, value, foot }: { label: string; value: ReactNode; foot?: ReactNode }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {foot && <div className="foot">{foot}</div>}
    </div>
  )
}

export function Notice({ kind, children }: { kind: 'info' | 'warn' | 'error' | 'success'; children: ReactNode }) {
  return <div className={`notice ${kind}`}>{children}</div>
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return <div className="loading">{text}</div>
}

export function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>
}

export function riskTone(level: string | null | undefined): string {
  switch ((level ?? '').toUpperCase()) {
    case 'CRITICAL':
    case 'HIGH':
      return 'danger'
    case 'MEDIUM':
      return 'warn'
    case 'LOW':
      return 'ok'
    default:
      return 'neutral'
  }
}

/** Formats a 0..1 score as a percentage without pretending it is calibrated. */
export function pct(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'n/a'
  return `${(score * 100).toFixed(1)}%`
}
