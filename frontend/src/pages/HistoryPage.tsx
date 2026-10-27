import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listScans } from '../api'
import { errorMessage } from '../api/client'
import type { Scan } from '../api/types'
import { Badge, Empty, Loading, Notice } from '../components/ui'

const PAGE_SIZE = 15
/** The API pages by recency; filters run over this many most-recent scans. */
const FILTER_WINDOW = 200

const TYPES = ['', 'WEBSITE', 'EMAIL', 'SMS', 'QR']
const VERDICTS = ['', 'PHISHING', 'SUSPICIOUS', 'LEGITIMATE']
const RISKS = ['', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

/**
 * Scan history over the persisted scan table. Search and the three filters
 * run client-side over the most recent FILTER_WINDOW records; pagination is
 * applied to the filtered list so every page shows real rows only.
 */
export default function HistoryPage() {
  const navigate = useNavigate()
  const [all, setAll] = useState<Scan[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [verdict, setVerdict] = useState('')
  const [risk, setRisk] = useState('')
  const [pageIndex, setPageIndex] = useState(0)

  useEffect(() => {
    listScans(0, FILTER_WINDOW)
      .then(page => setAll(page.content))
      .catch(err => setError(errorMessage(err)))
  }, [])

  const filtered = useMemo(() => {
    if (!all) return []
    const q = search.trim().toLowerCase()
    return all.filter(s =>
      (!q || s.submittedUrl.toLowerCase().includes(q)) &&
      (!type || (s.inputType ?? 'WEBSITE') === type) &&
      (!verdict || (s.finalPrediction ?? '') === verdict) &&
      (!risk || (s.riskLevel ?? '') === risk),
    )
  }, [all, search, type, verdict, risk])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const page = Math.min(pageIndex, totalPages - 1)
  const rows = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)
  const anyFilter = search || type || verdict || risk

  const resetFilters = () => {
    setSearch(''); setType(''); setVerdict(''); setRisk(''); setPageIndex(0)
  }

  if (error) return <Notice kind="error">{error}</Notice>
  if (!all) return <Loading text="Loading scan history…" />

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Scan History</h1>
          <div className="hint">
            Every analysis you have run, with its verdict. Click any row to open the full report.
          </div>
        </div>
      </div>

      {/* ------------------------------ filters ------------------------------ */}
      <div className="panel" style={{ paddingBottom: 16 }}>
        <div className="filter-bar" style={{ marginBottom: 0 }}>
          <div className="f-item grow">
            <label htmlFor="f-search">Search by website or input</label>
            <input
              id="f-search" type="text" value={search}
              onChange={e => { setSearch(e.target.value); setPageIndex(0) }}
              placeholder="e.g. paypal, http://…"
            />
          </div>
          <div className="f-item">
            <label htmlFor="f-type">Input type</label>
            <select id="f-type" value={type} onChange={e => { setType(e.target.value); setPageIndex(0) }}>
              {TYPES.map(t => <option key={t} value={t}>{t || 'All types'}</option>)}
            </select>
          </div>
          <div className="f-item">
            <label htmlFor="f-verdict">Result</label>
            <select id="f-verdict" value={verdict} onChange={e => { setVerdict(e.target.value); setPageIndex(0) }}>
              {VERDICTS.map(v => <option key={v} value={v}>{v || 'All results'}</option>)}
            </select>
          </div>
          <div className="f-item">
            <label htmlFor="f-risk">Risk level</label>
            <select id="f-risk" value={risk} onChange={e => { setRisk(e.target.value); setPageIndex(0) }}>
              {RISKS.map(r => <option key={r} value={r}>{r || 'All levels'}</option>)}
            </select>
          </div>
          {anyFilter && (
            <button className="row-btn" onClick={resetFilters}>Clear filters</button>
          )}
        </div>
      </div>

      {/* ------------------------------ table ------------------------------ */}
      {filtered.length === 0 ? (
        <>
          <Empty
            text={anyFilter
              ? 'No scans match the current filters.'
              : 'No scans yet - run your first check:'}
          />
          {!anyFilter && (
            <div className="row" style={{ justifyContent: 'center', marginBottom: 14 }}>
              <Link to="/scan/website" className="row-btn">Website Scanner</Link>
              <Link to="/scan/email" className="row-btn">Email Scanner</Link>
              <Link to="/scan/sms" className="row-btn">SMS Scanner</Link>
              <Link to="/scan/qr" className="row-btn">QR Code Scanner</Link>
            </div>
          )}
          {anyFilter && (
            <div style={{ textAlign: 'center' }}>
              <button className="row-btn" onClick={resetFilters}>Clear filters</button>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Input</th><th>Type</th><th>Verdict</th><th>Risk level</th>
                  <th>Date</th><th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map(s => (
                  <tr key={s.id} className="clickable" onClick={() => navigate(`/scans/${s.id}`)}>
                    <td>
                      <span className="truncate mono" title={s.submittedUrl}>{s.submittedUrl}</span>
                    </td>
                    <td><Badge value={s.inputType ?? 'WEBSITE'} kind="status" /></td>
                    <td><Badge value={s.finalPrediction} /></td>
                    <td><Badge value={s.riskLevel} /></td>
                    <td className="small muted">{new Date(s.submittedAt).toLocaleString()}</td>
                    <td>
                      <button
                        className="row-btn"
                        onClick={e => { e.stopPropagation(); navigate(`/scans/${s.id}`) }}
                      >
                        View report
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pager">
            <span>
              {filtered.length} scan{filtered.length === 1 ? '' : 's'}
              {anyFilter ? ` match (searched the ${Math.min(all.length, FILTER_WINDOW)} most recent)` : ''}
            </span>
            {totalPages > 1 && (
              <span className="row">
                <button className="row-btn" disabled={page === 0} onClick={() => setPageIndex(page - 1)}>
                  ← Previous
                </button>
                <span>Page {page + 1} of {totalPages}</span>
                <button
                  className="row-btn"
                  disabled={page >= totalPages - 1}
                  onClick={() => setPageIndex(page + 1)}
                >
                  Next →
                </button>
              </span>
            )}
          </div>
        </>
      )}
    </>
  )
}
