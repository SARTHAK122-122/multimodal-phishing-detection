import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listModels } from '../api'
import { errorMessage } from '../api/client'
import type { ModelVersion } from '../api/types'
import { Badge, Loading, Notice } from '../components/ui'

/** Parses metrics JSON defensively - a stored blob must never crash the page. */
function parseMetrics(json: string | null): Record<string, unknown> | null {
  if (!json) return null
  try {
    const parsed = JSON.parse(json)
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null
  } catch {
    return null
  }
}

/** Friendly labels for the metric keys stored by the training pipeline. */
const METRIC_LABELS: Record<string, string> = {
  accuracy: 'Accuracy',
  f1: 'F1 score',
  f1Score: 'F1 score',
  precision: 'Precision',
  recall: 'Recall',
  rocAuc: 'ROC-AUC',
  testAccuracy: 'Accuracy (hold-out)',
  testF1: 'F1 (hold-out)',
  testRocAuc: 'ROC-AUC (hold-out)',
}

function prettyMetric(v: unknown): string {
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(4)
  return String(v)
}

/**
 * Model Performance: one card per registered model with its real status and
 * measured metrics. Metrics stay empty until a model is actually trained and
 * evaluated - nothing on this page is estimated.
 */
export default function ModelsPage() {
  const [models, setModels] = useState<ModelVersion[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listModels()
      .then(setModels)
      .catch(err => setError(errorMessage(err)))
  }, [])

  if (error) return <Notice kind="error">{error}</Notice>
  if (!models) return <Loading text="Loading model information…" />

  const untrained = models.filter(m => m.evaluationStatus === 'NOT_TRAINED')

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Model Performance</h1>
          <div className="hint">
            The detection models behind PhishGuard AI, with the accuracy actually measured on
            held-out test data. Models that have not been trained yet show no numbers rather than
            guessed ones.
          </div>
        </div>
        <Link to="/evaluations" className="btn secondary">Evaluation history →</Link>
      </div>

      {untrained.length > 0 && (
        <Notice kind="warn">
          {untrained.length} of {models.length} models are not trained yet. Their performance
          boxes stay empty because no measurement exists for them.
        </Notice>
      )}

      {models.map(m => {
        const metrics = parseMetrics(m.metricsJson)
        return (
          <div className="panel" key={m.id}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <h2 style={{ marginBottom: 2 }}>{m.modelName}</h2>
                <div className="small muted">
                  {m.modelType} · version <span className="mono">{m.version}</span>
                  {m.trainingDate && <> · trained {new Date(m.trainingDate).toLocaleDateString()}</>}
                </div>
              </div>
              <Badge value={m.evaluationStatus} kind="status" />
            </div>

            <div className="spacer" />

            {metrics && Object.keys(metrics).length > 0 ? (
              <div className="grid cols-4">
                {Object.entries(metrics)
                  .filter(([, v]) => typeof v === 'number' || typeof v === 'string')
                  .slice(0, 8)
                  .map(([k, v]) => (
                    <div className="stat-card" key={k}>
                      <div className="label">{METRIC_LABELS[k] ?? k}</div>
                      <div className="value" style={{ fontSize: 20 }}>{prettyMetric(v)}</div>
                    </div>
                  ))}
              </div>
            ) : (
              <div className="empty">No measured metrics - this model has not been evaluated yet.</div>
            )}

            {m.notes && (
              <div className="sub" style={{ marginTop: 12 }}>{m.notes}</div>
            )}
          </div>
        )
      })}
    </>
  )
}
