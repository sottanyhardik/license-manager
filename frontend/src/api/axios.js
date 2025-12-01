import axios from "axios";

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

// Auto-refresh access token on 401 errors
api.interceptors.response.use(
    (res) => res,
    async (error) => {
        const original = error.config;

        // Only attempt refresh once
        if (error.response?.status === 401 && !original._retry) {
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

        return Promise.reject(error);
    }
);

export default api;
