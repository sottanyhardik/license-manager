// Re-export the shared formatters/error-extractor from `pages/license-balance/`
// rather than duplicating them — `licenseBalanceHelpers.ts` itself stays put
// (still imported by other license-balance/license-overview consumers), but
// nothing stops this module from importing and re-using its formatters.
export { fmtNum, fmtDate, extractApiError } from "@/pages/license-balance/licenseBalanceHelpers";
import type {
    InvoiceLedgerStatus,
    LicenseOverviewStatus,
    OverviewAllotmentStatus,
    OverviewBoeStatus,
} from "./types";

// ─── Status badge variants ─────────────────────────────────────────────────

const LICENSE_STATUS_BADGE_VARIANT: Record<LicenseOverviewStatus, "success" | "warning" | "destructive" | "secondary"> = {
    Active: "success",
    Expired: "destructive",
    Inactive: "secondary",
};

export function licenseOverviewStatusVariant(status: LicenseOverviewStatus) {
    return LICENSE_STATUS_BADGE_VARIANT[status] ?? "secondary";
}

const BOE_STATUS_VARIANT: Record<OverviewBoeStatus, "success" | "warning" | "destructive" | "secondary"> = {
    Reconciled: "success",
    Pending: "warning",
    Frozen: "secondary",
    Dispute: "destructive",
};

export function overviewBoeStatusVariant(status: OverviewBoeStatus) {
    return BOE_STATUS_VARIANT[status] ?? "secondary";
}

const ALLOTMENT_STATUS_VARIANT: Record<OverviewAllotmentStatus, "success" | "warning" | "destructive" | "secondary" | "info"> = {
    "Linked to BOE": "success",
    Allotted: "info",
    Approved: "warning",
    Pending: "secondary",
};

export function overviewAllotmentStatusVariant(status: OverviewAllotmentStatus) {
    return ALLOTMENT_STATUS_VARIANT[status] ?? "secondary";
}

const INVOICE_LEDGER_STATUS_VARIANT: Record<InvoiceLedgerStatus, "success" | "warning" | "destructive"> = {
    Paid: "success",
    Partial: "warning",
    Unpaid: "destructive",
};

export function invoiceLedgerStatusVariant(status: InvoiceLedgerStatus) {
    return INVOICE_LEDGER_STATUS_VARIANT[status] ?? "secondary";
}

// ─── Generic client-side sort helper shared by the new tabs ───────────────

export type SortDirection = "asc" | "desc";

export interface SortState<K extends string> {
    key: K | null;
    direction: SortDirection;
}

/** Stable sort by a string/number-valued accessor, nulls/undefined always last regardless of direction. */
export function sortRows<T, K extends string>(
    rows: T[],
    sort: SortState<K>,
    accessor: (row: T, key: K) => string | number | null | undefined
): T[] {
    if (!sort.key) return rows;
    const { key, direction } = sort;
    const withIndex = rows.map((row, index) => ({ row, index }));
    withIndex.sort((a, b) => {
        const av = accessor(a.row, key);
        const bv = accessor(b.row, key);
        const aEmpty = av === null || av === undefined || av === "";
        const bEmpty = bv === null || bv === undefined || bv === "";
        if (aEmpty && bEmpty) return a.index - b.index;
        if (aEmpty) return 1;
        if (bEmpty) return -1;
        let cmp: number;
        if (typeof av === "number" && typeof bv === "number") {
            cmp = av - bv;
        } else {
            cmp = String(av).localeCompare(String(bv), undefined, { numeric: true, sensitivity: "base" });
        }
        if (cmp === 0) return a.index - b.index;
        return direction === "asc" ? cmp : -cmp;
    });
    return withIndex.map((w) => w.row);
}
