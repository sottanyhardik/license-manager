import {useContext} from "react";
import {Navigate, useLocation} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";

export default function ProtectedRoute({children}) {
    const {user, loading} = useContext(AuthContext);
    const location = useLocation();

    if (loading) return <div className="p-4">Loading...</div>;

    if (!user) {
        // Save the current path to redirect back after login
        return <Navigate to="/login" state={{from: location.pathname}} replace />;
    }

    return children;
}
