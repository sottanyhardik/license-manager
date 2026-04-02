import axios from "axios";
import { toast } from 'react-toastify';

const api = axios.create({
    baseURL: "/api/",  // Use relative URL to work on any domain
    headers: {"Content-Type": "application/json"},
});

// Attach access token on every request
api.interceptors.request.use((config) => {
    const access = localStorage.getItem("access");
    if (access) config.headers.Authorization = `Bearer ${access}`;
    return config;
});

// Auto-refresh access token on 401 errors with enhanced error handling
api.interceptors.response.use(
    (res) => res,
    async (error) => {
        const original = error.config;

        // Network error (offline)
        if (!error.response) {
            toast.error('Network error. Please check your connection.');
            return Promise.reject(error);
        }

        // 401 - Unauthorized (existing logic)
        if (error.response.status === 401 && !original._retry) {
            original._retry = true;

            const refresh = localStorage.getItem("refresh");
            if (!refresh) {
                localStorage.clear();
                window.location.href = "/login";
                return Promise.reject(error);
            }

            try {
                const {data} = await axios.post(
                    "/api/auth/refresh/",  // Use relative URL
                    {refresh}
                );

                // Save new tokens (rotation)
                localStorage.setItem("access", data.access);
                if (data.refresh) {
                    localStorage.setItem("refresh", data.refresh);
                }

                // Update the authorization header for the retry
                original.headers.Authorization = `Bearer ${data.access}`;

                // Retry original request
                return api(original);

            } catch (refreshError) {
                localStorage.clear();
                window.location.href = "/login";
                return Promise.reject(refreshError);
            }
        }

        // 403 - Forbidden
        if (error.response.status === 403) {
            toast.error('Access denied. You do not have permission.');
        }

        // 404 - Not found
        if (error.response.status === 404) {
            toast.error('Resource not found.');
        }

        // 500+ - Server error with retry
        if (error.response.status >= 500 && !original._retryCount) {
            original._retryCount = (original._retryCount || 0) + 1;
            if (original._retryCount <= 2) {
                await new Promise(resolve => setTimeout(resolve, 1000));
                return api(original);
            }
            toast.error('Server error. Please try again later.');
        }

        return Promise.reject(error);
    }
);

export default api;
