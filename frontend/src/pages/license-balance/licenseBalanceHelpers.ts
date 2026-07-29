import { formatIndianNumber } from "@/utils/numberFormatter";
import { formatDate } from "@/utils/dateFormatter";
import type { CustomsLedgerRowKind, FinancialLedgerRowKind, TimelineEventColor } from "./types";

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

/** Format an ISO datetime string as date + time, "—" for empty/invalid — used by the Timeline. */
export function fmtDateTime(value: string | null | undefined): string {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "—";
    const datePart = formatDate(value) || "—";
    const timePart = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    return `${datePart} ${timePart}`;
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
    /** A credit entry, like Opening Balance — kept visually distinct from
     * the debit-side "trade" (Sold) rows below. */
    trade_purchase: "bg-info/10",
    trade: "bg-primary/10",
    final: "bg-muted font-semibold",
};

export function financialLedgerRowClass(rowKind: FinancialLedgerRowKind, mismatched?: boolean): string {
    if (mismatched) return "bg-destructive/10 text-destructive";
    return ROW_KIND_CLASSES[rowKind] ?? "";
}

// ─── Customs ledger row-kind styling ──────────────────────────────────────
// Same semantic-not-pixel-matched approach as the Financial Ledger, kept
// visually distinct so the two ledgers are never mistaken for one another.
const CUSTOMS_ROW_KIND_CLASSES: Record<CustomsLedgerRowKind, string> = {
    customs_opening: "bg-info/10",
    customs_boe: "bg-primary/10",
    customs_pending_allotment: "bg-warning/10",
    final: "bg-muted font-semibold",
};

export function customsLedgerRowClass(rowKind: CustomsLedgerRowKind, mismatched?: boolean): string {
    if (mismatched) return "bg-destructive/10 text-destructive";
    return CUSTOMS_ROW_KIND_CLASSES[rowKind] ?? "";
}

const CUSTOMS_STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "info" | "secondary"> = {
    Matched: "success",
    Unmatched: "destructive",
    Pending: "warning",
    "Balance Engine": "info",
    "-": "secondary",
};

export function customsStatusVariant(status: string) {
    return CUSTOMS_STATUS_VARIANT[status] ?? "secondary";
}

// ─── Timeline event color mapping ─────────────────────────────────────────
// Maps the backend's `color` tone (shared with the PDF's `TONE_COLORS`) onto
// this app's design tokens — a Badge variant for the event-type chip and a
// small dot class for the vertical rail, kept semantically (not
// pixel-)consistent with the PDF's own color-per-event-type convention.
const TIMELINE_COLOR_BADGE_VARIANT: Record<TimelineEventColor, "default" | "secondary" | "destructive" | "success" | "warning" | "info" | "outline"> = {
    blue: "info",
    orange: "warning",
    green: "success",
    purple: "default",
    teal: "secondary",
    grey: "secondary",
    red: "destructive",
};

export function timelineColorBadgeVariant(color: TimelineEventColor) {
    return TIMELINE_COLOR_BADGE_VARIANT[color] ?? "secondary";
}

const TIMELINE_COLOR_DOT_CLASSES: Record<TimelineEventColor, string> = {
    blue: "bg-info",
    orange: "bg-warning",
    green: "bg-success",
    purple: "bg-primary",
    teal: "bg-secondary-foreground/60",
    grey: "bg-muted-foreground",
    red: "bg-destructive",
};

export function timelineColorDotClass(color: TimelineEventColor): string {
    return TIMELINE_COLOR_DOT_CLASSES[color] ?? "bg-muted-foreground";
}

// ─── Financial integrity score badge ──────────────────────────────────────
export function integrityScoreBadgeVariant(score: number): "success" | "warning" | "destructive" {
    if (score >= 95) return "success";
    if (score >= 70) return "warning";
    return "destructive";
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
