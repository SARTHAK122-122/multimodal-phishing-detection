import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Loader2, ShieldCheck, UserPlus } from 'lucide-react'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Notice } from '../components/ui'
import { safeNext } from './LoginPage'

/**
 * Account creation (route /register) - same design system as the sign-in card.
 *
 * The server hashes the password with BCrypt and, on a fresh database, makes
 * this first account the administrator (stated here rather than hidden).
 * Request fields match the backend contract exactly
 * ({ username, email, password, displayName? }); validation errors come from
 * the real server rules (Bean Validation + uniqueness checks).
 */
export default function RegisterPage() {
  const { register } = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))

  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (busy) return // no double submit while a request is pending
    setError(null)
    if (password !== confirm) {
      setError('The two passwords do not match.')
      return
    }
    if (password.length < 8) {
      setError('The password must be at least 8 characters.')
      return
    }
    setBusy(true)
    try {
      // The server creates the account AND signs the user in (session cookie).
      // The shell lands on `next` once the session flips - no race.
      await register(
        {
          username: username.trim(),
          email: email.trim(),
          password,
          ...(displayName.trim() ? { displayName: displayName.trim() } : {}),
        },
        next,
      )
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const loginHref = next !== '/dashboard'
    ? `/login?next=${encodeURIComponent(next)}`
    : '/login'

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

          <h1>Create your account</h1>
          <p className="auth-sub">Scan websites, emails, SMS and QR codes in seconds.</p>

          <div className="auth-alert" role="alert" aria-live="polite">
            {error && <Notice kind="error">{error}</Notice>}
          </div>

          <form className="auth-form" onSubmit={submit}>
            <div className="field">
              <label className="lbl" htmlFor="reg-username">Username</label>
              <input
                id="reg-username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="3–50 characters: letters, digits, _ . -"
                autoComplete="username"
                required
                autoFocus
              />
            </div>

            <div className="field">
              <label className="lbl" htmlFor="reg-display">
                Display name <span className="opt">(optional)</span>
              </label>
              <input
                id="reg-display"
                type="text"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                placeholder="How should we greet you?"
              />
            </div>

            <div className="field">
              <label className="lbl" htmlFor="reg-email">Email</label>
              <input
                id="reg-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>

            <div className="field">
              <label className="lbl" htmlFor="reg-password">Password</label>
              <div className="pw-wrap">
                <input
                  id="reg-password"
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  autoComplete="new-password"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  className="pw-toggle"
                  onClick={() => setShowPw(v => !v)}
                  aria-label={showPw ? 'Hide passwords' : 'Show passwords'}
                  aria-pressed={showPw}
                  title={showPw ? 'Hide passwords' : 'Show passwords'}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="field">
              <label className="lbl" htmlFor="reg-confirm">Confirm password</label>
              <input
                id="reg-confirm"
                type={showPw ? 'text' : 'password'}
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                placeholder="Repeat the password"
                autoComplete="new-password"
                required
              />
            </div>

            <button className="btn auth-btn" type="submit" disabled={busy} aria-busy={busy}>
              {busy
                ? <><Loader2 size={16} className="spin" /> Creating account…</>
                : <><UserPlus size={16} /> Create account</>}
            </button>
          </form>

          <p className="auth-note">
            The first account on a fresh database becomes the administrator.
            Passwords are stored only as salted hashes - they are never shown or shared.
          </p>

          <p className="auth-alt">
            Already have an account? <Link to={loginHref}>Sign in</Link>
          </p>
        </main>

        <footer className="auth-foot">AI-powered threat analysis</footer>
      </div>
    </div>
  )
}
