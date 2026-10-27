import { useState } from 'react'
import { MessageSquare, ScanLine } from 'lucide-react'
import { scanSms } from '../../api'
import { Notice } from '../../components/ui'
import ScanResultCard from '../../components/scanner/ScanResultCard'
import { useScanner } from '../../components/scanner/useScanner'

/**
 * SMS Scanner - dedicated page (route /scan/sms).
 * Uses POST /api/scans/sms: wording analysis, payment/urgency patterns,
 * every link scored by the URL engine (never opened), sender checks.
 */
export default function SmsScannerPage() {
  const { busy, stage, error, result, run, PROGRESS_STAGES } = useScanner()
  const [sender, setSender] = useState('')
  const [message, setMessage] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    void run(() => scanSms({ message, sender: sender.trim() }))
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>SMS Scanner</h1>
          <div className="hint">Check suspicious messages, payment requests, and links.</div>
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
            <label className="field">
              <span className="lbl">Sender (optional)</span>
              <input
                type="text" value={sender} onChange={e => setSender(e.target.value)}
                placeholder="Phone number or name shown in the message"
              />
            </label>
            <label className="field">
              <span className="lbl">Message text</span>
              <textarea
                rows={7} value={message} onChange={e => setMessage(e.target.value)}
                placeholder="Paste the full message here…"
                required
              />
            </label>

            <div className="spacer" />
            <button className="btn" type="submit" disabled={busy}>
              <ScanLine size={16} /> Analyze Message
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
            <h2><MessageSquare size={16} style={{ verticalAlign: -2, marginRight: 6 }} />What gets checked</h2>
            <ul className="tip-list">
              <li><MessageSquare size={16} /><span>Wording that pressures you to pay or act immediately.</span></li>
              <li><MessageSquare size={16} /><span>Links in the message - checked without being opened.</span></li>
              <li><MessageSquare size={16} /><span>The sender number or name, when provided.</span></li>
            </ul>
          </div>
        </>
      )}
    </>
  )
}
