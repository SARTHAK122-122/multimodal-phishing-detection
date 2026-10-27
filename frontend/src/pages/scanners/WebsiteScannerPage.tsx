import { useState } from 'react'
import { ChevronDown, Globe, ScanLine } from 'lucide-react'
import { scanWebsite } from '../../api'
import { Notice } from '../../components/ui'
import ScanResultCard from '../../components/scanner/ScanResultCard'
import { useScanner } from '../../components/scanner/useScanner'

/**
 * Website Scanner - dedicated page (route /scan/website).
 * Uses the existing POST /api/scans/website endpoint: URL features, fetched
 * page/DOM/text analysis, form & link checks and fusion all run server-side.
 */
export default function WebsiteScannerPage() {
  const { busy, stage, error, result, run, PROGRESS_STAGES } = useScanner()
  const [url, setUrl] = useState('')
  const [fetchHtml, setFetchHtml] = useState(true)
  const [renderPage, setRenderPage] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [touched, setTouched] = useState(false)

  const invalid = touched && url.trim() !== '' && !/^https?:\/\/.+/i.test(url.trim())

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (!/^https?:\/\/.+/i.test(url.trim())) return
    void run(() => scanWebsite({ url: url.trim(), fetch: fetchHtml, render: renderPage }))
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Website Scanner</h1>
          <div className="hint">Check whether a website or link appears suspicious.</div>
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      {busy ? (
        <div className="panel progress-box">
          <div className="spinner" />
          <div className="stage">{PROGRESS_STAGES[stage]}</div>
          <div className="sub">
            {renderPage
              ? 'Deep scans open the real page and can take up to about a minute.'
              : 'This usually takes a few seconds.'}
          </div>
        </div>
      ) : (
        <div className="panel">
          <form onSubmit={submit}>
            <label className="field">
              <span className="lbl">Website address (URL)</span>
              <input
                type="url"
                value={url}
                onChange={e => { setUrl(e.target.value); setTouched(true) }}
                placeholder="https://example.com/login"
                aria-invalid={invalid}
                required
              />
            </label>
            {invalid && (
              <div className="small" style={{ color: 'var(--danger)', marginTop: -6, marginBottom: 10 }}>
                Enter a full web address starting with http:// or https://
              </div>
            )}

            <button
              type="button"
              className="row-btn"
              onClick={() => setShowAdvanced(v => !v)}
              aria-expanded={showAdvanced}
            >
              <ChevronDown size={14} style={{ transform: showAdvanced ? 'rotate(180deg)' : 'none' }} />
              Advanced settings
            </button>
            {showAdvanced && (
              <div style={{ marginTop: 10 }}>
                <div className="check-row">
                  <input
                    id="w-fetch" type="checkbox" checked={fetchHtml}
                    onChange={e => setFetchHtml(e.target.checked)}
                  />
                  <label htmlFor="w-fetch">
                    <div className="name">Read the page content</div>
                    <div className="desc">
                      Downloads the page text and structure to inspect its content and forms.
                      Private network addresses are blocked for safety.
                    </div>
                  </label>
                </div>
                <div className="check-row">
                  <input
                    id="w-render" type="checkbox" checked={renderPage}
                    onChange={e => setRenderPage(e.target.checked)}
                  />
                  <label htmlFor="w-render">
                    <div className="name">Deep scan with screenshot (slower, ~30–60 s)</div>
                    <div className="desc">
                      Opens the page in an invisible browser to analyze what it really looks like,
                      and stores a screenshot as evidence.
                    </div>
                  </label>
                </div>
              </div>
            )}

            <div className="spacer" />
            <button className="btn" type="submit" disabled={busy}>
              <ScanLine size={16} /> Analyze Website
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
            <h2><Globe size={16} style={{ verticalAlign: -2, marginRight: 6 }} />What gets checked</h2>
            <ul className="tip-list">
              <li><Globe size={16} /><span>The link address itself (structure, age signals, known patterns).</span></li>
              <li><Globe size={16} /><span>The page content and any login forms it contains.</span></li>
              <li><Globe size={16} /><span>Whether the page asks for passwords, OTPs or payment details.</span></li>
            </ul>
          </div>
        </>
      )}
    </>
  )
}
