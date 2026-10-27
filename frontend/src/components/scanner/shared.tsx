import type { ReactNode } from 'react'
import {
  AlertOctagon, AlertTriangle, CheckCircle2, ChevronDown, Info,
} from 'lucide-react'
import { Badge, pct } from '../ui'
import type { EvidenceItem, ModalityResult, ScanEvidence, ScanModality } from '../../api/types'

/**
 * Shared results language for every scanner page and the full report.
 *
 * The four scanner pages render LIVE engine output (ScanResult from
 * POST /api/scans/*); the stored report page renders database rows
 * (Scan with ModalityResult/EvidenceItem). Both are normalized into the
 * plain views below so the same components render either source - the
 * evidence shown is always what the engine actually returned.
 */

/* ------------------------------- shared views ------------------------------- */

export interface EvidenceView {
  key: string | number
  modality: string
  severity: string
  description: string
  supportingValue?: string | null
  direction?: 'risk' | 'safety' | 'neutral'
  kind?: 'FINDING' | 'INFERENCE'
}

export interface ModalityView {
  key: string | number
  modality: string
  status: string
  prediction: string | null
  riskScore: number | null
  modelLine: string
  note?: string | null
  detail: Record<string, unknown>
}

export const fromLiveEvidence = (e: ScanEvidence, i: number): EvidenceView => ({
  key: i, modality: e.modality, severity: e.severity, description: e.description,
  supportingValue: e.supportingValue, direction: e.direction, kind: e.kind,
})

export const fromStoredEvidence = (e: EvidenceItem): EvidenceView => ({
  key: e.id, modality: e.modality, severity: e.severity, description: e.description,
  supportingValue: e.supportingValue, direction: e.direction, kind: e.kind,
})

export const fromLiveModality = (m: ScanModality, i: number): ModalityView => ({
  key: i, modality: m.modality, status: m.status, prediction: m.prediction,
  riskScore: m.riskScore,
  modelLine: `${m.modelName}${m.modelVersion ? ` (${m.modelVersion})` : ''}${
    m.modelType ? ` · ${m.modelType}` : ''}${m.processingTimeMs ? ` · ${m.processingTimeMs} ms` : ''}`,
  note: m.note, detail: m.detail ?? {},
})

export const fromStoredModality = (m: ModalityResult, detail: Record<string, unknown>): ModalityView => ({
  key: m.id, modality: m.modality, status: m.status, prediction: m.prediction,
  riskScore: m.riskScore,
  modelLine: `${m.modelName}${m.modelVersion ? ` (${m.modelVersion})` : ''}${
    m.processingTimeMs ? ` · ${m.processingTimeMs} ms` : ''}`,
  detail,
})

/* ----------------------------- plain-language map ---------------------------- */

const MODALITY_LABELS: Record<string, string> = {
  URL: 'Link address analysis',
  HTML: 'Webpage structure',
  NLP: 'Page text analysis',
  VISION: 'Visual analysis',
  FORM_LINK: 'Forms and links',
  EMAIL_NLP: 'Message text',
  EMAIL_METADATA: 'Sender checks',
  SMS_NLP: 'Message text',
  SMS_METADATA: 'Sender checks',
  QR_URL: 'QR destination',
  QR_NLP: 'QR content text',
  QR_METADATA: 'QR image details',
}

export const modalityLabel = (m: string): string => MODALITY_LABELS[m] ?? m

export function severityRank(s: string): number {
  return ({ CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 } as Record<string, number>)[s] ?? 0
}

/* -------------------------------- verdict hero ------------------------------- */

export function verdictClassOf(verdict: string): 'legit' | 'susp' | 'phish' | 'unknown' {
  const v = verdict.toUpperCase()
  return v === 'LEGITIMATE' ? 'legit' : v === 'SUSPICIOUS' ? 'susp'
    : v === 'PHISHING' ? 'phish' : 'unknown'
}

export function riskColorOf(risk: string): string {
  const r = (risk ?? '').toUpperCase()
  return r === 'LOW' ? 'var(--ok)' : r === 'MEDIUM' ? 'var(--warn)'
    : (r === 'HIGH' || r === 'CRITICAL') ? 'var(--danger)' : 'var(--text-dim)'
}

/** The prominent result card. `score` is the engine's 0..1 risk score. */
export function VerdictHero({
  verdict, riskLevel, score, meta, explanation,
}: {
  verdict: string | null | undefined
  riskLevel: string | null | undefined
  score: number | null | undefined
  meta?: ReactNode
  explanation?: string | null
}) {
  const v = (verdict ?? 'UNKNOWN').toUpperCase()
  const risk = (riskLevel ?? 'UNKNOWN').toUpperCase()
  const cls = verdictClassOf(v)
  const VerdictIcon = v === 'LEGITIMATE' ? CheckCircle2
    : v === 'SUSPICIOUS' ? AlertTriangle
    : v === 'PHISHING' ? AlertOctagon : Info
  const color = riskColorOf(risk)
  const riskPct = score === null || score === undefined ? 0 : Math.round(score * 100)

  return (
    <div className={`verdict-card ${cls}`}>
      <div className="v-icon"><VerdictIcon size={28} /></div>
      <div style={{ minWidth: 0 }}>
        <div className="v-verdict">
          {v === 'LEGITIMATE' ? 'Likely Legitimate'
            : v === 'SUSPICIOUS' ? 'Suspicious'
            : v === 'PHISHING' ? 'Phishing Detected' : 'No Verdict'}
        </div>
        <div className="v-meta">Risk level: <b>{risk}</b>{meta ? <> · {meta}</> : null}</div>
        <div className="risk-meter" title={`Risk score ${riskPct}%`}>
          <div className="level" style={{ width: `${riskPct}%`, background: color }} />
        </div>
        {explanation && <div className="v-meta">{explanation}</div>}
      </div>
      {score !== null && score !== undefined && (
        <div className="v-score">
          <div className="num" style={{ color }}>{pct(score)}</div>
          <div className="lbl">risk score</div>
        </div>
      )}
    </div>
  )
}

/* ---------------------------------- evidence --------------------------------- */

function EvidenceRow({ e }: { e: EvidenceView }) {
  return (
    <div className={`evidence-item ${e.severity}${e.direction === 'safety' ? ' safety' : ''}`}>
      <div className="head">
        <Badge value={e.severity} />
        {e.kind === 'INFERENCE' && <Badge value="model prediction" kind="status" />}
        {e.kind === 'FINDING' && <Badge value="observed" kind="status" />}
        {e.direction && (
          <span className="small muted">
            {e.direction === 'risk' ? '↑ raises risk' : e.direction === 'safety' ? '↓ lowers risk' : 'context'}
          </span>
        )}
        <span className="small muted mono">{modalityLabel(e.modality)}</span>
      </div>
      <div className="desc">{e.description}</div>
      {e.supportingValue && <div className="val">{e.supportingValue}</div>}
    </div>
  )
}

/** "Why this result?" - risk-raising signs first, then risk-lowering ones. */
export function EvidenceSection({ items, emptyText }: { items: EvidenceView[]; emptyText?: string }) {
  if (items.length === 0) {
    return <div className="empty">{emptyText ?? 'No evidence items were recorded for this scan.'}</div>
  }
  const raised = items.filter(e => e.direction !== 'safety')
    .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
  const lowered = items.filter(e => e.direction === 'safety')
  return (
    <>
      {raised.length > 0 && (
        <>
          <div className="small muted" style={{ marginBottom: 8, fontWeight: 600 }}>
            Signs that raised the risk:
          </div>
          {raised.map(e => <EvidenceRow key={e.key} e={e} />)}
        </>
      )}
      {lowered.length > 0 && (
        <>
          <div className="small muted" style={{ margin: '14px 0 8px', fontWeight: 600 }}>
            Signs that lowered the risk:
          </div>
          {lowered.map(e => <EvidenceRow key={e.key} e={e} />)}
        </>
      )}
      {raised.length === 0 && lowered.length === 0 && (
        <div className="empty">{emptyText ?? 'No evidence items were recorded for this scan.'}</div>
      )}
    </>
  )
}

/* --------------------------------- modalities -------------------------------- */

interface Contributor {
  feature: string
  value: number
  contribution?: number
  importance?: number
  direction?: 'risk' | 'safety' | 'neutral'
}

/** One analysis module as an expandable section (plain title, tech inside). */
export function ModalityCard({ m }: { m: ModalityView }) {
  const contributors = (m.detail?.contributors ?? []) as Contributor[]

  return (
    <details className="tech">
      <summary>
        <ChevronDown size={14} />
        <b>{modalityLabel(m.modality)}</b>
        <Badge value={m.status} kind="status" />
        {m.prediction && <Badge value={m.prediction} />}
        {m.riskScore !== null && <span className="small muted mono">score {m.riskScore.toFixed(3)}</span>}
      </summary>
      <div className="tech-body">
        {m.note && <div className="small" style={{ marginBottom: 8 }}>{m.note}</div>}
        <div className="small muted">{m.modelLine}</div>

        {contributors.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div className="small muted" style={{ marginBottom: 4 }}>
              {typeof contributors[0]?.contribution === 'number'
                ? 'Top contributors to the link score (▲ toward phishing, ▼ toward legitimate):'
                : 'Most influential link features (rank of influence only, no direction available):'}
            </div>
            <div className="row" style={{ gap: 6 }}>
              {contributors.slice(0, 8).map(c => {
                const signed = typeof c.contribution === 'number'
                const arrow = signed ? (c.contribution! > 0 ? ' ▲' : c.contribution! < 0 ? ' ▼' : '') : ''
                const tip = signed
                  ? `value=${c.value} contribution=${c.contribution} (${c.contribution! > 0 ? 'toward phishing' : 'toward legitimate'})`
                  : `value=${c.value} importance=${c.importance} (no direction available)`
                const cls = c.direction === 'risk' ? 'badge danger'
                  : c.direction === 'safety' ? 'badge ok' : 'badge neutral'
                return (
                  <span key={c.feature} className={cls} title={tip}>
                    {c.feature}: {c.value}{arrow}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        <details className="tech" style={{ marginTop: 10 }}>
          <summary><ChevronDown size={13} /> Raw module output</summary>
          <div className="tech-body">
            <pre className="mono small" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>
              {JSON.stringify(m.detail, null, 2)}
            </pre>
          </div>
        </details>
      </div>
    </details>
  )
}

export function ModalitySection({ items }: { items: ModalityView[] }) {
  if (items.length === 0) {
    return <div className="empty">No per-module results were stored for this scan.</div>
  }
  return <>{items.map(m => <ModalityCard key={m.key} m={m} />)}</>
}

/* --------------------------------- next steps -------------------------------- */

export interface Step { text: string; cls: string }

/** Concrete, verdict-aware guidance. Never claims certainty either way. */
export function nextStepsFor(verdict: string | null | undefined, risk: string | null | undefined): Step[] {
  const v = (verdict ?? '').toUpperCase()
  const r = (risk ?? '').toUpperCase()
  const dangerous = v === 'PHISHING' || r === 'HIGH' || r === 'CRITICAL'
  const unsure = v === 'SUSPICIOUS' || r === 'MEDIUM'

  if (dangerous) {
    return [
      { text: 'Do not enter any passwords, card numbers or personal details on this page or message.', cls: 'danger-step' },
      { text: 'Do not follow the links and do not open any attachments.', cls: 'danger-step' },
      { text: 'If you already entered details, change that password immediately from a device and site you trust.', cls: 'danger-step' },
      { text: 'Verify with the real organization through their official app or website - never through this link.', cls: 'warn-step' },
      { text: 'Report the message or site to your email provider, phone carrier, or national cyber-security agency.', cls: 'warn-step' },
    ]
  }
  if (unsure) {
    return [
      { text: 'Treat this with caution - some suspicious signs were found.', cls: 'warn-step' },
      { text: 'Verify the sender through an independent channel (official app, phone number you already had).', cls: 'warn-step' },
      { text: 'Do not enter passwords until you are sure the site is genuine.', cls: 'warn-step' },
      { text: 'Read the evidence above - it explains exactly what looked wrong.', cls: 'ok-step' },
    ]
  }
  if (v === 'LEGITIMATE') {
    return [
      { text: 'No phishing signs were found in the evidence that could be collected.', cls: 'ok-step' },
      { text: 'Still avoid entering passwords on pages reached through unsolicited messages - check the link itself next time.', cls: 'ok-step' },
      { text: 'Keep your browser and operating system up to date.', cls: 'ok-step' },
    ]
  }
  return [
    { text: 'No verdict could be produced - the checks may not have run. Try again or use another scanner.', cls: 'warn-step' },
    { text: 'When in doubt, do not enter credentials and contact the sender through an official channel.', cls: 'warn-step' },
  ]
}

export function NextStepsPanel({ verdict, riskLevel }: {
  verdict: string | null | undefined
  riskLevel: string | null | undefined
}) {
  return (
    <div className="panel">
      <h2>Recommended next steps</h2>
      <ul className="next-steps">
        {nextStepsFor(verdict, riskLevel).map((step, i) => (
          <li key={i} className={step.cls}>
            {step.cls === 'danger-step' ? <AlertOctagon size={16} />
              : step.cls === 'warn-step' ? <AlertTriangle size={16} />
              : <CheckCircle2 size={16} />}
            <span>{step.text}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** The standing honesty note shown with every result. */
export function ResultDisclaimer() {
  return (
    <div className="small muted" style={{ marginBottom: 14 }}>
      A low score means no phishing signs were found in the evidence that could be collected - it
      is not a guarantee that the site is safe. Never enter passwords on a page you reached
      through an unsolicited message.
    </div>
  )
}
