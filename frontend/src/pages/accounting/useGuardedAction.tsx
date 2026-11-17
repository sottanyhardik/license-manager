import { useCallback, type ReactNode } from "react";

import { useConfirmDialog } from "@/hooks/useConfirmDialog";

export interface GuardConfig {
    title: string;
    message: string;
    confirmText: string;
    /** "danger" for reversals, unlocks, migrations; "warning" for posting. */
    severity?: "warning" | "danger" | "info";
}

/**
 * Confirmation for financial actions, reusing the app's accessible ConfirmDialog.
 * `guard(config, action)` runs `action` only after the user confirms.
 */
export function useGuardedAction(): { guard: (config: GuardConfig, action: () => void) => Promise<void>; dialog: ReactNode } {
    const { showConfirm, confirmDialog } = useConfirmDialog();
    const guard = useCallback(async (config: GuardConfig, action: () => void) => {
        const ok = await showConfirm({ severity: "warning", ...config });
        if (ok) action();
    }, [showConfirm]);
    return { guard, dialog: confirmDialog };
}
