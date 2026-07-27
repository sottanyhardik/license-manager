/**
 * Types for the Licence Balance & Financial Reconciliation Workspace.
 *
 * Mirrors the exact JSON shape returned by
 * `GET /api/licenses/<id>/balance-ledger/`, built server-side by
 * `LicenseBalanceLedgerBuilder.build()`
 * (`backend/apps/license/services/license_balance_ledger_builder.py`) and
 * shaped for the wire by `_json_safe()`
 * (`backend/apps/license/views/license_balance_ledger.py`) — every Decimal
 * becomes a plain `number`, every date becomes an ISO `YYYY-MM-DD` string or
 * `null`.
 */

export interface LicenseBalanceLicense {
    id: number;
    license_number: string | null;
    license_date: string | null;
    license_expiry_date: string | null;
    exporter: string | null;
    original_cif: number;
    original_qty: number;
    current_balance_cif: number;
    current_balance_qty: number;
    financial_integrity_score: number;
    difference: number;
}

export type FinancialLedgerRowKind = "opening" | "boe" | "allotment" | "trade" | "final";

export interface FinancialLedgerRow {
    sr: number;
    date: string | null;
    type: string;
    document_number: string | null;
    boe_number: string | null;
    boe_date: string | null;
    company: string | null;
    item_name: string | null;
    invoice_numbers: string[];
    qty: number | null;
    cif_usd: number | null;
    cif_inr: number | null;
    credit: number;
    debit: number;
    running_balance: number;
    remarks: string | null;
    row_kind: FinancialLedgerRowKind;
    row_details_id?: number;
    allotment_item_id?: number;
    mismatched?: boolean;
}

export interface FinancialLedgerSummary {
    opening_balance: number;
    total_boe_debit: number;
    total_allotment_debit: number;
    total_trade_debit: number;
    computed_balance: number;
    engine_balance: number;
    difference: number;
    mismatched: boolean;
    tolerance: number;
}

export interface LinkedBoe {
    allocation_id?: number;
    link_id?: number;
    row_details_id: number;
    bill_of_entry_number: string;
    allocated_qty: number;
    allocated_cif_fc: number;
}

export type InvoiceBoeStatus = "FULLY_MATCHED" | "PARTIALLY_MATCHED" | "UNMATCHED" | "EXTERNAL";

export interface InvoiceBoeEntry {
    kind: "system" | "external";
    trade_line_id?: number;
    invoice_number: string;
    supplier: string | null;
    purchase_date: string | null;
    invoice_qty: number;
    invoice_cif: number;
    matched_qty: number;
    matched_cif: number;
    remaining_qty: number;
    remaining_cif: number;
    status: InvoiceBoeStatus;
    linked_boes: LinkedBoe[];
}

export interface LinkedAllotment {
    allocation_id: number;
    allotment_item_id: number;
    allotment_number: string;
    allocated_qty: number;
    allocated_cif_fc: number;
}

export type BoeAllotmentStatus = "FULLY_SOURCED" | "PARTIALLY_SOURCED" | "UNSOURCED";

export interface BoeAllotmentEntry {
    row_details_id: number;
    bill_of_entry_number: string;
    bill_of_entry_date: string | null;
    company: string | null;
    boe_qty: number;
    boe_cif: number;
    matched_qty: number;
    matched_cif: number;
    remaining_qty: number;
    remaining_cif: number;
    status: BoeAllotmentStatus;
    linked_allotments: LinkedAllotment[];
}

export interface ReconciliationSummary {
    financial_ledger_balance: number;
    customs_ledger_balance: number;
    balance_engine: number;
    difference: number;
    tolerance: number;
    matched: boolean;
}

export interface LicenseBalanceLedgerData {
    license: LicenseBalanceLicense;
    financial_ledger: {
        rows: FinancialLedgerRow[];
        summary: FinancialLedgerSummary;
    };
    invoice_boe: InvoiceBoeEntry[];
    boe_allotment: BoeAllotmentEntry[];
    reconciliation: ReconciliationSummary;
    warnings: string[];
}
