import axios from "axios";
import { toast } from "sonner";

// Resolve API base URL:
//   - If VITE_API_URL is defined (e.g. "http://localhost:8000"), call Django directly.
//   - Otherwise fall back to "/api/" so requests flow through Vite's dev proxy.
// Django CORS_ALLOWED_ORIGINS must include the frontend origin when calling directly.
const API_HOST = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const API_BASE = API_HOST ? `${API_HOST}/api/` : "/api/";

const api = axios.create({
    baseURL: API_BASE,
    headers: {"Content-Type": "application/json"},
    // Django's default names differ from Axios' defaults. This keeps
    // session-authenticated browser requests valid as a fallback while the
    // application normally authenticates with a bearer token.
    xsrfCookieName: "csrftoken",
    xsrfHeaderName: "X-CSRFToken",
});

const getCookie = (name) => {
    if (typeof document === "undefined") return null;
    const prefix = `${name}=`;
    const cookie = document.cookie.split(";").map(part => part.trim()).find(part => part.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
};

// Attach access token on every request
api.interceptors.request.use((config) => {
    const access = localStorage.getItem("access");
    if (access) config.headers.Authorization = `Bearer ${access}`;

    // Axios only injects an XSRF header automatically in certain same-origin
    // configurations. Set Django's standard header explicitly so a browser
    // session cookie can never cause a legitimate form submission to fail.
    const csrfToken = getCookie("csrftoken");
    if (csrfToken && !config.headers["X-CSRFToken"]) {
        config.headers["X-CSRFToken"] = csrfToken;
    }
    return config;
});

// ─── In-flight GET dedup ─────────────────────────────────────────────────────
// Coalesces concurrent identical GETs into a single HTTP request. Each caller
// gets its own response copy (so an .interceptor/transform on one doesn't
// affect another). Cleared as soon as the request resolves/rejects — this is
// NOT a response cache, only a request dedup.
//
// Common triggers this fixes:
//   • React StrictMode double-mount in dev (effects fire twice → 2 GETs)
//   • Two components mounting near-simultaneously and both fetching the same
//     metadata endpoint.
const _getInFlight = new Map(); // url -> Promise<axiosResponse>

const _origGet = api.get.bind(api);
api.get = (url, config = {}) => {
    // Skip dedup if caller used signal/cancelToken (they want fine control).
    if (config.signal || config.cancelToken || config._noDedupe) {
        return _origGet(url, config);
    }
    // Key includes the URL plus any params so paginated/filtered requests
    // don't share a single promise.
    const paramKey = config.params
        ? JSON.stringify(config.params, Object.keys(config.params).sort())
        : "";
    const key = `${url}|${paramKey}`;

    let pending = _getInFlight.get(key);
    if (!pending) {
        pending = _origGet(url, config).finally(() => {
            // Use a microtask delay so synchronous .then handlers see the
            // same in-flight promise, but a fresh later GET re-fetches.
            queueMicrotask(() => _getInFlight.delete(key));
        });
        _getInFlight.set(key, pending);
    }
    // Each caller gets a separate Promise resolving to a shallow-cloned
    // response, so downstream mutations on `data` don't leak across callers.
    return pending.then(
        (res) => ({ ...res, data: res.data }),
        (err) => Promise.reject(err),
    );
};

// ─── Refresh queue ────────────────────────────────────────────────────────────
// Prevents the race condition where multiple concurrent 401s each try to refresh,
// causing "token already blacklisted" errors and unexpected logouts.
// Only one refresh fires; all other pending requests wait for it to finish.
let refreshPromise = null;
let logoutRedirected = false;

export const AUTH_SESSION_EVENT_KEY = "auth:session-event";

export const clearStoredAuth = () => {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    localStorage.removeItem("user");
};

export const publishAuthEvent = (type) => {
    // Storage events synchronise other tabs. The CustomEvent helps code in the
    // current tab react without waiting for a navigation/reload.
    const payload = JSON.stringify({ type, at: Date.now() });
    localStorage.setItem(AUTH_SESSION_EVENT_KEY, payload);
    window.dispatchEvent(new CustomEvent("auth:session", { detail: { type } }));
};

const redirectToLoginOnce = (reason = "session_expired") => {
    if (logoutRedirected) return;
    logoutRedirected = true;
    clearStoredAuth();
    publishAuthEvent("logout");
    const redirect = encodeURIComponent(window.location.pathname);
    window.location.assign(`/login?reason=${reason}&redirect=${redirect}`);
};

/**
 * The single source of truth for refreshing an access token. Both the response
 * interceptor and the session lifecycle manager call this function, so a near
 * expiry timer and a burst of 401 responses cannot rotate a SimpleJWT refresh
 * token more than once.
 */
export const refreshAccessToken = () => {
    if (refreshPromise) return refreshPromise;

    const refresh = localStorage.getItem("refresh");
    if (!refresh) {
        const error = new Error("Missing refresh token");
        redirectToLoginOnce();
        return Promise.reject(error);
    }

    refreshPromise = axios.post(`${API_BASE}auth/refresh/`, { refresh })
        .then(({ data }) => {
            localStorage.setItem("access", data.access);
            // SimpleJWT refresh rotation is optional at the API boundary. Keep
            // the rotated value when supplied and retain the old one otherwise.
            if (data.refresh) localStorage.setItem("refresh", data.refresh);
            logoutRedirected = false;
            publishAuthEvent("refresh");
            return data.access;
        })
        .catch((error) => {
            redirectToLoginOnce();
            throw error;
        })
        .finally(() => {
            refreshPromise = null;
        });
    return refreshPromise;
};
// ─────────────────────────────────────────────────────────────────────────────

api.interceptors.response.use(
    (res) => res,
    async (error) => {
        const original = error.config;

        // Intentional aborts (AbortController / axios cancel) — not a real network error
        if (error.name === 'CanceledError' || error.name === 'AbortError') {
            return Promise.reject(error);
        }

        // Network error (no response — offline or server unreachable)
        if (!error.response) {
            toast.error('Network error. Please check your connection.');
            return Promise.reject(error);
        }

        const status = error.response.status;

        // 401 - Unauthorized: attempt token refresh once
        if (status === 401 && !original?._retry && !String(original?.url || "").includes("auth/refresh/")) {
            original._retry = true;
            try {
                const token = await refreshAccessToken();
                original.headers = original.headers || {};
                original.headers.Authorization = `Bearer ${token}`;
                return api(original);
            } catch (refreshError) {
                return Promise.reject(refreshError);
            }
        }

        // 403 - Forbidden
        if (status === 403) {
            toast.error('Access denied. You do not have permission.');
            return Promise.reject(error);
        }

        // 404 - Not found (skip toast on retry requests to avoid double-toasting)
        if (status === 404 && !original._retry) {
            toast.error('Resource not found.');
            return Promise.reject(error);
        }

        // 500+ - Server error with up to 2 retries (exponential backoff)
        if (status >= 500) {
            original._retryCount = (original._retryCount || 0) + 1;
            if (original._retryCount <= 2) {
                await new Promise(resolve => setTimeout(resolve, 1000 * original._retryCount));
                return api(original);
            }
            toast.error('Server error. Please try again later.');
            return Promise.reject(error);
        }

        return Promise.reject(error);
    }
);

export default api;
