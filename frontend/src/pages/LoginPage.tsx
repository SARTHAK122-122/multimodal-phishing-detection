import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Loader2, LogIn, ShieldCheck } from 'lucide-react'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Notice } from '../components/ui'

/** Where to land after signing in (never another auth page). */
export function safeNext(raw: string | null): string {
  return raw && raw.startsWith('/') && !raw.startsWith('/login') && !raw.startsWith('/register')
    ? raw
    : '/dashboard'
}

/**
 * Sign-in page (route /login).
 *
 * The session is created server-side: this form only calls
 * POST /api/auth/login and the HttpOnly session cookie does the rest.
 * Wrong credentials surface the backend's generic message verbatim -
 * no client-side pretending, no fake success states. A "Remember me"
 * checkbox is deliberately absent because the backend has one fixed
 * session lifetime (8h); the honest session note is shown instead.
 */
export default function LoginPage() {
  const { login } = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (busy) return // belt-and-braces against double submit (Enter while pending)
    setBusy(true)
    setError(null)
    try {
      // The shell consumes the landing path once the session flips, so the
      // redirect cannot race the swap from the auth route tree to the app tree.
      await login({ username: username.trim(), password }, next)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const registerHref = next !== '/dashboard'
    ? `/register?next=${encodeURIComponent(next)}`
    : '/register'

  return (
    <div className="auth-page">
      <div className="auth-stack">
        <main className="auth-card">
          <div className="auth-brand">
            <span className="logo" aria-hidden="true"><ShieldCheck size={22} /></span>
            <span>
              <span className="title">PhishGuard AI</span>
              <span className="subtitle">Intelligent Threat Protection</span>
            </span>
          </div>

          <h1>Welcome back</h1>
          <p className="auth-sub">Sign in to continue protecting yourself online.</p>

          <div className="auth-alert" role="alert" aria-live="polite">
            {error && <Notice kind="error">{error}</Notice>}
          </div>

          <form className="auth-form" onSubmit={submit}>
            <div className="field">
              <label className="lbl" htmlFor="login-username">Username</label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Enter your username"
                autoComplete="username"
                required
                autoFocus
              />
            </div>

            <div className="field">
              <label className="lbl" htmlFor="login-password">Password</label>
              <div className="pw-wrap">
                <input
                  id="login-password"
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="pw-toggle"
                  onClick={() => setShowPw(v => !v)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                  aria-pressed={showPw}
                  title={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <p className="auth-meta">Your session expires after 8 hours of inactivity.</p>

            <button className="btn auth-btn" type="submit" disabled={busy} aria-busy={busy}>
              {busy
                ? <><Loader2 size={16} className="spin" /> Signing in…</>
                : <><LogIn size={16} /> Sign in</>}
            </button>
          </form>

          <p className="auth-alt">
            Don&apos;t have an account? <Link to={registerHref}>Create account</Link>
          </p>
        </main>

        <footer className="auth-foot">AI-powered threat analysis</footer>
      </div>
    </div>
  )
}
