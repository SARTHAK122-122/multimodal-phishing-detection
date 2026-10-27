import { useRef, useState } from 'react'
import { ImageUp, QrCode, ScanLine } from 'lucide-react'
import { scanQr } from '../../api'
import { Notice } from '../../components/ui'
import ScanResultCard from '../../components/scanner/ScanResultCard'
import { useScanner } from '../../components/scanner/useScanner'

const QR_MAX_BYTES = 10 * 1024 * 1024
const QR_TYPES = 'png, jpg, jpeg, bmp, gif, webp'

/**
 * QR Code Scanner - dedicated page (route /scan/qr).
 * Uses POST /api/scans/qr (multipart): the image is decoded server-side and
 * the decoded destination is analyzed as a string - it is never visited,
 * and this page never navigates to it.
 */
export default function QrScannerPage() {
  const { busy, stage, error, result, run, setError, PROGRESS_STAGES } = useScanner()
  const [file, setFile] = useState<File | null>(null)
  const [drag, setDrag] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const pickFile = (f: File | null) => {
    setError(null)
    if (!f) { setFile(null); return }
    if (f.size > QR_MAX_BYTES) {
      setError(`That image is ${(f.size / 1024 / 1024).toFixed(1)} MB. The limit is 10 MB.`)
      return
    }
    setFile(f)
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) { setError('Choose a QR image first.'); return }
    void run(() => scanQr(file))
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>QR Code Scanner</h1>
          <div className="hint">Upload a QR code to inspect its destination.</div>
        </div>
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      {busy ? (
        <div className="panel progress-box">
          <div className="spinner" />
          <div className="stage">{PROGRESS_STAGES[stage]}</div>
          <div className="sub">Decoding the image and checking its destination.</div>
        </div>
      ) : (
        <div className="panel">
          <form onSubmit={submit}>
            <div
              className={`dropzone${drag ? ' drag' : ''}`}
              onClick={() => fileInput.current?.click()}
              onDragOver={e => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={e => {
                e.preventDefault()
                setDrag(false)
                pickFile(e.dataTransfer.files?.[0] ?? null)
              }}
              role="button"
              tabIndex={0}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') fileInput.current?.click() }}
            >
              <div className="dz-icon"><ImageUp size={30} /></div>
              <div className="dz-main">
                {file ? file.name : 'Drag and drop a QR image here'}
              </div>
              <div className="dz-sub">
                or click to browse · accepts {QR_TYPES} · maximum 10 MB
              </div>
              <input
                ref={fileInput}
                type="file"
                accept=".png,.jpg,.jpeg,.bmp,.gif,.webp,image/png,image/jpeg,image/bmp,image/gif,image/webp"
                style={{ display: 'none' }}
                onChange={e => pickFile(e.target.files?.[0] ?? null)}
              />
            </div>

            {file && (
              <div style={{ marginTop: 12, textAlign: 'center' }}>
                <img className="qr-preview" src={URL.createObjectURL(file)} alt="Selected QR code preview" />
              </div>
            )}

            <div className="spacer" />
            <div className="row">
              <button className="btn" type="submit" disabled={busy || !file}>
                <ScanLine size={16} /> Analyze QR Code
              </button>
              <span className="small muted">
                The QR destination is decoded and checked as text - it is never visited.
              </span>
            </div>
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
            <h2><QrCode size={16} style={{ verticalAlign: -2, marginRight: 6 }} />What gets checked</h2>
            <ul className="tip-list">
              <li><QrCode size={16} /><span>The hidden destination the QR code points to.</span></li>
              <li><QrCode size={16} /><span>That destination is analyzed like a website link - without opening it.</span></li>
              <li><QrCode size={16} /><span>If the image cannot be read, you get a clear error - never a guessed result.</span></li>
            </ul>
          </div>
        </>
      )}
    </>
  )
}
