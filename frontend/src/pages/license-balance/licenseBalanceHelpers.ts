import { formatIndianNumber } from "@/utils/numberFormatter";
import { formatDate } from "@/utils/dateFormatter";
import type { FinancialLedgerRowKind } from "./types";

/** Format a number (or null/undefined) as an Indian-grouped 2dp string, "—" for empty. */
export function fmtNum(value: number | null | undefined, decimals = 2): string {
    if (value === null || value === undefined) return "—";
    const num = Number(value);
    if (Number.isNaN(num)) return "—";
    return formatIndianNumber(num, decimals);
}

/** Format an ISO date string, "—" for empty/invalid. */
export function fmtDate(value: string | null | undefined): string {
    if (!value) return "—";
    return formatDate(value) || "—";
}

/** Join a list of invoice numbers with ", ", "—" when empty. */
export function fmtInvoiceNumbers(values: string[] | null | undefined): string {
    if (!values || values.length === 0) return "—";
    return values.join(", ");
}

// ─── Financial ledger row-kind styling ────────────────────────────────────
// Semantic, not pixel-matched to the PDF's exact hex colours — conveys the
// same distinction (opening/boe/allotment/trade/final) via Tailwind
// utilities, with mismatched rows always rendered red regardless of kind.
const ROW_KIND_CLASSES: Record<FinancialLedgerRowKind, string> = {
    opening: "bg-info/10",
    boe: "bg-success/10",
    allotment: "bg-warning/10",
    trade: "bg-primary/10",
    final: "bg-muted font-semibold",
};

export function financialLedgerRowClass(rowKind: FinancialLedgerRowKind, mismatched?: boolean): string {
    if (mismatched) return "bg-destructive/10 text-destructive";
    return ROW_KIND_CLASSES[rowKind] ?? "";
}

// ─── Financial integrity score badge ──────────────────────────────────────
export function integrityScoreBadgeVariant(score: number): "success" | "warning" | "destructive" {
    if (score >= 95) return "success";
    if (score >= 70) return "warning";
    return "destructive";
}

// ─── Status badge variants for Invoice<->BOE / BOE<->Allotment tables ─────
const INVOICE_BOE_STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "info"> = {
    FULLY_MATCHED: "success",
    PARTIALLY_MATCHED: "warning",
    UNMATCHED: "destructive",
    EXTERNAL: "info",
};

const BOE_ALLOTMENT_STATUS_VARIANT: Record<string, "success" | "warning" | "destructive"> = {
    FULLY_SOURCED: "success",
    PARTIALLY_SOURCED: "warning",
    UNSOURCED: "destructive",
};

export function invoiceBoeStatusVariant(status: string) {
    return INVOICE_BOE_STATUS_VARIANT[status] ?? "secondary";
}

export function boeAllotmentStatusVariant(status: string) {
    return BOE_ALLOTMENT_STATUS_VARIANT[status] ?? "secondary";
}

/** Pull the most useful error string out of an axios error response — same shape as `utils/errorUtils.js`. */
export function extractApiError(error: unknown, fallback = "Request failed"): string {
    const err = error as { response?: { data?: { detail?: string; message?: string; error?: string } }; message?: string };
    return (
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        err?.response?.data?.error ||
        err?.message ||
        fallback
    );
}
