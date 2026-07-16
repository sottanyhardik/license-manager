/**
 * Tests for AuthContext / AuthProvider (frontend/src/context/AuthContext.tsx)
 *
 * The codebase has no standalone useAuth hook — consumers call
 * useContext(AuthContext) directly. These tests exercise the Provider's
 * behavior: initial unauthenticated state, loginSuccess(), logout(), and
 * localStorage token persistence.
 *
 * Network calls are fully mocked:
 *  - `api` (src/api/axios) is vi.mock'd so no real HTTP happens.
 *  - `axios` (the raw package) is vi.mock'd to intercept the /auth/refresh/ call.
 */

import React, { useContext } from 'react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthContext, AuthProvider } from '@/context/AuthContext'
import type { LoginResponse, AuthUser } from '@/types'

// ── Module mocks ──────────────────────────────────────────────────────────────
// Mock the internal `api` instance used by AuthProvider for auth/me/ and auth/logout/
vi.mock('@/api/axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

// Also mock raw axios used for /api/auth/refresh/ (proactive token refresh)
vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

import api from '@/api/axios'

// ── Fixtures ──────────────────────────────────────────────────────────────────
const MOCK_USER: AuthUser = {
  id: 1,
  username: 'testuser',
  first_name: 'Test',
  last_name: 'User',
  email: 'test@example.com',
  is_superuser: false,
  is_staff: false,
  is_active: true,
  roles: ['VIEWER'],
  date_joined: '2024-01-01T00:00:00Z',
}

const MOCK_LOGIN_RESPONSE: LoginResponse = {
  access: 'mock-access-token',
  refresh: 'mock-refresh-token',
  user: MOCK_USER,
}

// Wrapper that provides the AuthProvider for renderHook
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
)

describe('AuthProvider / AuthContext', () => {
  beforeEach(() => {
    // Start with a clean localStorage and no pending timers
    localStorage.clear()
    vi.clearAllMocks()

    // Default: /auth/me/ fails (simulates no valid session) so AuthProvider
    // reaches the catch branch and sets loading=false without a user.
    ;(api.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('401 Unauthorized'))
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
  })

  afterEach(() => {
    localStorage.clear()
  })

  // ── Initial unauthenticated state ─────────────────────────────────────────

  it('starts with user=null and loading=true, then resolves to loading=false with no user when no token exists', async () => {
    // No access token in localStorage → loadUser bails early without calling api.get
    const { result } = renderHook(() => useContext(AuthContext), { wrapper })

    // By the time the effect settles, loading should be false and user null
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.user).toBeNull()
  })

  it('isAuthenticated helpers return falsy when user is null', async () => {
    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.isSuperAdmin()).toBe(false)
    expect(result.current.hasRole('ADMIN')).toBe(false)
    expect(result.current.hasAnyRole(['ADMIN', 'VIEWER'])).toBe(false)
    expect(result.current.canManageUsers()).toBe(false)
  })

  // ── loginSuccess() ────────────────────────────────────────────────────────

  it('after loginSuccess() user state becomes the logged-in user', async () => {
    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => {
      result.current.loginSuccess(MOCK_LOGIN_RESPONSE)
    })

    expect(result.current.user).toEqual(MOCK_USER)
    expect(result.current.loading).toBe(false)
  })

  it('loginSuccess() stores access and refresh tokens in localStorage', async () => {
    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => {
      result.current.loginSuccess(MOCK_LOGIN_RESPONSE)
    })

    expect(localStorage.getItem('access')).toBe('mock-access-token')
    expect(localStorage.getItem('refresh')).toBe('mock-refresh-token')
  })

  it('loginSuccess() stores the serialized user object in localStorage', async () => {
    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => {
      result.current.loginSuccess(MOCK_LOGIN_RESPONSE)
    })

    const stored = localStorage.getItem('user')
    expect(stored).not.toBeNull()
    expect(JSON.parse(stored!)).toEqual(MOCK_USER)
  })

  // ── Role helpers after login ──────────────────────────────────────────────

  it('hasRole() returns true for a role the user holds', async () => {
    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => { result.current.loginSuccess(MOCK_LOGIN_RESPONSE) })

    expect(result.current.hasRole('VIEWER')).toBe(true)
    expect(result.current.hasRole('ADMIN')).toBe(false)
  })

  it('isSuperAdmin() reflects the user flag', async () => {
    const superAdminResponse: LoginResponse = {
      ...MOCK_LOGIN_RESPONSE,
      user: { ...MOCK_USER, is_superuser: true },
    }
    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => { result.current.loginSuccess(superAdminResponse) })

    expect(result.current.isSuperAdmin()).toBe(true)
    // Superuser bypasses role checks
    expect(result.current.hasRole('ANYTHING')).toBe(true)
  })

  // ── logout() ─────────────────────────────────────────────────────────────

  it('logout() resets user to null and clears localStorage', async () => {
    // Seed localStorage as if user is logged in
    localStorage.setItem('access', 'mock-access-token')
    localStorage.setItem('refresh', 'mock-refresh-token')
    localStorage.setItem('user', JSON.stringify(MOCK_USER))

    // Suppress the window.location.href assignment that logout() does
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { ...originalLocation, href: '' },
    })

    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    // Put the user into state first
    act(() => { result.current.loginSuccess(MOCK_LOGIN_RESPONSE) })
    expect(result.current.user).toEqual(MOCK_USER)

    // Now logout
    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('access')).toBeNull()
    expect(localStorage.getItem('refresh')).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()

    // Restore
    Object.defineProperty(window, 'location', {
      writable: true,
      value: originalLocation,
    })
  })

  it('logout() calls the api to invalidate the refresh token', async () => {
    localStorage.setItem('refresh', 'mock-refresh-token')

    Object.defineProperty(window, 'location', {
      writable: true,
      value: { href: '' },
    })

    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    act(() => { result.current.loginSuccess(MOCK_LOGIN_RESPONSE) })

    await act(async () => {
      await result.current.logout()
    })

    expect(api.post).toHaveBeenCalledWith(
      'auth/logout/',
      { refresh: 'mock-refresh-token' }
    )
  })

  // ── Hydration from localStorage ───────────────────────────────────────────

  it('hydrates user from localStorage when an access token is present and /auth/me/ succeeds', async () => {
    localStorage.setItem('access', 'valid-token')
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ data: MOCK_USER })

    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.user).toEqual(MOCK_USER)
  })

  it('ignores corrupted serialized user data from localStorage', async () => {
    localStorage.setItem('user', '{bad json')

    const { result } = renderHook(() => useContext(AuthContext), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.user).toBeNull()
    expect(localStorage.getItem('user')).toBeNull()
  })
})
