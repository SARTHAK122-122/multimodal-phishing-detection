import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react'
import type { ReactNode } from 'react'
import {
  getMe, login as apiLogin, logout as apiLogout, register as apiRegister,
} from '../api'
import type { AuthUser, LoginInput, RegisterInput } from '../api/types'

/**
 * Session state for the whole app.
 *
 * The "who am I" check is the real backend session (`GET /api/auth/me`):
 * a signed-out visitor gets 401 → `user = null` → App renders the login
 * routes. Nothing about authentication is faked in the client - the server
 * is the authority, and the axios instance carries the HttpOnly session
 * cookie automatically (same-origin /api).
 */
interface AuthContextValue {
  /** null = signed out. undefined is never used; booting covers "checking". */
  user: AuthUser | null
  /** True while the first /auth/me check is in flight. */
  booting: boolean
  /**
   * Sign in. `landing` is an in-app path (e.g. "/history") the shell should
   * land on after the session flips; omit for the default (/dashboard).
   */
  login: (input: LoginInput, landing?: string | null) => Promise<AuthUser>
  register: (input: RegisterInput, landing?: string | null) => Promise<AuthUser>
  logout: () => Promise<void>
  /** Replace the cached user after a profile update. */
  setUser: (user: AuthUser) => void
  /**
   * Path the signed-in shell should navigate to once the session flips
   * (e.g. "/history"). Consumed and cleared by the shell's effect. Null when
   * there is no pending landing (the shell falls back to the current path).
   */
  pendingLanding: string | null
  /** Called by the shell after it has consumed the landing path. */
  clearPendingLanding: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [booting, setBooting] = useState(true)
  const [pendingLanding, setPendingLanding] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getMe()
      .then(me => { if (!cancelled) setUser(me) })
      .catch(() => { /* signed out (401) or backend down - show login either way */ })
      .finally(() => { if (!cancelled) setBooting(false) })
    return () => { cancelled = true }
  }, [])

  // Single, atomic completion of a login/register: the user AND the landing
  // target are set in one state update, so the signed-in shell mounts with the
  // pendingLanding already present. This removes the race where navigating via
  // two separate router/state updates let the shell's catch-all ("/dashboard")
  // win before navigate(next) committed.
  const completeAuth = useCallback((me: AuthUser, landing: string | null) => {
    setPendingLanding(landing)
    setUser(me)
  }, [])

  const login = useCallback(
    async (input: LoginInput, landing?: string | null) => {
      const me = await apiLogin(input)
      completeAuth(me, landing ?? null)
      return me
    },
    [completeAuth],
  )

  const register = useCallback(
    async (input: RegisterInput, landing?: string | null) => {
      const me = await apiRegister(input)
      completeAuth(me, landing ?? null)
      return me
    },
    [completeAuth],
  )

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      // Local state clears even if the server call failed (session is
      // server-side; a failed logout must never leave a stale UI signed in).
      setPendingLanding(null)
      setUser(null)
    }
  }, [])

  // The shell calls this once it has consumed the landing path, so a later
  // re-render (or a hard reload that restores the session via /auth/me) does
  // not re-navigate to a stale target.
  const clearPendingLanding = useCallback(() => {
    setPendingLanding(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user, booting, login, register, logout, setUser,
      pendingLanding, clearPendingLanding,
    }),
    [user, booting, login, register, logout, pendingLanding, clearPendingLanding],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
