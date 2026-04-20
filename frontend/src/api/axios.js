import axios from "axios";
import { toast } from 'react-toastify';

const api = axios.create({
    baseURL: "/api/",
    headers: {"Content-Type": "application/json"},
});

// Attach access token on every request
api.interceptors.request.use((config) => {
    const access = localStorage.getItem("access");
    if (access) config.headers.Authorization = `Bearer ${access}`;
    return config;
});

// ─── Refresh queue ────────────────────────────────────────────────────────────
// Prevents the race condition where multiple concurrent 401s each try to refresh,
// causing "token already blacklisted" errors and unexpected logouts.
// Only one refresh fires; all other pending requests wait for it to finish.
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
    failedQueue.forEach(({ resolve, reject }) => {
        if (error) reject(error);
        else resolve(token);
    });
    failedQueue = [];
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
        if (status === 401 && !original._retry) {

            // If a refresh is already in flight, queue this request until it completes
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                }).then((token) => {
                    original.headers.Authorization = `Bearer ${token}`;
                    return api(original);
                }).catch((err) => Promise.reject(err));
            }

            original._retry = true;
            isRefreshing = true;

            const refresh = localStorage.getItem("refresh");
            if (!refresh) {
                isRefreshing = false;
                processQueue(error);
                localStorage.clear();
                window.location.href = "/login";
                return Promise.reject(error);
            }

            try {
                const { data } = await axios.post("/api/auth/refresh/", { refresh });

                localStorage.setItem("access", data.access);
                if (data.refresh) localStorage.setItem("refresh", data.refresh);

                original.headers.Authorization = `Bearer ${data.access}`;
                processQueue(null, data.access);
                return api(original);

            } catch (refreshError) {
                processQueue(refreshError);
                localStorage.clear();
                window.location.href = "/login?reason=session_expired";
                return Promise.reject(refreshError);
            } finally {
                isRefreshing = false;
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
