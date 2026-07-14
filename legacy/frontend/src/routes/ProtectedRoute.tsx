import React, {useContext} from "react";
import {Navigate, useLocation} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";

interface ProtectedRouteProps {
    children: React.ReactNode;
    requiredRole?: string;
    requiredAnyRole?: string[];
    requireSuperuser?: boolean;
}

/**
 * Wraps a route so it requires authentication.
 *
 * Optional role guards:
 *   requiredRole      — user must have exactly this role (or be superuser)
 *   requiredAnyRole   — user must have at least one of these roles (or be superuser)
 *
 * Unauthenticated users → /login
 * Authenticated but unauthorised users → /403
 */
export default function ProtectedRoute({children, requiredRole, requiredAnyRole, requireSuperuser}: ProtectedRouteProps) {
    const {user, loading, hasRole, hasAnyRole} = useContext(AuthContext);
    const location = useLocation();

    if (loading) return <div className="p-4">Loading...</div>;

    if (!user) {
        return <Navigate to="/login" state={{from: location.pathname}} replace/>;
    }

    if (requireSuperuser && !user.is_superuser) {
        return <Navigate to="/403" replace/>;
    }

    if (requiredRole && !hasRole(requiredRole)) {
        return <Navigate to="/403" replace/>;
    }

    if (requiredAnyRole && !hasAnyRole(requiredAnyRole)) {
        return <Navigate to="/403" replace/>;
    }

    return <>{children}</>;
}
