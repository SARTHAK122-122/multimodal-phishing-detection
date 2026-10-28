import { useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import {
  Globe, History as HistoryIcon, LayoutDashboard, LogOut, Mail, Menu,
  MessageSquare, QrCode, Shield, ShieldCheck, UserRound, X,
} from 'lucide-react'
import { AuthProvider, useAuth } from './auth/AuthContext'
import DashboardPage from './pages/DashboardPage'
import WebsiteScannerPage from './pages/scanners/WebsiteScannerPage'
import EmailScannerPage from './pages/scanners/EmailScannerPage'
import SmsScannerPage from './pages/scanners/SmsScannerPage'
import QrScannerPage from './pages/scanners/QrScannerPage'
import ScanReportPage from './pages/ScanReportPage'
import HistoryPage from './pages/HistoryPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ProfilePage from './pages/ProfilePage'
import DatasetPreprocessingPage from './pages/DatasetPreprocessingPage'
import ModelsPage from './pages/ModelsPage'
import EvaluationsPage from './pages/EvaluationsPage'
import HealthPage from './pages/HealthPage'
import PublicDemoPage from './pages/PublicDemoPage'

/**
 * Application shell.
 *
 * Authentication is real (Spring Security session): while signed out only
 * /login and /register render; every app route sits behind the session check.
 * Research pages (datasets/models/evaluations) additionally require the ADMIN
 * role - enforced by the backend and mirrored here for a clear explanation
 * instead of a dead page. The system-status page stays available to any
 * signed-in account (its endpoint is intentionally public for ops checks).
 */
const nav = [
  { section: 'Main' },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { section: 'Threat Detection' },
  { to: '/scan/website', label: 'Website Scanner', icon: Globe },
  { to: '/scan/email', label: 'Email Scanner', icon: Mail },
  { to: '/scan/sms', label: 'SMS Scanner', icon: MessageSquare },
  { to: '/scan/qr', label: 'QR Code Scanner', icon: QrCode },
  { section: 'My Activity' },
  { to: '/history', label: 'Scan History', icon: HistoryIcon },
  { section: 'Account' },
  { to: '/profile', label: 'Profile', icon: UserRound },
]

/** Honest in-app explanation when a non-admin opens a research route. */
function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  if (user?.role === 'ADMIN') return <>{children}</>
  return (
    <div className="panel admin-gate">
      <h2>Administrator access required</h2>
      <p>
        The research workspace (dataset management, model training, evaluation
        history) is limited to administrator accounts. You are signed in as{' '}
        <b className="mono">@{user?.username}</b> with the member role, so this
        area is closed to you - by the same rule the server enforces on every
        request to it.
      </p>
      <p className="small muted">
        To open it, sign in with the administrator account (the first account
        created on this database), or create a fresh one on a new database.
      </p>
      <div className="row" style={{ marginTop: 14 }}>
        <Link to="/dashboard" className="btn">Back to dashboard</Link>
        <Link to="/profile" className="btn secondary">Open profile</Link>
      </div>
    </div>
  )
}

function BootSplash() {
  return (
    <div className="auth-page">
      <div className="boot-note">
        <span className="logo"><ShieldCheck size={20} /></span>
        Checking your session…
      </div>
    </div>
  )
}

function SignedOutRoutes() {
  const location = useLocation()
  const next = encodeURIComponent(location.pathname + location.search)
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="*" element={<Navigate to={`/login?next=${next}`} replace />} />
    </Routes>
  )
}

function Shell() {
  const { user, booting, logout, pendingLanding, clearPendingLanding } = useAuth()
  const [drawer, setDrawer] = useState(false)
  const location = useLocation()

  // The landing path is consumed by the single <Navigate> rendered below
  // (see the main content); here we only clear it once we have arrived, so a
  // later re-render never re-navigates to a stale target. Compared with
  // pathname+search because safeNext() can carry a query string.
  useEffect(() => {
    if (!booting && user && pendingLanding
        && location.pathname + location.search === pendingLanding) {
      clearPendingLanding()
    }
  }, [booting, user, pendingLanding, clearPendingLanding,
      location.pathname, location.search])

  if (booting) return <BootSplash />
  if (!user) return <SignedOutRoutes />

  const initial = (user.displayName || user.username).trim().charAt(0).toUpperCase()

  return (
    <div className="app-shell">
      {/* Mobile top bar */}
      <div className="topbar">
        <button
          className="menu-btn"
          aria-label={drawer ? 'Close menu' : 'Open menu'}
          onClick={() => setDrawer(v => !v)}
        >
          {drawer ? <X size={18} /> : <Menu size={18} />}
        </button>
        <div>
          <div className="tb-title">PhishGuard AI</div>
          <div className="tb-sub">Intelligent Threat Protection</div>
        </div>
      </div>
      {drawer && (
        <button
          className="sidebar-backdrop"
          aria-label="Close menu"
          onClick={() => setDrawer(false)}
        />
      )}

      <aside className={`sidebar${drawer ? ' open' : ''}`}>
        <div className="brand">
          <span className="logo">
            <ShieldCheck size={19} />
          </span>
          <span>
            <span className="title">PhishGuard AI</span>
            <span className="subtitle">Intelligent Threat Protection</span>
          </span>
        </div>

        {nav.map((item, i) =>
          'section' in item ? (
            <div key={`s-${i}`} className="nav-section">{item.section}</div>
          ) : (
            <NavLink
              key={item.to}
              to={item.to!}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              onClick={() => setDrawer(false)}
            >
              <item.icon size={16} />
              {item.label}
            </NavLink>
          ),
        )}

        {/* Signed-in account: identity + one-click sign out */}
        <div className="user-chip">
          <span className="avatar">{initial}</span>
          <Link to="/profile" className="uc-text" onClick={() => setDrawer(false)}>
            <span className="uc-name">{user.displayName || user.username}</span>
            <span className="uc-role">
              {user.role === 'ADMIN' ? 'administrator' : 'member'}
            </span>
          </Link>
          <button
            className="icon-btn"
            title="Sign out"
            aria-label="Sign out"
            onClick={() => { setDrawer(false); void logout() }}
          >
            <LogOut size={15} />
          </button>
        </div>

        <div style={{ padding: '10px 10px 4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-dim)', fontSize: 12 }}>
            <Shield size={14} />
            <span>Scans are analyzed by AI,</span>
          </div>
          <div style={{ color: 'var(--text-dim)', fontSize: 12, paddingLeft: 22 }}>
            not a guarantee of safety.
          </div>
        </div>
      </aside>

      <main className="main">
        {pendingLanding ? (
          /* While a post-login landing is pending, render ONLY this redirect.
             The signed-in route table's own <Navigate> redirects (/login and
             the catch-all go to /dashboard) are deliberately not mounted here:
             their effects can re-fire and race this navigation (observed as
             /history being bounced back to /dashboard). One target, no race. */
          <Navigate to={pendingLanding} replace />
        ) : (
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/scan/website" element={<WebsiteScannerPage />} />
          <Route path="/scan/email" element={<EmailScannerPage />} />
          <Route path="/scan/sms" element={<SmsScannerPage />} />
          <Route path="/scan/qr" element={<QrScannerPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/scans/:id" element={<ScanReportPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          {/* Legacy route from the previous tabbed analyzer. */}
          <Route path="/analyze" element={<Navigate to="/dashboard" replace />} />
          {/* Signed-in users landing on the auth pages go to the dashboard. */}
          <Route path="/login" element={<Navigate to="/dashboard" replace />} />
          <Route path="/register" element={<Navigate to="/dashboard" replace />} />
          {/* Research workspace: admin only (mirrors the server-side rule). */}
          <Route path="/datasets" element={<RequireAdmin><DatasetPreprocessingPage /></RequireAdmin>} />
          <Route path="/models" element={<RequireAdmin><ModelsPage /></RequireAdmin>} />
          <Route path="/evaluations" element={<RequireAdmin><EvaluationsPage /></RequireAdmin>} />
          {/* System status: any signed-in account; dev diagnostics stay collapsed. */}
          <Route path="/health" element={<HealthPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        )}
      </main>
    </div>
  )
}

export default function App() {
  if (import.meta.env.MODE === 'github-pages' && !import.meta.env.VITE_API_BASE_URL) {
    return <PublicDemoPage />
  }

  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}
