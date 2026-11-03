import type { AttentionItem } from "@/pages/dashboardContract";
import { attentionTarget } from "./dashboardLinks";

export type AttentionCopy = { title: string; description: string; action: string };

/** Copy for each verified attention key. Unknown keys fall back to the key itself. */
export const ATTENTION_COPY: Record<string, AttentionCopy> = {
    expired_with_balance: {
        title: "Expired licences with balance",
        description: "Expired licences that still show financial balance. Check whether they should be closed out.",
        action: "Review expired licences",
    },
    expiring_7d_usable: {
        title: "Expiring within 7 days",
        description: "Active licences expiring within 7 days whose live financial balance is at least 100.",
        action: "View expiring licences",
    },
    missing_dgft: {
        title: "Missing DGFT details",
        description: "Licences whose live balance is below 200 (Null DFIA rule of the licence list).",
        action: "Open licences",
    },
    over_utilised: {
        title: "Over-utilised licences",
        description: "Utilisation exceeds credit. The balance is floored at zero, so the excess is not visible on the licence.",
        action: "Review financial bridge",
    },
    stale_expiry_flags: {
        title: "Stale expiry flags",
        description: "The stored expired flag disagrees with the expiry date. It is corrected on the next licence save.",
        action: "Open expired licences",
    },
    c969_link_review: {
        title: "C969 saved items to review",
        description: "A saved item differs from the item its product name selects. Nothing has been changed.",
        action: "Review C969 items",
    },
    boe_pending_licence_mapping: {
        title: "BOEs pending licence mapping",
        description: "Bills of entry with no licence item rows, so they cannot be debited against a licence.",
        action: "Open BOEs",
    },
    boe_without_invoice_no: {
        title: "BOEs without invoice number",
        description: "Bills of entry where the invoice number is blank.",
        action: "Open BOEs",
    },
    invoices_outstanding: {
        title: "Invoices with balance outstanding",
        description: "Invoices where the amount still to pay or receive is above zero.",
        action: "Open invoices",
    },
};

export type AttentionRow = AttentionItem & {
    title: string;
    description: string;
    action: string;
    href: string | null;
};

/** Joins verified attention items with copy and link targets. */
export function buildAttentionRows(items: AttentionItem[], companyId: number | null): AttentionRow[] {
    return items
        .filter((item) => item.count > 0)
        .map((item) => {
            const copy = ATTENTION_COPY[item.key] ?? {
                title: item.key.replace(/_/g, " "),
                description: "",
                action: "View",
            };
            return { ...item, ...copy, href: attentionTarget(item.key, companyId) };
        });
}
