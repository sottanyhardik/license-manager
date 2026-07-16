import axios from "axios";
import React, {createContext, useCallback, useEffect, useMemo, useRef, useState} from "react";
import api from "../api/axios";
import type { AuthContextValue, AuthUser, LoginResponse } from "../types";

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
});

// ─── Session config ───────────────────────────────────────────────────────────
// How long with no mouse/keyboard/scroll activity before auto-logout (30 minutes)
const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
// How often to check for idle state
const IDLE_CHECK_INTERVAL_MS = 60 * 1000;
// Refresh the access token this many ms before it actually expires
const TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000;
// ─────────────────────────────────────────────────────────────────────────────

function getTokenExpiryMs(token: string): number | null {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.exp * 1000; // JWT exp is in seconds, convert to ms
    } catch {
        return null;
    }
}

function getStoredUser(): AuthUser | null {
    const storedUser = localStorage.getItem("user");
    if (!storedUser) return null;
    try {
        return JSON.parse(storedUser);
    } catch {
        localStorage.removeItem("user");
        return null;
    }
}

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
    const [loading, setLoading] = useState(true);
    const loadUserCalled = useRef(false);
    const lastActivityRef = useRef(Date.now());
    const idleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const clearTimers = () => {
        if (idleTimerRef.current) clearInterval(idleTimerRef.current);
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        idleTimerRef.current = null;
        refreshTimerRef.current = null;
    };

    const logout = useCallback(async (reason?: string) => {
        clearTimers();
        try {
            await api.post("auth/logout/", {
                refresh: localStorage.getItem("refresh")
            });
        } catch {
            // Ignore logout API errors — clear locally regardless
        }
        const currentPath = window.location.pathname;
        localStorage.clear();
        setUser(null);
        const redirectParam = encodeURIComponent(currentPath);
        if (reason === 'idle') {
            window.location.href = `/login?reason=idle&redirect=${redirectParam}`;
        } else if (reason === 'session_expired') {
            window.location.href = `/login?reason=session_expired&redirect=${redirectParam}`;
        } else {
            window.location.href = `/login?redirect=${redirectParam}`;
        }
    }, []);

    // Proactively refresh the access token before it expires so the user
    // never sees a 401 mid-request while actively working.
    const scheduleProactiveRefresh = useCallback(() => {
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);

        const access = localStorage.getItem("access");
        if (!access) return;

        const expiry = getTokenExpiryMs(access);
        if (!expiry) return;

        const delay = Math.max(expiry - Date.now() - TOKEN_REFRESH_BUFFER_MS, 10_000);

        refreshTimerRef.current = setTimeout(async () => {
            const refresh = localStorage.getItem("refresh");
            if (!refresh) return;
            try {
                const {data} = await axios.post("/api/auth/refresh/", {refresh});
                localStorage.setItem("access", data.access);
                if (data.refresh) localStorage.setItem("refresh", data.refresh);
                scheduleProactiveRefresh(); // schedule next refresh for the new token
            } catch {
                logout('session_expired');
            }
        }, delay);
    }, [logout]);

    // Reset the idle clock whenever the user interacts with the page
    const resetActivity = useCallback(() => {
        lastActivityRef.current = Date.now();
    }, []);

    const startIdleTimer = useCallback(() => {
        if (idleTimerRef.current) clearInterval(idleTimerRef.current);
        idleTimerRef.current = setInterval(() => {
            if (Date.now() - lastActivityRef.current >= IDLE_TIMEOUT_MS) {
                logout('idle');
            }
        }, IDLE_CHECK_INTERVAL_MS);
    }, [logout]);

    // Wire up activity listeners and timers when user is logged in
    useEffect(() => {
        if (!user) return;

        const events = ['mousemove', 'keydown', 'click', 'scroll', 'touchstart'];
        events.forEach(e => window.addEventListener(e, resetActivity, {passive: true}));
        lastActivityRef.current = Date.now();
        startIdleTimer();
        scheduleProactiveRefresh();

        return () => {
            events.forEach(e => window.removeEventListener(e, resetActivity));
            clearTimers();
        };
    }, [user, resetActivity, startIdleTimer, scheduleProactiveRefresh]);

    const loadUser = async () => {
        if (loadUserCalled.current) return;
        loadUserCalled.current = true;

        const token = localStorage.getItem("access");
        if (!token) {
            setLoading(false);
            return;
        }

        try {
            const {data} = await api.get("auth/me/");
            setUser(data);
            localStorage.setItem("user", JSON.stringify(data));
        } catch {
            localStorage.clear();
            setUser(null);
        }
        setLoading(false);
    };

    useEffect(() => {
        loadUser();
    }, []);

    const loginSuccess = useCallback((data: LoginResponse) => {
        localStorage.setItem("access", data.access);
        localStorage.setItem("refresh", data.refresh);
        localStorage.setItem("user", JSON.stringify(data.user));
        setUser(data.user);
        setLoading(false);
    }, []);

    // ── Role helpers ──────────────────────────────────────────────────────────
    // These read from the `roles` array that the /me endpoint now returns.
    // Superusers bypass all role checks — check isSuperAdmin() first when gating.
    // useCallback-stabilized (deps: user) so the context value below stays
    // referentially stable across renders where user hasn't changed.

    const isSuperAdmin = useCallback(() => user?.is_superuser === true, [user]);

    const hasRole = useCallback((roleCode: string) => {
        if (user?.is_superuser) return true;
        return Array.isArray(user?.roles) && user.roles.includes(roleCode);
    }, [user]);

    const hasAnyRole = useCallback((roleCodes: string[]) => {
        if (user?.is_superuser) return true;
        if (!Array.isArray(user?.roles)) return false;
        return roleCodes.some(r => user.roles.includes(r));
    }, [user]);

    const canManageUsers = useCallback(
        () => isSuperAdmin() || hasRole('USER_MANAGER'),
        [isSuperAdmin, hasRole],
    );

    // Memoize the context value so the ~39 consumers only re-render when auth state
    // actually changes (user/loading), not on every AuthProvider render. All the
    // functions below are useCallback-stabilized so this memo is genuinely stable.
    const contextValue = useMemo(() => ({
        user,
        loading,
        loginSuccess,
        logout,
        hasRole,
        hasAnyRole,
        isSuperAdmin,
        canManageUsers,
    }), [user, loading, loginSuccess, logout, hasRole, hasAnyRole, isSuperAdmin, canManageUsers]);

    return (
        <AuthContext.Provider value={contextValue}>
            {children}
        </AuthContext.Provider>
    );
};
