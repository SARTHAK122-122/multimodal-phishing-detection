import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listEvaluations } from '../api'
import { errorMessage } from '../api/client'
import type { EvaluationRun } from '../api/types'
import { Empty, Loading, Notice } from '../components/ui'

function num(v: number | null): string {
  return v === null || v === undefined ? '-' : v.toFixed(4)
}

/**
 * Evaluation history: metrics measured on a held-out test set, one row per
 * recorded run. Rows only exist once an evaluation has actually run - empty
 * cells mean "not measured", never a placeholder zero.
 */
export default function EvaluationsPage() {
  const [runs, setRuns] = useState<EvaluationRun[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listEvaluations()
      .then(setRuns)
      .catch(err => setError(errorMessage(err)))
  }, [])

  if (error) return <Notice kind="error">{error}</Notice>
  if (!runs) return <Loading text="Loading evaluation history…" />

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Evaluation History</h1>
          <div className="hint">
            Accuracy measured on held-out test data the models never saw while training. Empty
            columns mean a value was not measured - not zero.
          </div>
        </div>
        <Link to="/models" className="btn secondary">← Model Performance</Link>
      </div>

      {runs.length === 0 ? (
        <>
          <Empty text="No evaluation runs recorded yet." />
          <div className="spacer" />
          <Notice kind="info">
            A run appears here automatically after a model is trained and measured on its test
            split.
          </Notice>
        </>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Model</th><th>Date</th><th>Split</th><th>Seed</th>
                <th className="num">Accuracy</th><th className="num">Precision</th>
                <th className="num">Recall</th><th className="num">F1</th>
                <th className="num">ROC-AUC</th><th className="num">FPR</th><th className="num">FNR</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(r => (
                <tr key={r.id}>
                  <td className="mono">{r.modelName ?? `#${r.modelVersionId}`}</td>
                  <td className="small">{new Date(r.evaluationDate).toLocaleString()}</td>
                  <td>{r.splitStrategy ?? '-'}</td>
                  <td>{r.randomSeed ?? '-'}</td>
                  <td className="num">{num(r.accuracy)}</td>
                  <td className="num">{num(r.precisionScore)}</td>
                  <td className="num">{num(r.recallScore)}</td>
                  <td className="num">{num(r.f1Score)}</td>
                  <td className="num">{num(r.rocAuc)}</td>
                  <td className="num">{num(r.falsePositiveRate)}</td>
                  <td className="num">{num(r.falseNegativeRate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
