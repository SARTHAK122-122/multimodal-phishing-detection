import { useCallback, useEffect, useState } from 'react'
import { Activity, CheckCircle2, RefreshCw, XCircle } from 'lucide-react'
import { getHealth } from '../api'
import { errorMessage } from '../api/client'
import type { HealthResponse } from '../api/types'
import { Loading, Notice } from '../components/ui'

/**
 * System Status: what an ordinary user needs - is analysis working right now?
 * The detailed service topology and database counts are kept for project
 * evaluation in a clearly marked developer section at the bottom (this
 * project has real sign-in now, so this section is behind the session - but
 * its /api/health data source is deliberately public (ops checks), which the
 * disclosure in the page states honestly.
 */
export default function HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      setHealth(await getHealth())
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  if (error && !health) return <Notice kind="error">{error}</Notice>
  if (!health) return <Loading text="Checking service status…" />

  const counts = health.counts ?? {}
  const analysisUp = health.aiService.status === 'UP'
  const allUp = health.status === 'UP' && health.database.status === 'UP' && analysisUp

  return (
    <>
      <div className="page-header">
        <div>
          <h1>System Status</h1>
          <div className="hint">Is PhishGuard AI available for analysis right now?</div>
        </div>
        <button className="btn secondary" onClick={() => void refresh()} disabled={refreshing}>
          <RefreshCw size={15} /> {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && <Notice kind="warn">{error}</Notice>}

      {/* ------------------------------ user-facing status ------------------------------ */}
      <div className={`status-strip ${analysisUp ? 'up' : 'down'}`}>
        <div className="s-icon">
          {analysisUp ? <CheckCircle2 size={22} /> : <XCircle size={22} />}
        </div>
        <div>
          <div className="s-title">
            {analysisUp ? 'All systems operational' : 'Analysis temporarily unavailable'}
          </div>
          <div className="s-sub">
            {analysisUp
              ? 'Website, email, SMS and QR analysis are all working. You can run a scan now.'
              : 'The detection engine is not responding, so new scans cannot be analyzed right now. Please try again in a few minutes.'}
          </div>
        </div>
      </div>

      <div className="grid cols-3">
        <div className="stat-card">
          <div className="label">Website &amp; URL analysis</div>
          <div className="value" style={{ fontSize: 18, color: analysisUp ? 'var(--ok)' : 'var(--danger)' }}>
            {analysisUp ? 'Available' : 'Unavailable'}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Email &amp; SMS analysis</div>
          <div className="value" style={{ fontSize: 18, color: analysisUp ? 'var(--ok)' : 'var(--danger)' }}>
            {analysisUp ? 'Available' : 'Unavailable'}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">Scan history &amp; reports</div>
          <div className="value" style={{ fontSize: 18, color: health.database.status === 'UP' ? 'var(--ok)' : 'var(--danger)' }}>
            {health.database.status === 'UP' ? 'Available' : 'Unavailable'}
          </div>
        </div>
      </div>

      <div className="spacer" />

      {!allUp && (
        <Notice kind="warn">
          Some part of the service is not responding. Until it recovers, scans started now may fail
          or return incomplete results - incomplete scans are always labeled as such.
        </Notice>
      )}

      {/* ------------------------------ developer diagnostics ------------------------------ */}
      <details className="tech" style={{ marginTop: 18 }}>
        <summary>
          <Activity size={14} /> Developer diagnostics (hidden from main navigation)
        </summary>
        <div className="tech-body">
          <Notice kind="info">
            Sign-in now exists (server-side sessions with user/admin roles), but{' '}
            <b>/api/health stays intentionally public</b> so ops checks and Docker
            healthchecks can reach it without a session - which means the counts
            below are readable by anyone who can reach the API directly. This page
            is kept out of the main navigation, not locked. The research workspace
            endpoints (datasets, models, evaluations) <i>are</i> admin-gated on the
            server.
          </Notice>

          <div className="kv">
            <div className="k">Overall status</div><div className="v mono">{health.status}</div>
            <div className="k">Database (PostgreSQL)</div>
            <div className="v mono">{health.database.status} - {health.database.detail}</div>
            <div className="k">Detection engine (Python)</div>
            <div className="v mono">{health.aiService.status} - {health.aiService.detail}</div>
            <div className="k">Service name</div><div className="v mono">{health.service}</div>
            <div className="k">Checked at</div>
            <div className="v mono">{new Date(health.timestamp).toLocaleString()}</div>
          </div>

          <h3>Stored record counts</h3>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Table</th><th className="num">Rows</th></tr></thead>
              <tbody>
                {Object.entries(counts).map(([table, count]) => (
                  <tr key={table}>
                    <td className="mono">{table}</td>
                    <td className="num">{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </details>
    </>
  )
}
