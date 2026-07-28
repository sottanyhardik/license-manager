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

export type FinancialLedgerRowKind = "opening" | "boe" | "boe_allocation" | "allotment" | "trade" | "final";

/**
 * A child row nested under a "boe_allocation" parent row — one per
 * underlying `InvoiceBOEAllocation` that makes up the parent's consolidated
 * debit. Informational only: `credit`/`debit`/`running_balance` are always
 * `null` on the wire (the parent already carries the accounting impact), so
 * these must always render as blank/em-dash, never their own numbers.
 */
export interface FinancialLedgerChildRow {
    type: string;
    row_kind: "boe_child";
    boe_number: string | null;
    boe_date: string | null;
    company: string | null;
    item_name: string | null;
    invoice_numbers: string[];
    qty: number | null;
    cif_usd: number | null;
    cif_inr: number | null;
    credit: null;
    debit: null;
    running_balance: null;
    status: "Matched" | "Partially Matched";
    remarks: string | null;
    row_details_id?: number;
    allocation_id?: number;
}

export interface FinancialLedgerRow {
    sr: number;
    date: string | null;
    type: string;
    document_number: string | null;
    boe_number: string | null;
    boe_date: string | null;
    /** Pre-joined display string for boe_date, only set on "boe_allocation"
     * rows (e.g. "20-02-2026, 20-02-2026") — prefer this over `boe_date`
     * when present. */
    boe_date_display?: string;
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
    /** Only on "boe_allocation" rows — the raw list behind the joined
     * `boe_number` display string, for UI truncation ("7650222 (+1)") with
     * a tooltip showing the rest. */
    linked_boe_numbers?: string[];
    linked_boe_dates?: (string | null)[];
    trade_line_id?: number;
    mismatched?: boolean;
    /** True only on "boe_allocation" rows that carry >=1 child. */
    expandable?: boolean;
    children?: FinancialLedgerChildRow[];
}

export interface FinancialLedgerSummary {
    opening_balance: number;
    total_boe_debit: number;
    /** Sum of the consolidated "BOE Allocation" rows' debits — omitted (0)
     * when this licence has no reconciled invoice/BOE allocations yet. */
    total_invoice_allocation_debit?: number;
    total_allotment_debit: number;
    total_trade_debit: number;
    computed_balance: number;
    engine_balance: number;
    difference: number;
    mismatched: boolean;
    tolerance: number;
}

// ─── Customs Ledger — SEPARATE running-balance statement ──────────────────
// See `LicenseBalanceLedgerBuilder.build_customs_ledger`'s docstring: every
// BOE here debits at its FULL raw `cif_fc` unconditionally (never
// allocation-adjusted), so this ledger's own running total can legitimately
// differ from the Financial Ledger's — that gap IS the reconciliation
// signal, never silently forced to match.

export type CustomsLedgerRowKind = "customs_opening" | "customs_boe" | "customs_pending_allotment" | "final";

export interface CustomsLedgerRow {
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
    status: string;
    remarks: string | null;
    row_kind: CustomsLedgerRowKind;
    row_details_id?: number;
    allotment_item_id?: number;
    mismatched?: boolean;
}

export interface CustomsLedgerSummary {
    opening_balance: number;
    total_boe_cif: number;
    total_pending_allotment_cif: number;
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

/**
 * One BOE debit row on this licence with its INVOICE-SIDE remaining capacity
 * (`remaining_for_row_details_invoice_side`) — the correct candidate source
 * for the "Find BOE" drawer (Invoice ↔ BOE, `InvoiceBoeSection.tsx`). This is
 * a distinct consumption track from `BoeAllotmentEntry.remaining_*` (the
 * ALLOTMENT-side remaining) — the two only coincidentally match when neither
 * track has any allocations yet, which is why they must never be conflated.
 */
export interface BoeInvoiceCandidate {
    row_details_id: number;
    bill_of_entry_number: string;
    bill_of_entry_date: string | null;
    company: string | null;
    item_name: string | null;
    boe_qty: number;
    boe_cif: number;
    boe_cif_inr: number;
    remaining_qty: number;
    remaining_cif: number;
    remaining_cif_inr: number;
}

/**
 * One `AllotmentItems` row on this licence with remaining capacity to be
 * sourced BY a BOE (`remaining_for_allotment_item`) — the correct candidate
 * source for the "Find Allotment" drawer (BOE ↔ Allotment,
 * `BoeAllotmentSection.tsx`). Already filtered server-side to items with
 * some remaining qty or CIF.
 */
export interface AllotmentCandidate {
    allotment_item_id: number;
    allotment_number: string;
    company: string | null;
    item_name: string | null;
    estimated_arrival_date: string | null;
    allotment_qty: number;
    allotment_cif: number;
    remaining_qty: number;
    remaining_cif: number;
    remaining_cif_inr: number;
}

export interface ReconciliationSummary {
    financial_ledger_balance: number;
    customs_ledger_balance: number;
    balance_engine: number;
    difference: number;
    tolerance: number;
    matched: boolean;
}

// ─── Timeline — real, persisted business-lifecycle events only ────────────
// See `LicenseBalanceLedgerBuilder.build_timeline`'s docstring: nothing here
// is fabricated or inferred; an empty array means no real records exist yet.

export type TimelineEventColor = "blue" | "orange" | "green" | "purple" | "teal" | "grey" | "red";

/** Shared fields on both a top-level timeline event and its children. */
export interface TimelineEventBase {
    event_type: string;
    label: string;
    /** ISO datetime string. */
    date: string;
    document_number: string | null;
    company: string | null;
    quantity: number | null;
    cif: number | null;
    user: string | null;
    status: string | null;
    remarks: string | null;
    entity_reference: string | null;
    event_source: string | null;
    color: TimelineEventColor;
}

export type TimelineEventChild = TimelineEventBase;

export interface TimelineEvent extends TimelineEventBase {
    sr: number;
    expandable: boolean;
    children: TimelineEventChild[];
}

// ─── Warnings — structured, ignorable workflow entries ─────────────────────
// BREAKING CHANGE from the earlier `string[]` shape: each warning now
// carries a stable identity (`warning_type`/`entity_type`/`entity_id`) that
// round-trips through `ignore-warning`/`restore-warning`, plus ignore
// bookkeeping populated from `IgnoredWarning`. Ignoring a warning is pure
// workflow bookkeeping — it never changes any financial value elsewhere in
// this dataset.
export interface LicenseBalanceWarning {
    warning_type: string;
    entity_type: string;
    entity_id: string;
    message: string;
    ignored: boolean;
    ignored_by: string | null;
    ignored_at: string | null;
    reason: string;
}

export interface LicenseBalanceLedgerData {
    license: LicenseBalanceLicense;
    financial_ledger: {
        rows: FinancialLedgerRow[];
        summary: FinancialLedgerSummary;
    };
    customs_ledger: {
        rows: CustomsLedgerRow[];
        summary: CustomsLedgerSummary;
    };
    invoice_boe: InvoiceBoeEntry[];
    boe_allotment: BoeAllotmentEntry[];
    boe_invoice_candidates: BoeInvoiceCandidate[];
    allotment_candidates: AllotmentCandidate[];
    reconciliation: ReconciliationSummary;
    warnings: LicenseBalanceWarning[];
    timeline: TimelineEvent[];
}
