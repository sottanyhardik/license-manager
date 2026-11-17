import type { CustomsLedgerSummary } from "@/pages/license-balance/types";

/**
 * Each figure maps 1:1 to `GET licenses/:id/balance-ledger/` →
 * `customs_ledger.summary.<field>`, with the labels the overview page's
 * CustomsLedgerTable flow strip already uses. Values are rendered as received.
 * Figures the API does not return (utilised, billed-without-BOE) are deliberately
 * absent: nothing is computed client-side. `signed` marks balances that get danger styling when negative.
 */
export const FINANCIAL_SUMMARY_FIELDS: { key: keyof CustomsLedgerSummary; label: string; signed?: boolean; emphasis?: boolean }[] = [
    { key: "opening_balance", label: "Original CIF" },
    { key: "total_boe_cif", label: "BOE CIF" },
    { key: "remaining_after_boe", label: "Remaining After BOE", signed: true },
    { key: "total_pending_allotment_cif", label: "Outstanding Allotment CIF" },
    { key: "computed_balance", label: "Available CIF (customs)", signed: true, emphasis: true },
    { key: "difference", label: "Difference", signed: true },
];
