import { useContext } from "react";

import { AuthContext } from "@/context/AuthContext";
import { ROLES } from "@/routes/authorizationRoles";

/**
 * Mirrors AccountingPermission (backend/apps/accounts/permissions.py) so the UI never shows an
 * action the API would refuse: write = draft/confirm/match/upload (manager or approver);
 * approve = post, reverse, payments, suspense, loans, migration, books setup (approver).
 * Superusers pass both (AuthContext.hasAnyRole already bypasses for them).
 */
export function useAccountingAccess(): { canWrite: boolean; canApprove: boolean } {
    const { hasAnyRole } = useContext(AuthContext);
    return {
        canWrite: hasAnyRole([ROLES.ACCOUNTS_MANAGER, ROLES.ACCOUNTS_APPROVER]),
        canApprove: hasAnyRole([ROLES.ACCOUNTS_APPROVER]),
    };
}
