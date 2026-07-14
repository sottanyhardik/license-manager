import axios from 'axios'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import apiClient, { API_HOST } from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type { Role } from './roles'

// ── Types ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_superuser: boolean
  roles: Role[]
}

export interface LoginResponse {
  access: string
  refresh: string
  user: AuthUser
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  loginSuccess: (data: LoginResponse) => void
  logout: (reason?: string) => Promise<void>
  hasRole: (roleCode: string) => boolean
  hasAnyRole: (roleCodes: string[]) => boolean
  isSuperAdmin: () => boolean
  canManageUsers: () => boolean
}

// ── Session constants ─────────────────────────────────────────────────────────
const IDLE_TIMEOUT_MS = 30 * 60 * 1000       // 30 minutes
const IDLE_CHECK_INTERVAL_MS = 60 * 1000      // check every 1 minute
const TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000 // refresh 5 min before expiry

function getTokenExpiryMs(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1])) as { exp: number }
    return payload.exp * 1000
  } catch {
    return null
  }
}

// ── Context ───────────────────────────────────────────────────────────────────

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  loginSuccess: () => {},
  logout: async () => {},
  hasRole: () => false,
  hasAnyRole: () => false,
  isSuperAdmin: () => false,
  canManageUsers: () => false,
})

// ── Provider ──────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const storedUser = localStorage.getItem('user')
  const [user, setUser] = useState<AuthUser | null>(() => {
    if (!storedUser) return null
    try {
      return JSON.parse(storedUser) as AuthUser
    } catch {
      // Malformed JSON in localStorage — discard and force re-login
      localStorage.removeItem('user')
      return null
    }
  })
  const [loading, setLoading] = useState(true)

  const loadUserCalled = useRef(false)
  const lastActivityRef = useRef(Date.now())
  const idleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimers = () => {
    if (idleTimerRef.current) clearInterval(idleTimerRef.current)
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
    idleTimerRef.current = null
    refreshTimerRef.current = null
  }

  const logout = useCallback(async (reason?: string) => {
    clearTimers()
    try {
      await apiClient.post(ENDPOINTS.AUTH.LOGOUT, {
        refresh: localStorage.getItem('refresh'),
      })
    } catch {
      // Ignore logout API errors — clear session locally regardless
    }
    const currentPath = window.location.pathname
    localStorage.clear()
    setUser(null)
    const redirectParam = encodeURIComponent(currentPath)
    if (reason === 'idle') {
      window.location.href = `/login?reason=idle&redirect=${redirectParam}`
    } else if (reason === 'session_expired') {
      window.location.href = `/login?reason=session_expired&redirect=${redirectParam}`
    } else {
      window.location.href = `/login?redirect=${redirectParam}`
    }
  }, [])

  const scheduleProactiveRefresh = useCallback(() => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)

    const access = localStorage.getItem('access')
    if (!access) return

    const expiry = getTokenExpiryMs(access)
    if (!expiry) return

    const delay = Math.max(expiry - Date.now() - TOKEN_REFRESH_BUFFER_MS, 10_000)

    refreshTimerRef.current = setTimeout(async () => {
      const refresh = localStorage.getItem('refresh')
      if (!refresh) return
      try {
        const { data } = await axios.post<{ access: string; refresh?: string }>(
          `${API_HOST}${ENDPOINTS.AUTH.REFRESH}`,
          { refresh },
        )
        localStorage.setItem('access', data.access)
        if (data.refresh) localStorage.setItem('refresh', data.refresh)
        scheduleProactiveRefresh()
      } catch {
        await logout('session_expired')
      }
    }, delay)
  }, [logout])

  const resetActivity = useCallback(() => {
    lastActivityRef.current = Date.now()
  }, [])

  const startIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearInterval(idleTimerRef.current)
    idleTimerRef.current = setInterval(() => {
      if (Date.now() - lastActivityRef.current >= IDLE_TIMEOUT_MS) {
        void logout('idle')
      }
    }, IDLE_CHECK_INTERVAL_MS)
  }, [logout])

  // Wire activity listeners + timers when user is logged in
  useEffect(() => {
    if (!user) return

    const events = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'] as const
    events.forEach((e) => window.addEventListener(e, resetActivity, { passive: true }))
    lastActivityRef.current = Date.now()
    startIdleTimer()
    scheduleProactiveRefresh()

    return () => {
      events.forEach((e) => window.removeEventListener(e, resetActivity))
      clearTimers()
    }
  }, [user, resetActivity, startIdleTimer, scheduleProactiveRefresh])

  // Validate stored token on mount by fetching /me
  useEffect(() => {
    if (loadUserCalled.current) return
    loadUserCalled.current = true

    const token = localStorage.getItem('access')
    if (!token) {
      setLoading(false)
      return
    }

    apiClient
      .get<AuthUser>(ENDPOINTS.AUTH.ME)
      .then(({ data }) => {
        setUser(data)
        localStorage.setItem('user', JSON.stringify(data))
      })
      .catch(() => {
        localStorage.clear()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const loginSuccess = useCallback((data: LoginResponse) => {
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    localStorage.setItem('user', JSON.stringify(data.user))
    setUser(data.user)
    setLoading(false)
  }, [])

  const isSuperAdmin = useCallback(() => user?.is_superuser === true, [user])

  const hasRole = useCallback(
    (roleCode: string) => {
      if (user?.is_superuser) return true
      return Array.isArray(user?.roles) && user.roles.includes(roleCode as Role)
    },
    [user],
  )

  const hasAnyRole = useCallback(
    (roleCodes: string[]) => {
      if (user?.is_superuser) return true
      if (!Array.isArray(user?.roles)) return false
      return roleCodes.some((r) => user.roles.includes(r as Role))
    },
    [user],
  )

  const canManageUsers = useCallback(
    () => isSuperAdmin() || hasRole('USER_MANAGER'),
    [isSuperAdmin, hasRole],
  )

  const contextValue = useMemo(
    () => ({
      user,
      loading,
      loginSuccess,
      logout,
      hasRole,
      hasAnyRole,
      isSuperAdmin,
      canManageUsers,
    }),
    [user, loading, loginSuccess, logout, hasRole, hasAnyRole, isSuperAdmin, canManageUsers],
  )

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
}

// ── Hook ──────────────────────────────────────────────────────────────────────

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  return useContext(AuthContext)
}
