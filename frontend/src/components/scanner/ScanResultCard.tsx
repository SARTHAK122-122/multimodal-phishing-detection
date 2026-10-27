import { Link } from 'react-router-dom'
import { FileText } from 'lucide-react'
import type { ScanResult } from '../../api/types'
import { Badge, Notice } from '../ui'
import {
  EvidenceSection, fromLiveEvidence, fromLiveModality, ModalitySection, NextStepsPanel,
  ResultDisclaimer, VerdictHero,
} from './shared'

/**
 * Shared result presentation for the four scanner pages. Renders the LIVE
 * engine payload (POST /api/scans/* response persisted by Spring Boot) and
 * shows only sections that exist for that input type: decoded QR payload,
 * extracted links (email/SMS), screenshot reference, caveats, missing-module
 * warnings. A FAILED analysis is shown as a failure - never as "legitimate".
 */
export default function ScanResultCard({ result }: { result: ScanResult }) {
  const failed = result.status === 'FAILED'
  const partial = result.status === 'PARTIAL'
  const evidence = (result.evidence ?? []).map(fromLiveEvidence)
  const modalities = (result.modalities ?? []).map(fromLiveModality)
  const links = result.extractedLinks ?? []

  return (
    <>
      {failed ? (
        <Notice kind="error">
          <b>The scan could not be completed.</b> The analysis engine returned a failed status, so
          no verdict is shown. Nothing here should be treated as "safe" - fix the input or try
          again later.
        </Notice>
      ) : (
        <VerdictHero
          verdict={result.classification}
          riskLevel={result.riskLevel}
          score={result.riskScore}
          explanation={result.explanation}
          meta={<>{result.inputType} scan · {result.processingTimeMs} ms</>}
        />
      )}

      {!failed && <ResultDisclaimer />}

      {partial && (
        <Notice kind="warn">
          <b>Incomplete scan.</b> Some checks could not run ({result.missingModalities.join(', ') || 'see analysis below'}).
          The verdict reflects only what was actually analyzed - missing checks were left out
          rather than assumed safe.
        </Notice>
      )}

      {(result.caveats?.length ?? 0) > 0 && (
        <Notice kind="info">
          <b>Notes about this scan</b>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {result.caveats!.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </Notice>
      )}

      {/* QR-only: decoded payload (never a clickable link - we never navigate). */}
      {result.decodedPayload !== undefined && result.decodedPayload !== '' && (
        <div className="panel">
          <h2>Decoded QR content</h2>
          <div className="kv">
            <div className="k">Content type</div>
            <div className="v"><Badge value={result.payloadType ?? 'UNKNOWN'} kind="status" /></div>
            <div className="k">Decoded value</div>
            <div className="v mono" style={{ wordBreak: 'break-all' }}>{result.decodedPayload}</div>
          </div>
          <div className="small muted" style={{ marginTop: 8 }}>
            The destination was analyzed as text - it was <b>not visited</b>, and this page will
            never open it for you.
          </div>
        </div>
      )}

      {/* Email/SMS: links found in the message, each already scored above. */}
      {links.length > 0 && (
        <div className="panel">
          <h2>Links found in the message ({links.length})</h2>
          <div className="sub" style={{ marginBottom: 8 }}>
            Each link was checked by the URL engine without being opened.
          </div>
          <ul className="small" style={{ paddingLeft: 18, lineHeight: 1.9, margin: 0 }}>
            {links.map((l, i) => (
              <li key={i} className="mono" style={{ wordBreak: 'break-all' }}>{l}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Website: screenshot reference captured during rendering. */}
      {result.screenshot && (
        <Notice kind="info">
          A screenshot of the page was captured and stored with this scan - open the full report
          to view it.
        </Notice>
      )}

      {/* Evidence + modules + next steps for every completed scan. */}
      {!failed && (
        <>
          <div className="panel">
            <h2>Why this result?</h2>
            <EvidenceSection
              items={evidence}
              emptyText="No evidence items were recorded for this scan."
            />
          </div>

          {modalities.length > 0 && (
            <div className="panel">
              <h2>Analysis details</h2>
              <div className="sub" style={{ marginBottom: 12 }}>
                Each check ran independently; the final verdict combines them.
              </div>
              <ModalitySection items={modalities} />
            </div>
          )}

          <NextStepsPanel verdict={result.classification} riskLevel={result.riskLevel} />
        </>
      )}

      {/* Full stored report - only when the backend assigned an id. */}
      {result.id !== undefined && (
        <div className="row" style={{ marginTop: 4 }}>
          <Link to={`/scans/${result.id}`} className="btn secondary">
            <FileText size={15} /> View Full Report
          </Link>
          <span className="small muted">
            This scan is saved to your history with its full evidence trail.
          </span>
        </div>
      )}
    </>
  )
}
