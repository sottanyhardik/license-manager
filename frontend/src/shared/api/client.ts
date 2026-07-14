import axios from 'axios'
import type { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { toast } from 'sonner'
import { ENDPOINTS } from './endpoints'

// ── Base URL resolution ──────────────────────────────────────────────────────
// docker-compose sets VITE_API_BASE_URL; local dev without Docker may set
// VITE_API_URL instead. Read either, with a fallback to empty string so that
// same-origin Vite proxy setups work without any env var at all.
const API_HOST = (
  import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? ''
).replace(/\/+$/, '')

const apiClient = axios.create({
  baseURL: API_HOST || undefined,
  headers: { 'Content-Type': 'application/json' },
})

// ── Attach JWT on every request ──────────────────────────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const access = localStorage.getItem('access')
  if (access) {
    config.headers.Authorization = `Bearer ${access}`
  }
  return config
})

// ── In-flight GET deduplication ──────────────────────────────────────────────
// Coalesces concurrent identical GETs into a single HTTP request.
// Each caller gets its own shallow-cloned response copy.
// NOT a response cache — cleared as soon as the request settles.
type ExtendedAxiosConfig = AxiosRequestConfig & {
  _noDedupe?: boolean
  _retry?: boolean
  _retryCount?: number
}

const _getInFlight = new Map<string, Promise<AxiosResponse>>()
const _origGet = apiClient.get.bind(apiClient)

function dedupedGet<T = unknown>(url: string, config: ExtendedAxiosConfig = {}): Promise<AxiosResponse<T>> {
  if (config.signal ?? config.cancelToken ?? config._noDedupe) {
    return _origGet<T>(url, config)
  }

  const paramKey = config.params
    ? JSON.stringify(config.params, Object.keys(config.params as object).sort())
    : ''
  const key = `${url}|${paramKey}`

  let pending = _getInFlight.get(key)
  if (!pending) {
    pending = _origGet(url, config).finally(() => {
      queueMicrotask(() => _getInFlight.delete(key))
    })
    _getInFlight.set(key, pending)
  }

  return pending.then(
    (res) => ({ ...res, data: res.data } as AxiosResponse<T>),
    (err: unknown) => Promise.reject(err),
  )
}

// Replace the get method while preserving axios type compatibility
Object.assign(apiClient, { get: dedupedGet })

// ── Refresh queue ─────────────────────────────────────────────────────────────
// Prevents the race condition where multiple concurrent 401s each try to refresh.
// Only one refresh fires; all other pending requests wait for it to complete.
interface QueueEntry {
  resolve: (token: string) => void
  reject: (err: unknown) => void
}

let isRefreshing = false
let failedQueue: QueueEntry[] = []

function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else if (token) resolve(token)
  })
  failedQueue = []
}

function clearSessionAndRedirect(reason?: string): void {
  localStorage.clear()
  const url = reason ? `/login?reason=${reason}` : '/login'
  window.location.href = url
}

// ── Response interceptor ──────────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (res) => res,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(error)

    const original = error.config as ExtendedAxiosConfig & InternalAxiosRequestConfig

    // Intentional aborts — not a real error
    if (error.name === 'CanceledError' || error.name === 'AbortError') {
      return Promise.reject(error)
    }

    // Network error — no response from server
    if (!error.response) {
      toast.error('Network error. Please check your connection.')
      return Promise.reject(error)
    }

    const status = error.response.status

    // ── 401 Unauthorized: attempt token refresh once ──────────────────────────
    if (status === 401 && !original._retry) {
      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return apiClient(original)
        })
      }

      original._retry = true
      isRefreshing = true

      const refresh = localStorage.getItem('refresh')
      if (!refresh) {
        isRefreshing = false
        processQueue(error)
        clearSessionAndRedirect()
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post<{ access: string; refresh?: string }>(
          `${API_HOST}${ENDPOINTS.AUTH.REFRESH}`,
          { refresh },
        )

        localStorage.setItem('access', data.access)
        if (data.refresh) localStorage.setItem('refresh', data.refresh)

        original.headers.Authorization = `Bearer ${data.access}`
        processQueue(null, data.access)
        return apiClient(original)
      } catch (refreshError: unknown) {
        processQueue(refreshError)
        clearSessionAndRedirect('session_expired')
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // ── 403 Forbidden ─────────────────────────────────────────────────────────
    if (status === 403) {
      toast.error('Access denied. You do not have permission.')
      return Promise.reject(error)
    }

    // ── 404 Not found (skip toast on retry to avoid double-toasting) ──────────
    if (status === 404 && !original._retry) {
      toast.error('Resource not found.')
      return Promise.reject(error)
    }

    // ── 5xx Server error: exponential backoff, max 2 retries ──────────────────
    if (status >= 500) {
      original._retryCount = (original._retryCount ?? 0) + 1
      if (original._retryCount <= 2) {
        await new Promise<void>((resolve) =>
          setTimeout(resolve, 1000 * original._retryCount!),
        )
        return apiClient(original)
      }
      toast.error('Server error. Please try again later.')
      return Promise.reject(error)
    }

    return Promise.reject(error)
  },
)

// ── Envelope unwrap interceptor ───────────────────────────────────────────────
// Django views return { success, data, message, pagination? }.
// This interceptor runs AFTER the 401-refresh interceptor above so that auth
// errors are handled first.  On success it replaces response.data with:
//   - { data, pagination } when a pagination key is present (list endpoints)
//   - envelope.data directly for all other responses (detail / mutation endpoints)
// On failure (success === false) it rejects with a structured error so callers
// receive envelope.message instead of a generic network error.
apiClient.interceptors.response.use(
  (response) => {
    const envelope = response.data
    if (
      envelope !== null &&
      typeof envelope === 'object' &&
      'success' in envelope &&
      'data' in envelope
    ) {
      if (!(envelope as { success: boolean }).success) {
        return Promise.reject({
          response,
          message: (envelope as { message?: string }).message ?? 'Request failed',
          errors: (envelope as { errors?: unknown[] }).errors ?? [],
        })
      }
      // Paginated response: keep items array + pagination together so callers
      // can access both through a single typed object.
      if ('pagination' in envelope) {
        response.data = {
          data: (envelope as { data: unknown }).data,
          pagination: (envelope as { pagination: unknown }).pagination,
        }
      } else {
        response.data = (envelope as { data: unknown }).data
      }
    }
    return response
  },
  (error) => Promise.reject(error),
)

export default apiClient
