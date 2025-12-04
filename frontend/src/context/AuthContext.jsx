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
            console.log("ME ENDPOINT FAILED:", err.response);
            localStorage.clear();
            setUser(null);
        }
        setLoading(false);
    };

    useEffect(() => {
        loadUser();
    }, []);

    const loginSuccess = (data) => {
        console.log("SAVING TOKENS:", data);
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

    const hasRole = (roles) => {
        if (!user || !roles || roles.length === 0) return true;
        return roles.includes(user.role);
    };

    return (
        <AuthContext.Provider value={{user, loading, loginSuccess, logout, hasRole}}>
            {children}
        </AuthContext.Provider>
    );
};
