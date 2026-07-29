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

export type FinancialLedgerRowKind = "opening" | "boe" | "allotment" | "trade_purchase" | "trade" | "final";

/**
 * A child row nested under a "trade" (Licence Trade Sold) parent row — one
 * per underlying `InvoiceBOEAllocation` that backs the parent's invoice.
 * Informational only: `credit`/`debit`/`running_balance` are always `null`
 * on the wire (the parent already carries the accounting impact), so these
 * must always render as blank/em-dash, never their own numbers.
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
    /** Pre-joined display string for boe_date, only set on "trade" (Sold)
     * rows matched to >=1 BOE allocation (e.g. "20-02-2026, 20-02-2026") —
     * prefer this over `boe_date` when present. */
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
    /** Only on "boe" rows — always `"Pending Invoice"` while the row
     * exists (a fully-invoiced BOE debit is never displayed as its own row
     * — see `row_kind`'s docstring in the backend builder). Render as a
     * small badge next to `type`. */
    status?: string;
    row_details_id?: number;
    allotment_item_id?: number;
    /** Only on "trade" (Sold) rows matched to >=1 BOE allocation — the raw
     * list behind the joined `boe_number` display string, for UI
     * truncation ("7650222 (+1)") with a tooltip showing the rest. */
    linked_boe_numbers?: string[];
    linked_boe_dates?: (string | null)[];
    trade_line_id?: number;
    mismatched?: boolean;
    /** True only on "trade" (Sold) rows that carry >=1 child. */
    expandable?: boolean;
    children?: FinancialLedgerChildRow[];
    /** Only on "trade" (Sold) rows linked to a BOE (via `.boes` tag) whose
     * CIF doesn't cleanly match the invoice, or that map to more than one
     * candidate BOE — a data-quality signal, not a second financial
     * movement (the row's own `debit` already reflects the invoice's full
     * CIF; this never affects `running_balance`). Render as a warning
     * badge with an expandable BOE CIF / Invoice CIF / Difference detail. */
    mismatch_warning?: {
        show_warning: boolean;
        status: "mismatch" | "ambiguous";
        boe_cif: number;
        invoice_cif: number;
        difference: number;
        message: string;
    } | null;
}

export interface FinancialLedgerSummary {
    opening_balance: number;
    total_boe_debit: number;
    /** Sum of the consolidated "BOE Allocation" rows' debits — omitted (0)
     * when this licence has no reconciled invoice/BOE allocations yet. */
    total_invoice_allocation_debit?: number;
    total_allotment_debit: number;
    /** Sum of every PURCHASE trade line's cif_fc — display-only, NOT part
     * of `calculate_credit()`/`calculate_balance()` (those are unchanged;
     * see `get_purchase_trade_rows`'s docstring). */
    total_purchase_credit: number;
    total_trade_debit: number;
    computed_balance: number;
    engine_balance: number;
    difference: number;
    mismatched: boolean;
    tolerance: number;
    /** True when this licence has ANY Purchase or Sale trade line at all —
     * the Financial Ledger section should only be rendered when this is
     * true (see `build_financial_ledger`'s docstring: a licence with
     * neither has nothing this ledger adds over the Customs Ledger). */
    has_trading_activity: boolean;
    has_purchase: boolean;
    has_sale: boolean;
    /** Shown as a banner above the ledger — instead of a fabricated Opening
     * Balance row — when a Sale exists with no matching Purchase. */
    missing_purchase_warning: {
        show_warning: boolean;
        message: string;
    };
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
    /** Only ever `true` on a `"customs_boe"` row when the ledger was fetched
     * with `?show_hidden=true` (`GET .../balance-ledger/`) — a previous-owner
     * BOE debit (`RowDetails.is_hidden`), kept for audit but excluded from
     * every balance/financial calculation by default. Omitted/false rows
     * render exactly as before. */
    is_hidden?: boolean;
    /** Free-text reason captured when the row was hidden (`POST
     * .../hide-boe/`'s `reason`) — shown as a tooltip/subtitle next to the
     * "Hidden" badge. */
    hidden_reason?: string | null;
    /** Not currently populated on this row by the backend builder (only
     * `is_hidden`/`hidden_reason` are) — present on the wire type for
     * forward-compatibility with `hide-boe`/`restore-boe`'s own response
     * shape (`{id, is_hidden, rows_affected, hidden_by, hidden_at}`). */
    hidden_by?: string | null;
    hidden_at?: string | null;
    /** NOT currently returned by `LicenseBalanceLedgerBuilder.build_customs_
     * ledger` on `"customs_boe"` rows — the `BillOfEntryModel` PK the
     * `hide-boe`/`restore-boe` actions need as `boe_id`. Until the backend
     * adds it here, the Hide/Restore row action stays hidden for rows
     * missing this field rather than guessing an id from `boe_number`
     * (not globally unique — see `BillOfEntryModel.Meta.unique_together`). */
    bill_of_entry_id?: number;
}

export interface CustomsLedgerSummary {
    opening_balance: number;
    total_boe_cif: number;
    /** `opening_balance - total_boe_cif` — the balance flow's midpoint,
     * before the Pending Allotment deduction. */
    remaining_after_boe: number;
    /** Sum of `AllotmentItems.contributed` for allotments with NO BOE
     * association (`AllotmentModel.is_boe`) — allotments already linked to
     * a BOE are excluded entirely, not just their matched portion. */
    total_pending_allotment_cif: number;
    computed_balance: number;
    engine_balance: number;
    difference: number;
    mismatched: boolean;
    tolerance: number;
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
    reconciliation: ReconciliationSummary;
    warnings: LicenseBalanceWarning[];
    timeline: TimelineEvent[];
}
