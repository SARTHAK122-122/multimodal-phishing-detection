import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  AlertOctagon, AlertTriangle, ArrowLeft, CheckCircle2, ChevronDown, Eye, Info,
} from 'lucide-react'
import { getScan } from '../api'
import { api, errorMessage } from '../api/client'
import type { ModalityResult, Scan } from '../api/types'
import { Badge, Loading, Notice, pct } from '../components/ui'

/** Parses the stored detail_json blob; returns {} when absent or malformed. */
function parseDetail(detailJson: string | null | undefined): Record<string, unknown> {
  if (!detailJson) return {}
  try { return JSON.parse(detailJson) as Record<string, unknown> } catch { return {} }
}

/** Plain-language names for the analysis modules. */
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

function modalityLabel(m: string): string {
  return MODALITY_LABELS[m] ?? m
}

/**
 * Scan report: verdict first, then why, then the per-module details, then
 * what to do next. Everything shown is stored data from the detection
 * engine - the page adds no interpretation of its own.
 */
export default function ScanReportPage() {
  const { id } = useParams()
  const [scan, setScan] = useState<Scan | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getScan(Number(id))
      .then(setScan)
      .catch(err => setError(errorMessage(err)))
  }, [id])

  if (error) return <Notice kind="error">{error}</Notice>
  if (!scan) return <Loading text="Loading scan report…" />

  const modalities = scan.modalityResults ?? []
  const evidence = scan.evidence ?? []
  const weights = Object.entries(scan.weightsUsed ?? {})
  const screenshotSrc = scan.screenshotUrl ? `${api.defaults.baseURL}${scan.screenshotUrl}` : null

  const verdict = (scan.finalPrediction ?? 'UNKNOWN').toUpperCase()
  const risk = (scan.riskLevel ?? 'UNKNOWN').toUpperCase()
  const verdictClass = verdict === 'LEGITIMATE' ? 'legit'
    : verdict === 'SUSPICIOUS' ? 'susp'
    : verdict === 'PHISHING' ? 'phish' : 'unknown'
  const VerdictIcon = verdict === 'LEGITIMATE' ? CheckCircle2
    : verdict === 'SUSPICIOUS' ? AlertTriangle
    : verdict === 'PHISHING' ? AlertOctagon : Info
  const riskColor = risk === 'LOW' ? 'var(--ok)'
    : risk === 'MEDIUM' ? 'var(--warn)'
    : (risk === 'HIGH' || risk === 'CRITICAL') ? 'var(--danger)' : 'var(--text-dim)'
  const riskPct = scan.riskScore === null ? 0 : Math.round(scan.riskScore * 100)

  const riskRaised = evidence.filter(e => e.direction !== 'safety')
  const riskLowered = evidence.filter(e => e.direction === 'safety')

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Security Report</h1>
          <div className="hint mono" style={{ wordBreak: 'break-all' }}>{scan.submittedUrl}</div>
        </div>
        <Link to="/history" className="btn secondary"><ArrowLeft size={15} /> Back to history</Link>
      </div>

      {scan.seedData && (
        <Notice kind="info">
          This is seeded demonstration data kept to exercise the interface - it was not produced by
          a live scan.
        </Notice>
      )}

      {/* ------------------------------ verdict card ------------------------------ */}
      <div className={`verdict-card ${verdictClass}`}>
        <div className="v-icon"><VerdictIcon size={28} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="v-verdict">
            {verdict === 'LEGITIMATE' ? 'Likely Legitimate'
              : verdict === 'SUSPICIOUS' ? 'Suspicious'
              : verdict === 'PHISHING' ? 'Phishing Detected' : 'No Verdict'}
          </div>
          <div className="v-meta">
            Risk level: <b>{risk}</b> · {scan.inputType ?? 'WEBSITE'} scan · {new Date(scan.submittedAt).toLocaleString()}
          </div>
          <div className="risk-meter" title={`Risk score ${riskPct}%`}>
            <div className="level" style={{ width: `${riskPct}%`, background: riskColor }} />
          </div>
          <div className="v-meta">
            {scan.explanation ?? 'The engine did not store a summary for this scan.'}
          </div>
        </div>
        <div className="v-score">
          <div className="num" style={{ color: riskColor }}>{pct(scan.riskScore)}</div>
          <div className="lbl">risk score</div>
        </div>
      </div>

      <div className="small muted" style={{ marginBottom: 14 }}>
        A low score means no phishing signs were found in the evidence that could be collected - it
        is not a guarantee that the site is safe. Never enter passwords on a page you reached
        through an unsolicited message.
      </div>

      {scan.status === 'PARTIAL' && (
        <Notice kind="warn">
          <b>Incomplete scan.</b> Some checks could not run ({scan.missingModalities.join(', ') || 'see analysis below'}).
          The verdict reflects only what was actually analyzed - missing checks were left out rather
          than assumed safe.
        </Notice>
      )}

      {(scan.caveats?.length ?? 0) > 0 && (
        <Notice kind="info">
          <b>Notes about this scan</b>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {scan.caveats!.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </Notice>
      )}

      {/* ------------------------------ why this result ------------------------------ */}
      <div className="panel">
        <h2>Why this result?</h2>
        {evidence.length === 0 ? (
          <div className="empty">No evidence items were recorded for this scan.</div>
        ) : (
          <>
            {riskRaised.length > 0 && (
              <>
                <div className="small muted" style={{ marginBottom: 8, fontWeight: 600 }}>
                  Signs that raised the risk:
                </div>
                {riskRaised
                  .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
                  .map(e => <EvidenceRow key={e.id} e={e} />)}
              </>
            )}
            {riskLowered.length > 0 && (
              <>
                <div className="small muted" style={{ margin: '14px 0 8px', fontWeight: 600 }}>
                  Signs that lowered the risk:
                </div>
                {riskLowered.map(e => <EvidenceRow key={e.id} e={e} />)}
              </>
            )}
          </>
        )}
      </div>

      {/* ------------------------------ recommended next steps ------------------------------ */}
      <div className="panel">
        <h2>Recommended next steps</h2>
        <ul className="next-steps">
          {nextSteps(verdict, risk).map((step, i) => (
            <li key={i} className={step.cls}>
              {step.cls === 'danger-step' ? <AlertOctagon size={16} />
                : step.cls === 'warn-step' ? <AlertTriangle size={16} />
                : <CheckCircle2 size={16} />}
              <span>{step.text}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* ------------------------------ analysis modules ------------------------------ */}
      <div className="panel">
        <h2>Analysis details</h2>
        <div className="sub" style={{ marginBottom: 12 }}>
          Each check ran independently; the final verdict combines them.
        </div>
        {modalities.length === 0 ? (
          <div className="empty">No per-module results were stored for this scan.</div>
        ) : (
          modalities.map(m => <ModalityCard key={m.id} m={m} detail={parseDetail(m.detailJson)} />)
        )}
      </div>

      {/* ------------------------------ screenshot ------------------------------ */}
      {screenshotSrc && (
        <div className="panel">
          <h2><Eye size={16} style={{ verticalAlign: -2, marginRight: 6 }} />Screenshot of the page</h2>
          <div className="small muted" style={{ marginBottom: 10 }}>
            Captured while the page was opened for analysis, as evidence of what it looked like.
            It is shown for human review - no verdict was derived from the image alone.
          </div>
          <img
            src={screenshotSrc}
            alt={`Screenshot captured for scan ${scan.id}`}
            style={{ maxWidth: '100%', border: '1px solid var(--border)', borderRadius: 8 }}
          />
        </div>
      )}

      {/* ------------------------------ technical details ------------------------------ */}
      <details className="tech">
        <summary><ChevronDown size={14} /> Technical details (for reviewers)</summary>
        <div className="tech-body">
          <div className="kv">
            <div className="k">Scan ID</div><div className="v mono">#{scan.id}</div>
            <div className="k">Status</div><div className="v"><Badge value={scan.status} kind="status" /></div>
            <div className="k">Model</div><div className="v mono">{scan.modelVersion ?? '-'}</div>
            <div className="k">Submitted at</div><div className="v mono">{new Date(scan.submittedAt).toLocaleString()}</div>
            <div className="k">Completed at</div>
            <div className="v mono">{scan.completedAt ? new Date(scan.completedAt).toLocaleString() : '-'}</div>
            <div className="k">Normalized input</div><div className="v mono">{scan.normalizedUrl ?? '-'}</div>
            <div className="k">Processing time</div>
            <div className="v mono">{scan.processingTimeMs === null ? '-' : `${scan.processingTimeMs} ms`}</div>
            <div className="k">Raw risk score</div>
            <div className="v mono">{scan.riskScore === null ? 'n/a' : scan.riskScore.toFixed(4)}</div>
            <div className="k">Checks that did not run</div>
            <div className="v">{scan.missingModalities.length ? scan.missingModalities.join(', ') : 'none'}</div>
          </div>

          <h3>Combination weights used</h3>
          {weights.length === 0 ? (
            <div className="muted small">No weights stored for this scan.</div>
          ) : (
            <>
              {weights.map(([name, w]) => (
                <div className="bar-row" key={name}>
                  <span className="name">{name}</span>
                  <span className="track">
                    <span className="fill" style={{ width: `${Math.min(100, w * 200)}%` }} />
                  </span>
                  <span className="count">{(w * 100).toFixed(0)}%</span>
                </div>
              ))}
              <div className="small muted" style={{ marginTop: 6 }}>
                Weights are renormalised over the modules that actually ran; modules that failed are
                excluded rather than counted as safe.
              </div>
            </>
          )}
        </div>
      </details>
    </>
  )
}

function severityRank(s: string): number {
  return ({ CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 } as Record<string, number>)[s] ?? 0
}

/** One evidence item with its direction made explicit. */
function EvidenceRow({ e }: { e: import('../api/types').EvidenceItem }) {
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

interface Contributor {
  feature: string;
  value: number;
  /** Signed SHAP contribution (present only when SHAP ran). */
  contribution?: number;
  /** Unsigned impurity importance (fallback path, no direction claim). */
  importance?: number;
  direction?: 'risk' | 'safety' | 'neutral';
  note?: string;
}

/** One analysis module: plain-language title, its own verdict, expandable tech. */
function ModalityCard({ m, detail }: { m: ModalityResult; detail: Record<string, unknown> }) {
  const contributors = (detail.contributors ?? []) as Contributor[]
  const modelType = typeof detail.modelType === 'string' ? detail.modelType : null
  const note = typeof detail.note === 'string' ? detail.note : null

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
        {note && <div className="small" style={{ marginBottom: 8 }}>{note}</div>}
        <div className="small muted">
          {m.modelName}{m.modelVersion ? ` (${m.modelVersion})` : ''}{modelType ? ` · ${modelType}` : ''}
          {m.processingTimeMs ? ` · ${m.processingTimeMs} ms` : ''}
        </div>

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
              {JSON.stringify(detail, null, 2)}
            </pre>
          </div>
        </details>
      </div>
    </details>
  )
}

/** Concrete, verdict-aware guidance. Never claims certainty either way. */
function nextSteps(verdict: string, risk: string): { text: string; cls: string }[] {
  const dangerous = verdict === 'PHISHING' || risk === 'HIGH' || risk === 'CRITICAL'
  const unsure = verdict === 'SUSPICIOUS' || risk === 'MEDIUM'

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
  if (verdict === 'LEGITIMATE') {
    return [
      { text: 'No phishing signs were found in the evidence that could be collected.', cls: 'ok-step' },
      { text: 'Still avoid entering passwords on pages reached through unsolicited messages - check the link itself next time.', cls: 'ok-step' },
      { text: 'Keep your browser and operating system up to date.', cls: 'ok-step' },
    ]
  }
  return [
    { text: 'No verdict could be produced - the checks may not have run. Try again or use another input type.', cls: 'warn-step' },
    { text: 'When in doubt, do not enter credentials and contact the sender through an official channel.', cls: 'warn-step' },
  ]
}
