import { useCallback, useRef, useState } from 'react'
import type { ScanResult } from '../../api/types'
import { errorMessage } from '../../api/client'

const PROGRESS_STAGES = [
  'Validating input…',
  'Analyzing available evidence…',
  'Preparing security report…',
]

/**
 * State machine shared by the four scanner pages: busy/stage/error plus the
 * live engine result. Stage text describes the real in-flight request (the
 * backend is analyzing while the POST is pending); nothing is claimed
 * finished before the server answers.
 */
export function useScanner() {
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ScanResult | null>(null)
  const timers = useRef<number[]>([])

  const clearTimers = () => {
    timers.current.forEach(t => window.clearTimeout(t))
    timers.current = []
  }

  const run = useCallback(async (fn: () => Promise<ScanResult>) => {
    setBusy(true)
    setError(null)
    setResult(null)
    clearTimers()
    timers.current = [
      window.setTimeout(() => setStage(1), 1200),
      window.setTimeout(() => setStage(2), 8000),
    ]
    try {
      setResult(await fn())
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      clearTimers()
      setBusy(false)
      setStage(0)
    }
  }, [])

  return { busy, stage, error, result, run, setError, PROGRESS_STAGES }
}
