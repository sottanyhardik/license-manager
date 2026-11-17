import type { Tone } from "@/components/shared/tone";

/** Backend-computed `invoice_status` (BillOfEntrySerializer). Never derive it from `invoice_no`. */
export type BoeInvoiceStatus = "hidden" | "invoiced" | "invoice_no_recorded" | "not_invoiced";

const STATUS_TONE: Record<BoeInvoiceStatus, Tone> = {
    invoiced: "success",
    invoice_no_recorded: "info",
    not_invoiced: "neutral",
    hidden: "neutral",
};

/** Fallback labels, used only when the API omits `invoice_status_label`. */
const STATUS_LABEL: Record<BoeInvoiceStatus, string> = {
    hidden: "Hidden",
    invoiced: "Invoiced",
    invoice_no_recorded: "Invoice no. recorded",
    not_invoiced: "Not invoiced",
};

export interface BoeInvoiceBadge {
    tone: Tone;
    label: string;
    /** Muted (hidden) rows get the soft neutral treatment with reduced emphasis. */
    muted: boolean;
}

export function boeInvoiceBadge(item: { invoice_status?: unknown; invoice_status_label?: unknown }): BoeInvoiceBadge | null {
    const status = item.invoice_status as BoeInvoiceStatus | undefined;
    if (!status || !(status in STATUS_TONE)) return null;
    const label = typeof item.invoice_status_label === "string" && item.invoice_status_label
        ? item.invoice_status_label
        : STATUS_LABEL[status];
    return { tone: STATUS_TONE[status], label, muted: status === "hidden" };
}
