import {useContext} from "react";
import {Navigate} from "react-router-dom";
import {AuthContext} from "../context/AuthContext";

export default function RoleRoute({children, roles}) {
    const {user, hasRole} = useContext(AuthContext);

    if (!user) {
        return <Navigate to="/login"/>;
    }

    if (!hasRole(roles)) {
        return <Navigate to="/401"/>;
    }

    return children;
}
