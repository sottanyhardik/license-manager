import React, {createContext, useCallback, useEffect, useMemo, useRef, useState} from "react";
import api, { AUTH_SESSION_EVENT_KEY, clearStoredAuth, publishAuthEvent, refreshAccessToken } from "../api/axios";
import type { AuthContextValue, AuthUser, LoginResponse } from "../types";

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue>({
    user: null,
    loading: true,
    loginSuccess: () => {},
    updateUser: () => {},
    logout: async () => {},
    hasRole: () => false,
    hasAnyRole: () => false,
    isSuperAdmin: () => false,
    canManageUsers: () => false,
});

// ─── Session config ───────────────────────────────────────────────────────────
// A session expires only after five continuous minutes without meaningful use.
const IDLE_TIMEOUT_MS = 5 * 60 * 1000;
const ACTIVITY_THROTTLE_MS = 1000;
const REFRESH_EARLY_MS = 5 * 60 * 1000;
// ─────────────────────────────────────────────────────────────────────────────

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

type JwtPayload = { exp?: number };

function accessTokenExpiry(access: string | null): number | null {
    if (!access) return null;
    try {
        const payload = access.split(".")[1];
        if (!payload) return null;
        const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
        const decoded = JSON.parse(window.atob(normalized)) as JwtPayload;
        return typeof decoded.exp === "number" ? decoded.exp * 1000 : null;
    } catch {
        return null;
    }
}

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
    const [loading, setLoading] = useState(true);
    const loadUserCalled = useRef(false);
    const lastActivityRef = useRef(Date.now());
    const lastActivityWriteRef = useRef(0);
    const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const logoutInProgressRef = useRef(false);

    const clearTimers = () => {
        if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
        idleTimerRef.current = null;
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
    };

    const logout = useCallback(async (reason?: string) => {
        if (logoutInProgressRef.current) return;
        logoutInProgressRef.current = true;
        clearTimers();
        try {
            await api.post("auth/logout/", {
                refresh: localStorage.getItem("refresh")
            });
        } catch {
            // Ignore logout API errors — clear locally regardless
        }
        const currentPath = window.location.pathname;
        clearStoredAuth();
        publishAuthEvent("logout");
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

    // Reset the idle clock whenever the user interacts with the page
    const resetActivity = useCallback(() => {
        const now = Date.now();
        if (now - lastActivityWriteRef.current < ACTIVITY_THROTTLE_MS) return;
        lastActivityWriteRef.current = now;
        lastActivityRef.current = now;
        if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
        idleTimerRef.current = setTimeout(() => logout('idle'), IDLE_TIMEOUT_MS);
    }, [logout]);

    const startIdleTimer = useCallback(() => {
        if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
        const remaining = Math.max(IDLE_TIMEOUT_MS - (Date.now() - lastActivityRef.current), 0);
        idleTimerRef.current = setTimeout(() => logout('idle'), remaining);
    }, [logout]);

    const scheduleRefresh = useCallback(() => {
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        const expiry = accessTokenExpiry(localStorage.getItem("access"));
        if (!expiry) return;
        const delay = Math.max(expiry - Date.now() - REFRESH_EARLY_MS, 0);
        refreshTimerRef.current = setTimeout(async () => {
            try {
                const previousAccess = localStorage.getItem("access");
                await refreshAccessToken();
                // A successful SimpleJWT refresh always writes a new access
                // token. Avoid a zero-delay refresh loop if an adapter returns
                // success without updating storage (for example, a malformed
                // test stub or a proxy stripping the response body).
                if (localStorage.getItem("access") !== previousAccess) scheduleRefresh();
            } catch {
                // refreshAccessToken emits one cross-tab logout and redirect.
                setUser(null);
            }
        }, delay);
    }, []);

    // Wire up activity listeners and timers when user is logged in
    useEffect(() => {
        if (!user) return;

        // `scroll` does not bubble from nested scroll containers. Capture it
        // on document so activity in page panels, tables and dialogs counts as
        // activity just like clicks and keyboard input.
        const windowEvents = ['pointerdown', 'mousemove', 'keydown', 'touchstart', 'focus'];
        const documentEvents = ['scroll', 'wheel'];
        windowEvents.forEach(e => window.addEventListener(e, resetActivity, {passive: true}));
        documentEvents.forEach(e => document.addEventListener(e, resetActivity, {capture: true, passive: true}));
        const onStorage = (event: StorageEvent) => {
            if (event.key === AUTH_SESSION_EVENT_KEY && event.newValue) {
                try {
                    const message = JSON.parse(event.newValue) as { type?: string };
                    if (message.type === "refresh") scheduleRefresh();
                    if (message.type !== "logout") return;
                } catch {
                    return;
                }
                clearTimers();
                setUser(null);
                window.location.href = "/login";
            }
        };
        const onAuthEvent = (event: Event) => {
            const type = (event as CustomEvent<{ type?: string }>).detail?.type;
            if (type === "refresh") scheduleRefresh();
        };
        const onVisibilityChange = () => {
            if (!document.hidden) resetActivity();
        };
        window.addEventListener("storage", onStorage);
        window.addEventListener("auth:session", onAuthEvent);
        document.addEventListener("visibilitychange", onVisibilityChange);
        lastActivityRef.current = Date.now();
        startIdleTimer();
        scheduleRefresh();

        return () => {
            windowEvents.forEach(e => window.removeEventListener(e, resetActivity));
            documentEvents.forEach(e => document.removeEventListener(e, resetActivity, true));
            window.removeEventListener("storage", onStorage);
            window.removeEventListener("auth:session", onAuthEvent);
            document.removeEventListener("visibilitychange", onVisibilityChange);
            clearTimers();
        };
    }, [user, resetActivity, scheduleRefresh, startIdleTimer]);

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
            clearStoredAuth();
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
        logoutInProgressRef.current = false;
        lastActivityRef.current = Date.now();
        setUser(data.user);
        setLoading(false);
    }, []);

    const updateUser = useCallback((nextUser: AuthUser) => {
        localStorage.setItem("user", JSON.stringify(nextUser));
        setUser(nextUser);
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
        updateUser,
        logout,
        hasRole,
        hasAnyRole,
        isSuperAdmin,
        canManageUsers,
    }), [user, loading, loginSuccess, updateUser, logout, hasRole, hasAnyRole, isSuperAdmin, canManageUsers]);

    return (
        <AuthContext.Provider value={contextValue}>
            {children}
        </AuthContext.Provider>
    );
};
