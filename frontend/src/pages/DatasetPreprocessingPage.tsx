import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  downloadRunUrl, listDatasets, listRuns, previewDataset, runPreprocessing, uploadDataset,
} from '../api'
import { errorMessage } from '../api/client'
import type { Dataset, DatasetPreview, PreprocessOptions, PreprocessingRun } from '../api/types'
import { Badge, Empty, Loading, Notice } from '../components/ui'

type Step = 1 | 2 | 3 | 4 | 5 | 6

interface MappingRow { from: string; to: string }

const DEFAULT_OPTIONS: PreprocessOptions = {
  normalizeLabels: true,
  dropInvalidRows: true,
  convertTypes: true,
  detectConflictingDuplicates: true,
  removeDuplicates: true,
  handleMissing: true,
  missingStrategy: 'median_mode',
  missingMaxFraction: 0.5,
  dedupeOnColumn: '',
  dropColumns: [],
  selectColumns: [],
  validateFeatures: true,
  labelMapping: {},
}

const OPERATION_DOCS: { key: keyof PreprocessOptions; name: string; desc: string }[] = [
  { key: 'removeDuplicates', name: 'Remove duplicate rows', desc: 'Exact duplicates across all columns; the first occurrence is kept.' },
  { key: 'detectConflictingDuplicates', name: 'Detect conflicting duplicates', desc: 'Rows with identical features but different labels are removed - contradictory supervision would poison training.' },
  { key: 'handleMissing', name: 'Handle missing values', desc: 'Strategy chosen below. Median/mode is computed on this dataset only (no fitting on a test set).' },
  { key: 'dropInvalidRows', name: 'Remove invalid rows', desc: 'Rows whose target/label cell is missing or empty.' },
  { key: 'normalizeLabels', name: 'Normalize label names', desc: 'Applies ONLY the explicit mapping you provide below - labels are never guessed.' },
  { key: 'convertTypes', name: 'Convert data types', desc: 'Coerces numeric-looking feature columns to numbers; unparseable cells become missing (and are reported).' },
  { key: 'validateFeatures', name: 'Validate feature columns', desc: 'Report-only: constant columns, non-numeric columns, leakage and identifier-like columns. Nothing is dropped automatically.' },
]

export default function DatasetPreprocessingPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [runs, setRuns] = useState<PreprocessingRun[]>([])
  const [selected, setSelected] = useState<Dataset | null>(null)
  const [preview, setPreview] = useState<DatasetPreview | null>(null)
  const [step, setStep] = useState<Step>(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  // STEP 1 form
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [source, setSource] = useState('')
  const [description, setDescription] = useState('')
  const [synthetic, setSynthetic] = useState(true)

  // STEP 3 form
  const [targetColumn, setTargetColumn] = useState('')
  const [options, setOptions] = useState<PreprocessOptions>(DEFAULT_OPTIONS)
  const [mapping, setMapping] = useState<MappingRow[]>([])

  // STEP 5 result
  const [result, setResult] = useState<PreprocessingRun | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [ds, rs] = await Promise.all([listDatasets(), listRuns()])
      setDatasets(ds)
      setRuns(rs)
    } catch (err) {
      setError(errorMessage(err))
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const setOpt = <K extends keyof PreprocessOptions>(key: K, value: PreprocessOptions[K]) =>
    setOptions(prev => ({ ...prev, [key]: value }))

  /* ---------------------------- STEP 1 ---------------------------- */
  const upload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { setError('Choose a CSV file first.'); return }
    setBusy(true); setError(null); setNotice(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('name', name || file.name)
      form.append('source', source || 'manual upload')
      form.append('description', description)
      form.append('synthetic', String(synthetic))
      const res = await uploadDataset(form)
      setNotice(`Uploaded "${res.dataset.originalFilename}" → dataset #${res.dataset.id}. The original file is stored unchanged.`)
      setSelected(res.dataset)
      setPreview(res.preview)
      setTargetColumn(res.preview?.target.column ?? '')
      setStep(res.preview ? 2 : 2)
      await refresh()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  /* ---------------------------- STEP 2 ---------------------------- */
  const loadPreview = async (ds: Dataset, target?: string) => {
    setBusy(true); setError(null)
    try {
      const p = await previewDataset(ds.id, target ?? (targetColumn || undefined))
      setPreview(p)
      setSelected(ds)
      if (target) setTargetColumn(target)
      // prefill label mapping suggestions for unrecognised labels
      const unmapped = p.target.unrecognisedValues.filter(
        v => !mapping.some(m => m.from === v))
      if (unmapped.length) {
        setMapping(prev => [...prev, ...unmapped.map(v => ({ from: v, to: '' }))])
      }
      setStep(s => (s < 2 ? 2 : s))
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  /* ---------------------------- STEP 4 ---------------------------- */
  const execute = async () => {
    if (!selected) return
    if (!targetColumn) { setError('Select the target (label) column before running preprocessing.'); return }
    setBusy(true); setError(null); setNotice(null)
    try {
      const labelMapping: Record<string, string> = {}
      mapping.forEach(m => {
        if (m.from.trim() && m.to.trim()) labelMapping[m.from.trim()] = m.to.trim()
      })
      const body = {
        targetColumn,
        options: {
          ...options,
          labelMapping,
          dedupeOnColumn: options.dedupeOnColumn?.trim() ? options.dedupeOnColumn.trim() : undefined,
        },
      }
      const run = await runPreprocessing(selected.id, body)
      setResult(run)
      setStep(5)
      setNotice(`Preprocessing run #${run.id} ${run.status.toLowerCase()} in ${run.elapsedMs ?? '?'} ms.`)
      await refresh()
      await loadPreview(selected)
    } catch (err) {
      setError(errorMessage(err))
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  const runAgain = (run: PreprocessingRun) => {
    const ds = datasets.find(d => d.id === run.datasetId)
    if (ds) {
      setSelected(ds)
      const params = run.parameters ?? {}
      if (params.targetColumn) setTargetColumn(String(params.targetColumn))
      setOptions({ ...DEFAULT_OPTIONS, ...(params as PreprocessOptions) })
      setResult(run)
      setStep(3)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const distributionBars = (dist: Record<string, number>) => {
    const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1
    return Object.entries(dist).map(([label, count]) => (
      <div className="bar-row" key={label}>
        <span className="name">{label}</span>
        <span className="track">
          <span
            className={`fill ${label.toLowerCase().includes('phish') ? 'phishing' : label.toLowerCase().includes('legit') ? 'legitimate' : ''}`}
            style={{ width: `${(count / total) * 100}%` }}
          />
        </span>
        <span className="count">{count}</span>
      </div>
    ))
  }

  const steps: { n: Step; label: string }[] = [
    { n: 1, label: '1 · Upload' },
    { n: 2, label: '2 · Preview raw data' },
    { n: 3, label: '3 · Choose operations' },
    { n: 4, label: '4 · Execute' },
    { n: 5, label: '5 · Results' },
    { n: 6, label: '6 · Export & audit' },
  ]

  const targetOptions = preview?.columnNames ?? selected?.columnNames ?? []
  const featureColumns = useMemo(
    () => (preview?.columnNames ?? []).filter(c => c !== targetColumn),
    [preview, targetColumn],
  )

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dataset &amp; Training</h1>
          <div className="hint">
            Research workspace for preparing training data: upload a CSV, inspect it, choose the
            cleanup operations, run them, review the before/after statistics and download the
            processed file. Your original file is never modified, and every run keeps a full audit
            record.
          </div>
        </div>
      </div>

      <div className="steps">
        {steps.map(s => (
          <span
            key={s.n}
            className={`step-chip${step === s.n ? ' active' : step > s.n ? ' done' : ''}`}
          >
            {s.label}
          </span>
        ))}
      </div>

      {error && <Notice kind="error">{error}</Notice>}
      {notice && <Notice kind="success">{notice}</Notice>}

      {/* ------------------------------ STEP 1 ------------------------------ */}
      <section className="panel">
        <h2>Step 1 · Upload dataset</h2>
        <div className="sub" style={{ marginBottom: 12 }}>
          CSV only, max 50&nbsp;MB. Metadata (filename, size, columns, row counts) is stored in the
          <span className="mono"> datasets</span> table; the file itself goes to
          <span className="mono"> uploads/</span>.
        </div>
        <form onSubmit={upload}>
          <div className="grid cols-2">
            <label className="field">
              <span className="lbl">CSV file *</span>
              <input type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <label className="field">
              <span className="lbl">Dataset name</span>
              <input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. PhishTank URLs 2026-10" />
            </label>
            <label className="field">
              <span className="lbl">Source</span>
              <input type="text" value={source} onChange={e => setSource(e.target.value)} placeholder="e.g. PhishTank export, Kaggle, local experiment" />
            </label>
            <label className="field">
              <span className="lbl">Description</span>
              <input type="text" value={description} onChange={e => setDescription(e.target.value)} placeholder="Licence, date, notes" />
            </label>
          </div>
          <div className="check-row">
            <input
              id="synthetic" type="checkbox" checked={synthetic}
              onChange={e => setSynthetic(e.target.checked)}
            />
            <label htmlFor="synthetic">
              <span className="name">This is synthetic / demonstration data</span>
              <div className="desc">
                Tick this for generated rows. Un-tick only for real datasets. The flag is stored in
                <span className="mono"> datasets.is_synthetic</span> and shown in the UI so demo data is never mistaken for real observations.
              </div>
            </label>
          </div>
          <div className="row">
            <button className="btn" type="submit" disabled={busy}>
              {busy ? 'Uploading…' : 'Upload dataset'}
            </button>
            <span className="muted small">The original file is preserved - preprocessing writes a separate file.</span>
          </div>
        </form>

        <hr className="hr" />
        <h3>Datasets in PostgreSQL ({datasets.length})</h3>
        {datasets.length === 0 ? (
          <Empty text="No datasets yet. Upload a CSV to begin." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th><th>Name</th><th>File</th><th className="num">Rows</th>
                  <th>Target</th><th>Status</th><th>Origin</th><th></th>
                </tr>
              </thead>
              <tbody>
                {datasets.map(d => (
                  <tr key={d.id}>
                    <td className="num">{d.id}</td>
                    <td>{d.name}</td>
                    <td className="mono">{d.originalFilename}</td>
                    <td className="num">{d.totalRows ?? '-'}</td>
                    <td className="mono">{d.targetColumn ?? '-'}</td>
                    <td><Badge value={d.status} kind="status" /></td>
                    <td>{d.synthetic ? <Badge value="synthetic" kind="status" /> : <Badge value="real" kind="status" />}</td>
                    <td>
                      <button className="row-btn" disabled={busy} onClick={() => void loadPreview(d)}>
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ------------------------------ STEP 2 ------------------------------ */}
      <section className="panel">
        <h2>Step 2 · Preview raw data</h2>
        {!selected ? (
          <Empty text="Upload or inspect a dataset to see its profile." />
        ) : busy && !preview ? (
          <Loading text="Profiling dataset…" />
        ) : preview ? (
          <>
            <div className="row" style={{ marginBottom: 12 }}>
              <label className="field" style={{ marginBottom: 0, minWidth: 260 }}>
                <span className="lbl">Target (label) column</span>
                <select value={targetColumn} onChange={e => setTargetColumn(e.target.value)}>
                  <option value="">— select the label column —</option>
                  {targetOptions.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <button
                className="btn secondary" disabled={busy}
                onClick={() => void loadPreview(selected, targetColumn)}
              >
                Re-run inspection
              </button>
            </div>

            <div className="grid cols-4" style={{ marginBottom: 14 }}>
              <div className="stat-card"><div className="label">Rows</div><div className="value">{preview.rows}</div></div>
              <div className="stat-card"><div className="label">Columns</div><div className="value">{preview.columns.length}</div></div>
              <div className="stat-card"><div className="label">Duplicate rows</div><div className="value">{preview.duplicateRows}</div></div>
              <div className="stat-card"><div className="label">Missing cells</div><div className="value">{preview.missingCells}</div></div>
            </div>

            {preview.warnings.map((w, i) => <Notice key={i} kind="warn">{w}</Notice>)}

            <h3>Column data types &amp; missing values</h3>
            <div className="table-wrap" style={{ marginBottom: 16 }}>
              <table className="data">
                <thead>
                  <tr><th>Column</th><th>Data type</th><th className="num">Missing</th><th className="num">%</th><th className="num">Unique</th><th>Sample values</th></tr>
                </thead>
                <tbody>
                  {preview.columns.map(c => (
                    <tr key={c.name}>
                      <td className="mono">{c.name}{c.name === targetColumn && <Badge value="target" kind="status" />}</td>
                      <td className="mono">{c.dtype}</td>
                      <td className="num">{c.missing}</td>
                      <td className="num">{c.missingPct}</td>
                      <td className="num">{c.unique}</td>
                      <td className="mono small">{c.samples.map(s => String(s)).slice(0, 2).join(' | ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid cols-2">
              <div>
                <h3>Target label distribution</h3>
                {preview.target.present
                  ? distributionBars(preview.target.distribution)
                  : <div className="muted small">No target column selected yet.</div>}
                {preview.target.unrecognisedValues.length > 0 && (
                  <Notice kind="warn">
                    Unrecognised label values: <span className="mono">{preview.target.unrecognisedValues.join(', ')}</span>.
                    Provide an explicit mapping in Step&nbsp;3 - rows will not be relabelled silently.
                  </Notice>
                )}
              </div>
              <div>
                <h3>First rows (raw)</h3>
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>{preview.columnNames.slice(0, 6).map(c => <th key={c}>{c}</th>)}</tr>
                    </thead>
                    <tbody>
                      {preview.head.slice(0, 8).map((row, i) => (
                        <tr key={i}>
                          {preview.columnNames.slice(0, 6).map(c => (
                            <td key={c} className="mono small">{String(row[c] ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {preview.columnNames.length > 6 && (
                  <div className="muted small" style={{ marginTop: 6 }}>
                    Showing the first 6 of {preview.columnNames.length} columns.
                  </div>
                )}
              </div>
            </div>
            <div className="row" style={{ marginTop: 14 }}>
              <button className="btn" onClick={() => setStep(3)}>Continue to Step 3 →</button>
            </div>
          </>
        ) : null}
      </section>

      {/* ------------------------------ STEP 3 ------------------------------ */}
      <section className="panel">
        <h2>Step 3 · Select preprocessing operations</h2>
        <div className="sub" style={{ marginBottom: 12 }}>
          Each operation is opt-in and explained. Nothing is dropped automatically: column removal
          and label changes only happen if you select them here.
        </div>

        <div className="grid cols-2">
          <div>
            {OPERATION_DOCS.map(op => (
              <div className="check-row" key={String(op.key)}>
                <input
                  id={`op-${String(op.key)}`} type="checkbox"
                  checked={Boolean(options[op.key])}
                  onChange={e => setOpt(op.key, e.target.value as never)}
                />
                <label htmlFor={`op-${String(op.key)}`}>
                  <span className="name">{op.name}</span>
                  <div className="desc">{op.desc}</div>
                </label>
              </div>
            ))}
          </div>

          <div>
            <label className="field">
              <span className="lbl">Missing-value strategy</span>
              <select
                value={options.missingStrategy}
                onChange={e => setOpt('missingStrategy', e.target.value as PreprocessOptions['missingStrategy'])}
              >
                <option value="median_mode">median_mode - fill numeric with median, text with mode</option>
                <option value="drop_rows">drop_rows - delete rows containing any missing value</option>
                <option value="drop_columns">drop_columns - drop columns above the missing threshold</option>
              </select>
            </label>

            <label className="field">
              <span className="lbl">Column to canonicalise for de-duplication (optional, e.g. url)</span>
              <select
                value={options.dedupeOnColumn ?? ''}
                onChange={e => setOpt('dedupeOnColumn', e.target.value || undefined)}
              >
                <option value="">— disabled —</option>
                {featureColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>

            <label className="field">
              <span className="lbl">Columns to remove (explicit selection, empty = none)</span>
              <select multiple size={4} value={options.dropColumns ?? []}
                onChange={e => setOpt('dropColumns', Array.from(e.target.selectedOptions).map(o => o.value))}>
                {featureColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>

            <label className="field">
              <span className="lbl">Columns to keep (empty = keep everything)</span>
              <select multiple size={4} value={options.selectColumns ?? []}
                onChange={e => setOpt('selectColumns', Array.from(e.target.selectedOptions).map(o => o.value))}>
                {featureColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          </div>
        </div>

        <hr className="hr" />
        <h3>Explicit label mapping</h3>
        <div className="sub" style={{ marginBottom: 8 }}>
          Only these pairs are applied. Example: <span className="mono">suspicious → phishing</span>.
        </div>
        {mapping.length === 0 && <div className="muted small">No mapping yet.</div>}
        {mapping.map((row, i) => (
          <div className="row" key={i} style={{ marginBottom: 6 }}>
            <input type="text" style={{ maxWidth: 220 }} value={row.from} placeholder="raw value"
              onChange={e => setMapping(m => m.map((r, j) => j === i ? { ...r, from: e.target.value } : r))} />
            <span className="muted">→</span>
            <input type="text" style={{ maxWidth: 220 }} value={row.to} placeholder="canonical value (phishing / legitimate)"
              onChange={e => setMapping(m => m.map((r, j) => j === i ? { ...r, to: e.target.value } : r))} />
            <button className="row-btn" onClick={() => setMapping(m => m.filter((_, j) => j !== i))}>remove</button>
          </div>
        ))}
        <div className="row">
          <button className="row-btn" onClick={() => setMapping(m => [...m, { from: '', to: '' }])}>+ add mapping</button>
          <button className="btn" disabled={busy} onClick={() => void execute()}>
            {busy ? 'Running preprocessing…' : 'Step 4 · Execute preprocessing'}
          </button>
        </div>
      </section>

      {/* ------------------------------ STEP 5 ------------------------------ */}
      <section className="panel">
        <h2>Step 5 · Results</h2>
        {!result ? (
          <Empty text="Run preprocessing in Step 4 to see before/after statistics." />
        ) : (
          <>
            <div className="row" style={{ marginBottom: 10 }}>
              <Badge value={result.status} kind="status" />
              <span className="muted small">
                run #{result.id} · dataset {result.datasetName ?? result.datasetId} ·{' '}
                {result.startedAt ? new Date(result.startedAt).toLocaleString() : ''}
                {result.elapsedMs != null && ` · ${result.elapsedMs} ms`}
              </span>
            </div>

            {result.status === 'FAILED' && (
              <Notice kind="error">Preprocessing failed: {result.errorMessage}</Notice>
            )}

            <div className="grid cols-4">
              <div className="stat-card"><div className="label">Original rows</div><div className="value">{result.inputRows}</div></div>
              <div className="stat-card"><div className="label">Processed rows</div><div className="value">{result.outputRows}</div></div>
              <div className="stat-card"><div className="label">Duplicates removed</div><div className="value">{result.duplicatesRemoved}</div></div>
              <div className="stat-card"><div className="label">Invalid rows removed</div><div className="value">{result.invalidRowsRemoved}</div></div>
            </div>

            <div className="grid cols-2" style={{ marginTop: 16 }}>
              <div>
                <h3>Missing values handled: {result.missingValuesHandled}</h3>
                <div className="table-wrap">
                  <table className="data">
                    <thead><tr><th>Column</th><th className="num">Before</th><th className="num">After</th></tr></thead>
                    <tbody>
                      {Object.keys(result.missingBefore).map(col => (
                        <tr key={col}>
                          <td className="mono">{col}</td>
                          <td className="num">{result.missingBefore[col]}</td>
                          <td className="num">{result.missingAfter[col] ?? 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div>
                <h3>Class distribution before</h3>
                {distributionBars(result.classDistributionBefore)}
                <h3>Class distribution after</h3>
                {distributionBars(result.classDistributionAfter)}
              </div>
            </div>

            <h3>Transformations applied</h3>
            <div className="table-wrap" style={{ marginBottom: 14 }}>
              <table className="data">
                <thead><tr><th>Step</th><th className="num">Rows affected</th><th>Description</th></tr></thead>
                <tbody>
                  {result.transformations.map((t, i) => (
                    <tr key={i}>
                      <td className="mono">{t.step}</td>
                      <td className="num">{t.rowsAffected}</td>
                      <td>{t.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {result.warnings?.map((w, i) => <Notice key={i} kind="warn">{w}</Notice>)}

            {result.featureReport && Object.keys(result.featureReport).length > 0 && (
              <>
                <h3>Feature validation report (report-only)</h3>
                <pre className="mono small" style={{ background: 'var(--bg-soft)', padding: 12, borderRadius: 8, overflowX: 'auto' }}>
                  {JSON.stringify(result.featureReport, null, 2)}
                </pre>
              </>
            )}

            <h3>Exact parameters used (reproducible)</h3>
            <pre className="mono small" style={{ background: 'var(--bg-soft)', padding: 12, borderRadius: 8, overflowX: 'auto' }}>
              {JSON.stringify(result.parameters, null, 2)}
            </pre>

            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn secondary" onClick={() => setStep(6)}>Continue to Step 6 →</button>
            </div>
          </>
        )}
      </section>

      {/* ------------------------------ STEP 6 ------------------------------ */}
      <section className="panel">
        <h2>Step 6 · Export &amp; audit</h2>
        <div className="sub" style={{ marginBottom: 12 }}>
          Download the processed CSV produced by a run, or re-run a previous configuration.
          Every run keeps its dataset id, parameters, counts and warnings - see the table below.
        </div>

        {runs.length === 0 ? (
          <Empty text="No preprocessing runs recorded yet." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Run</th><th>Dataset</th><th>Started</th>
                  <th className="num">In</th><th className="num">Out</th>
                  <th className="num">Dupes</th><th className="num">Invalid</th>
                  <th>Status</th><th>Output</th><th></th>
                </tr>
              </thead>
              <tbody>
                {runs.map(r => (
                  <tr key={r.id}>
                    <td className="num">{r.id}</td>
                    <td>{r.datasetName ?? r.datasetId}</td>
                    <td className="small">{r.startedAt ? new Date(r.startedAt).toLocaleString() : '-'}</td>
                    <td className="num">{r.inputRows}</td>
                    <td className="num">{r.outputRows}</td>
                    <td className="num">{r.duplicatesRemoved}</td>
                    <td className="num">{r.invalidRowsRemoved}</td>
                    <td><Badge value={r.status} kind="status" /></td>
                    <td className="mono small">{r.outputFilename ?? '-'}</td>
                    <td>
                      <div className="row">
                        {r.status === 'COMPLETED' && (
                          <a className="row-btn" href={downloadRunUrl(r.id)} download>Download</a>
                        )}
                        <button className="row-btn" onClick={() => runAgain(r)}>Reuse settings</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
