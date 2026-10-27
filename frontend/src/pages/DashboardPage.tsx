import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  ArrowRight, Globe, Mail, MessageSquare, QrCode,
} from 'lucide-react'
import { getScanHistory, listScans } from '../api'
import { errorMessage } from '../api/client'
import type { Scan } from '../api/types'
import { Badge, Loading, Notice, StatCard } from '../components/ui'

/**
 * Dashboard: the four scanners are the main focus, each card opening its
 * dedicated page. Every number below is computed from the scans actually
 * returned by the API (own + shared scans after sign-in) - an empty history
 * shows an honest empty state with scanner links.
 */
const SCANNERS = [
  {
    to: '/scan/website', icon: Globe, title: 'Website Scanner',
    desc: 'Analyze suspicious URLs and webpage evidence.',
  },
  {
    to: '/scan/email', icon: Mail, title: 'Email Scanner',
    desc: 'Inspect suspicious emails and embedded links.',
  },
  {
    to: '/scan/sms', icon: MessageSquare, title: 'SMS Scanner',
    desc: 'Check suspicious text messages and links.',
  },
  {
    to: '/scan/qr', icon: QrCode, title: 'QR Code Scanner',
    desc: 'Decode QR codes and analyze their destinations.',
  },
]

export default function DashboardPage() {
  const navigate = useNavigate()
  const [recent, setRecent] = useState<Scan[] | null>(null)
  const [total, setTotal] = useState<number | null>(null)
  const [threats, setThreats] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Recent five for the table.
    getScanHistory(5)
      .then(setRecent)
      .catch(err => setError(errorMessage(err)))
    // Exact stored total + threat count over ALL scans (up to 500; the page
    // shows how many were covered when the cap kicks in - never a guess).
    listScans(0, 500)
      .then(page => {
        setTotal(page.totalElements)
        setThreats(page.content.filter(
          s => s.finalPrediction === 'PHISHING' || s.finalPrediction === 'SUSPICIOUS',
        ).length)
      })
      .catch(() => { /* totals optional; the table below still renders */ })
  }, [])

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Welcome to PhishGuard AI</h1>
          <div className="hint">Check suspicious websites and messages before interacting with them.</div>
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      {/* ------------------------- scanner feature cards ------------------------- */}
      <div className="grid cols-2" style={{ marginBottom: 18 }}>
        {SCANNERS.map(s => (
          <div className="panel feature-card" key={s.to} style={{ marginBottom: 0 }}>
            <div className="feature-icon"><s.icon size={22} /></div>
            <h2 style={{ marginBottom: 4 }}>{s.title}</h2>
            <div className="sub" style={{ marginBottom: 14 }}>{s.desc}</div>
            <Link to={s.to} className="btn">
              Open Scanner <ArrowRight size={15} />
            </Link>
          </div>
        ))}
      </div>

      {/* ------------------------------ real stats ------------------------------ */}
      <div className="grid cols-2">
        <StatCard
          label="Total scans"
          value={total !== null ? total : (recent !== null ? recent.length : '…')}
          foot={total !== null ? 'stored analyses in your history' : 'loading…'}
        />
        <StatCard
          label="Threats detected"
          value={threats !== null ? threats : '…'}
          foot={total !== null && total > 500
            ? 'phishing or suspicious among the 500 most recent scans'
            : 'phishing or suspicious across stored scans'}
        />
      </div>

      <div className="spacer" />

      {/* ---------------------------- recent scans ---------------------------- */}
      <div className="panel">
        <h2>Recent scans</h2>
        {recent === null && error === null ? (
          <Loading text="Loading recent scans…" />
        ) : recent === null ? null /* load failed - the error notice is above */
        : recent.length === 0 ? (
          <div className="empty">
            <div style={{ marginBottom: 10 }}>No scans yet - run your first check:</div>
            <div className="row" style={{ justifyContent: 'center' }}>
              {SCANNERS.map(s => (
                <Link key={s.to} to={s.to} className="row-btn">{s.title}</Link>
              ))}
            </div>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Website or input</th><th>Type</th><th>Result</th>
                  <th>Risk level</th><th>Date</th>
                </tr>
              </thead>
              <tbody>
                {recent.map(s => (
                  <tr key={s.id} className="clickable" onClick={() => navigate(`/scans/${s.id}`)}>
                    <td>
                      <span className="truncate mono" title={s.submittedUrl}>{s.submittedUrl}</span>
                    </td>
                    <td><Badge value={s.inputType ?? 'WEBSITE'} kind="status" /></td>
                    <td><Badge value={s.finalPrediction} /></td>
                    <td><Badge value={s.riskLevel} /></td>
                    <td className="small muted">{new Date(s.submittedAt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {recent !== null && recent.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <Link to="/history">View all scans →</Link>
          </div>
        )}
      </div>
    </>
  )
}
