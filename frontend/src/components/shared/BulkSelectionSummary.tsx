import type { ReactNode } from "react";

export interface BulkSelectionSummaryProps {
    /** Number of selected rows; nothing renders when 0. */
    count: number;
    /** Bulk action controls for the current selection. */
    children: ReactNode;
}

/**
 * "N selected" + bulk actions. Shared by `DataTable` (table selection) and the
 * card registers (`GenericMasterCards`) so every list announces and lays out a
 * selection the same way.
 */
export function BulkSelectionSummary({ count, children }: BulkSelectionSummaryProps) {
    if (count <= 0) return null;
    return (
        <>
            <span className="text-xs text-muted-foreground" aria-live="polite">{count} selected</span>
            {children}
        </>
    );
}
