import {useContext} from "react";
import {AuthContext} from "../context/AuthContext";

/**
 * Renders children only when the current user passes the role check.
 * Superusers always pass.
 *
 * Props:
 *   role       — require exactly this role code
 *   anyRole    — require at least one of these role codes (array)
 *   fallback   — what to render when the check fails (default: nothing)
 *
 * Examples:
 *   <PermissionGate role="LICENSE_MANAGER">
 *     <CreateButton />
 *   </PermissionGate>
 *
 *   <PermissionGate anyRole={['LICENSE_MANAGER', 'LICENSE_VIEWER']} fallback={<p>No access</p>}>
 *     <LicenseList />
 *   </PermissionGate>
 */
export default function PermissionGate({role, anyRole, children, fallback = null}) {
    const {hasRole, hasAnyRole} = useContext(AuthContext);

    if (role && !hasRole(role)) return fallback;
    if (anyRole && !hasAnyRole(anyRole)) return fallback;

    return children;
}
