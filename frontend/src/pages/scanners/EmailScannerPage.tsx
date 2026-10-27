import { useState } from 'react'
import { ChevronDown, Mail, ScanLine } from 'lucide-react'
import { scanEmail } from '../../api'
import { Notice } from '../../components/ui'
import ScanResultCard from '../../components/scanner/ScanResultCard'
import { useScanner } from '../../components/scanner/useScanner'

/**
 * Email Scanner - dedicated page (route /scan/email).
 * Uses POST /api/scans/email: wording analysis, every embedded link scored
 * by the URL engine (never opened), sender and SPF/DKIM/DMARC checks.
 */
export default function EmailScannerPage() {
  const { busy, stage, error, result, run, PROGRESS_STAGES } = useScanner()
  const [sender, setSender] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [spf, setSpf] = useState('')
  const [dkim, setDkim] = useState('')
  const [dmarc, setDmarc] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    void run(() => scanEmail({
      subject: subject.trim(), body, sender: sender.trim(), spf, dkim, dmarc,
    }))
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Email Scanner</h1>
          <div className="hint">Check suspicious emails for phishing indicators.</div>
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      {busy ? (
        <div className="panel progress-box">
          <div className="spinner" />
          <div className="stage">{PROGRESS_STAGES[stage]}</div>
          <div className="sub">This usually takes a few seconds.</div>
        </div>
      ) : (
        <div className="panel">
          <form onSubmit={submit}>
            <div className="grid cols-2">
              <label className="field">
                <span className="lbl">Sender (optional)</span>
                <input
                  type="text" value={sender} onChange={e => setSender(e.target.value)}
                  placeholder="name@example.com or display name"
                />
              </label>
              <label className="field">
                <span className="lbl">Subject</span>
                <input
                  type="text" value={subject} onChange={e => setSubject(e.target.value)}
                  placeholder="e.g. Your account will be suspended"
                />
              </label>
            </div>
            <label className="field">
              <span className="lbl">Email body</span>
              <textarea
                rows={7} value={body} onChange={e => setBody(e.target.value)}
                placeholder="Paste the full message text here…"
                required
              />
            </label>

            <button
              type="button"
              className="row-btn"
              onClick={() => setShowAdvanced(v => !v)}
              aria-expanded={showAdvanced}
            >
              <ChevronDown size={14} style={{ transform: showAdvanced ? 'rotate(180deg)' : 'none' }} />
              Advanced: email authentication results
            </button>
            {showAdvanced && (
              <div className="grid cols-3" style={{ marginTop: 10 }}>
                <label className="field">
                  <span className="lbl">SPF result (optional)</span>
                  <select value={spf} onChange={e => setSpf(e.target.value)}>
                    <option value="">not known</option>
                    <option value="pass">pass</option>
                    <option value="fail">fail</option>
                    <option value="softfail">softfail</option>
                    <option value="none">none</option>
                  </select>
                </label>
                <label className="field">
                  <span className="lbl">DKIM result (optional)</span>
                  <select value={dkim} onChange={e => setDkim(e.target.value)}>
                    <option value="">not known</option>
                    <option value="pass">pass</option>
                    <option value="fail">fail</option>
                    <option value="none">none</option>
                  </select>
                </label>
                <label className="field">
                  <span className="lbl">DMARC result (optional)</span>
                  <select value={dmarc} onChange={e => setDmarc(e.target.value)}>
                    <option value="">not known</option>
                    <option value="pass">pass</option>
                    <option value="fail">fail</option>
                    <option value="none">none</option>
                  </select>
                </label>
              </div>
            )}

            <div className="spacer" />
            <button className="btn" type="submit" disabled={busy}>
              <ScanLine size={16} /> Analyze Email
            </button>
          </form>
        </div>
      )}

      {result && !busy && (
        <>
          <div className="spacer" />
          <ScanResultCard result={result} />
        </>
      )}

      {!result && !busy && (
        <>
          <div className="spacer" />
          <div className="panel">
            <h2><Mail size={16} style={{ verticalAlign: -2, marginRight: 6 }} />What gets checked</h2>
            <ul className="tip-list">
              <li><Mail size={16} /><span>Wording that pressures you to act fast or share credentials.</span></li>
              <li><Mail size={16} /><span>Every link in the message - checked without being opened.</span></li>
              <li><Mail size={16} /><span>The sender address and, if you have them, SPF/DKIM/DMARC results.</span></li>
            </ul>
          </div>
        </>
      )}
    </>
  )
}
