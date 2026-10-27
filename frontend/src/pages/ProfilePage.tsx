import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle2, KeyRound, LogOut, Save, ShieldCheck, UserRound,
} from 'lucide-react'
import { changePassword, updateProfile } from '../api'
import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Badge, Loading, Notice } from '../components/ui'

/**
 * Profile (route /profile): view the signed-in account, edit display name /
 * email, change the password (current password required - server-verified),
 * and sign out. Every action hits a real endpoint; the role badge reflects the
 * server's role, which is also what gates the research workspace.
 */
export default function ProfilePage() {
  const { user, setUser, logout } = useAuth()
  const navigate = useNavigate()

  const [displayName, setDisplayName] = useState(user?.displayName ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [profileBusy, setProfileBusy] = useState(false)
  const [profileMsg, setProfileMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwBusy, setPwBusy] = useState(false)
  const [pwMsg, setPwMsg] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)

  if (!user) return <Loading text="Loading profile…" />

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    setProfileBusy(true)
    setProfileMsg(null)
    try {
      const updated = await updateProfile({ displayName, email })
      setUser(updated)
      setProfileMsg({ kind: 'success', text: 'Profile updated.' })
    } catch (err) {
      setProfileMsg({ kind: 'error', text: errorMessage(err) })
    } finally {
      setProfileBusy(false)
    }
  }

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setPwMsg(null)
    if (newPw !== confirmPw) {
      setPwMsg({ kind: 'error', text: 'The two new passwords do not match.' })
      return
    }
    if (newPw.length < 8) {
      setPwMsg({ kind: 'error', text: 'The new password must be at least 8 characters.' })
      return
    }
    setPwBusy(true)
    try {
      await changePassword({ currentPassword: currentPw, newPassword: newPw })
      setCurrentPw(''); setNewPw(''); setConfirmPw('')
      setPwMsg({ kind: 'success', text: 'Password changed. Use it the next time you sign in.' })
    } catch (err) {
      setPwMsg({ kind: 'error', text: errorMessage(err) })
    } finally {
      setPwBusy(false)
    }
  }

  const signOut = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const initial = (user.displayName || user.username).trim().charAt(0).toUpperCase()
  const memberSince = new Date(user.createdAt).toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  })
  const lastLogin = user.lastLoginAt
    ? new Date(user.lastLoginAt).toLocaleString()
    : 'first sign-in'

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Profile</h1>
          <div className="hint">Your account details and sign-in settings.</div>
        </div>
        <button className="btn secondary" onClick={() => void signOut()}>
          <LogOut size={15} /> Sign out
        </button>
      </div>

      {/* ------------------------------ identity ------------------------------ */}
      <div className="panel">
        <div className="profile-head">
          <div className="avatar big">{initial}</div>
          <div style={{ minWidth: 0 }}>
            <div className="profile-name">
              {user.displayName || user.username}
              <Badge value={user.role === 'ADMIN' ? 'administrator' : 'member'} kind="status" />
            </div>
            <div className="small muted mono">@{user.username}</div>
          </div>
        </div>

        <div className="kv profile-kv">
          <div className="k">Email</div>
          <div className="v">{user.email}</div>
          <div className="k">Role</div>
          <div className="v">
            {user.role === 'ADMIN'
              ? 'Administrator - can open the research workspace (datasets, models, evaluations).'
              : 'Member - scanners, history and this profile.'}
          </div>
          <div className="k">Member since</div>
          <div className="v">{memberSince}</div>
          <div className="k">Last sign-in</div>
          <div className="v">{lastLogin}</div>
        </div>
      </div>

      <div className="spacer" />

      <div className="grid cols-2">
        {/* --------------------------- edit profile -------------------------- */}
        <form className="panel" onSubmit={saveProfile}>
          <h2><UserRound size={16} style={{ verticalAlign: -2, marginRight: 6 }} />Edit profile</h2>
          {profileMsg && <Notice kind={profileMsg.kind}>{profileMsg.text}</Notice>}
          <label className="field">
            <span className="lbl">Display name</span>
            <input
              type="text"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="Shown instead of your username"
              maxLength={100}
            />
          </label>
          <label className="field">
            <span className="lbl">Email</span>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </label>
          <div className="spacer" />
          <button className="btn" type="submit" disabled={profileBusy}>
            <Save size={15} /> {profileBusy ? 'Saving…' : 'Save changes'}
          </button>
        </form>

        {/* -------------------------- change password ------------------------ */}
        <form className="panel" onSubmit={savePassword}>
          <h2><KeyRound size={16} style={{ verticalAlign: -2, marginRight: 6 }} />Change password</h2>
          {pwMsg && <Notice kind={pwMsg.kind}>{pwMsg.text}</Notice>}
          <label className="field">
            <span className="lbl">Current password</span>
            <input
              type="password"
              value={currentPw}
              onChange={e => setCurrentPw(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label className="field">
            <span className="lbl">New password</span>
            <input
              type="password"
              value={newPw}
              onChange={e => setNewPw(e.target.value)}
              placeholder="At least 8 characters"
              autoComplete="new-password"
              required
            />
          </label>
          <label className="field">
            <span className="lbl">Confirm new password</span>
            <input
              type="password"
              value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)}
              autoComplete="new-password"
              required
            />
          </label>
          <div className="spacer" />
          <button className="btn" type="submit" disabled={pwBusy}>
            <KeyRound size={15} /> {pwBusy ? 'Updating…' : 'Update password'}
          </button>
        </form>
      </div>

      <div className="spacer" />

      <div className="panel">
        <h2><ShieldCheck size={16} style={{ verticalAlign: -2, marginRight: 6 }} />Good to know</h2>
        <ul className="tip-list">
          <li><CheckCircle2 size={16} /><span>
            Your password is stored only as a salted hash - nobody, including
            this system, can read it back.
          </span></li>
          <li><KeyRound size={16} /><span>
            Password reset by email and two-factor authentication are not
            implemented in this build - if you lose your password, ask an
            administrator to create a fresh account.
          </span></li>
          <li><LogOut size={16} /><span>
            Signing out ends this session on the server; do it on shared
            computers.
          </span></li>
        </ul>
      </div>
    </>
  )
}
