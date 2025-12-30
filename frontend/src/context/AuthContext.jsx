import {createContext, useEffect, useState, useRef} from "react";
import api from "../api/axios";

export const AuthContext = createContext();

export const AuthProvider = ({children}) => {
    const [user, setUser] = useState(
        localStorage.getItem("user")
            ? JSON.parse(localStorage.getItem("user"))
            : null
    );
    const [loading, setLoading] = useState(true);
    const loadUserCalled = useRef(false);

    const loadUser = async () => {
        // Prevent duplicate calls in StrictMode
        if (loadUserCalled.current) return;
        loadUserCalled.current = true;

        // Don't attempt to load user if no access token exists
        const token = localStorage.getItem("access");
        if (!token) {
            setLoading(false);
            return;
        }

        try {
            const {data} = await api.get("/auth/me/");
            setUser(data);
            localStorage.setItem("user", JSON.stringify(data));
        } catch (err) {
            localStorage.clear();
            setUser(null);
        }
        setLoading(false);
    };

    useEffect(() => {
        loadUser();
    }, []);

    const loginSuccess = (data) => {
        localStorage.setItem("access", data.access);
        localStorage.setItem("refresh", data.refresh);
        localStorage.setItem("user", JSON.stringify(data.user));
        setUser(data.user);
        setLoading(false); // Ensure loading is false after login
    };

    const logout = async () => {
        try {
            await api.post("/auth/logout/", {
                refresh: localStorage.getItem("refresh")
            });
        } catch {
        }
        localStorage.clear();
        setUser(null);
        window.location.href = "/login";
    };

    const hasRole = (roleCodes) => {
        if (!user || !roleCodes || roleCodes.length === 0) return true;

        // Superuser has all permissions
        if (user.is_superuser) return true;

        // Check if user has any of the required role codes
        if (user.role_codes && user.role_codes.length > 0) {
            return roleCodes.some(code => user.role_codes.includes(code));
        }

        return false;
    };

    return (
        <AuthContext.Provider value={{user, loading, loginSuccess, logout, hasRole}}>
            {children}
        </AuthContext.Provider>
    );
};
