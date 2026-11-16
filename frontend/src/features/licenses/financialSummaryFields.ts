import type { CustomsLedgerSummary } from "@/pages/license-balance/types";

/**
 * Each figure maps 1:1 to `GET licenses/:id/balance-ledger/` →
 * `customs_ledger.summary.<field>`, with the labels the overview page's
 * CustomsLedgerTable flow strip already uses. Values are rendered as received.
 * `signed` marks balances that get danger styling when negative.
 */
export const FINANCIAL_SUMMARY_FIELDS: { key: keyof CustomsLedgerSummary; label: string; signed?: boolean }[] = [
    { key: "opening_balance", label: "Original Licence CIF" },
    { key: "total_boe_cif", label: "Total BOE CIF" },
    { key: "remaining_after_boe", label: "Remaining After BOE", signed: true },
    { key: "total_pending_allotment_cif", label: "Pending / Unlinked Allotted CIF" },
    { key: "computed_balance", label: "Available Balance", signed: true },
    { key: "difference", label: "Difference", signed: true },
];
