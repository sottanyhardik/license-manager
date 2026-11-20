/**
 * Types for the License Overview dashboard's 6 lightweight, read-only
 * endpoints — each backs exactly one tab of `LicenseOverviewPage.tsx` and is
 * fetched lazily (only once its tab is activated).
 *
 * Mirrors the doc-comment / wire-format-quirk style of
 * `pages/license-balance/types.ts`. Every Decimal on the backend becomes a
 * plain `number` here, every date an ISO `YYYY-MM-DD` string or `null` —
 * same `_json_safe()`-style convention as the balance-ledger endpoint.
 */

// ─── GET licenses/<id>/overview-summary/ — Overview tab header + 7 cards ──

export type LicenseOverviewStatus = "Expired" | "Active" | "Inactive";

export interface LicenseOverviewSummaryCounts {
    total_boes: number;
    /** Excludes allotments already linked to a BOE (`AllotmentModel.is_boe`). */
    total_allotments: number;
    /** Sum of `LicenseItemPlan.planned_cif_fc` across every Utilization
     * Planning record on this license — `0` when there are no plan records at all. */
    total_planned_cif: number;
    total_cif: number;
    total_debited_cif: number;
    total_allotted_cif: number;
    total_balance_cif: number;
}

export interface LicenseOverviewSummary {
    balance_cif?: string | number | null;
    /** `true` opts into per-import-item CIF ceilings; null/false are legacy. */
    individual_item_cif_override?: boolean | null;
    license_number: string | null;
    /** = `LicenseDetailsModel.registration_number` — no field literally
     * named "authorisation number" exists on the backend. */
    authorisation_number: string | null;
    file_number: string | null;
    license_date: string | null;
    license_expiry_date: string | null;
    importer: string | null;
    status: LicenseOverviewStatus;
    /** `core.PurchaseStatus` FK (GE/MI/IP/SM/CO, etc.) — editable via the
     * generic `PATCH licenses/{id}/` endpoint, same field the main license
     * form already writes. `null` when never set. */
    purchase_status_id: number | null;
    purchase_status_code: string | null;
    purchase_status_label: string | null;
    /** `core.PortModel` FK — display-only, same additive convention as
     * `purchase_status_*` above. `null` when the license has no port set. */
    port_code: string | null;
    port_name: string | null;
    summary: LicenseOverviewSummaryCounts;
}

// ─── GET licenses/<id>/overview-boes/ — BOEs tab ──────────────────────────
// One row per distinct BOE linked to this license (NOT one row per ledger
// entry) — status/remaining-CIF are allocation-aware, computed the same way
// as `LicenseBalanceLedgerBuilder.build_boe_allotment_relationships`, never
// a raw re-sum of `RowDetails`.

export type OverviewBoeStatus = "Dispute" | "Frozen" | "Reconciled" | "Pending";

export interface LicenseOverviewBoeRow {
    bill_of_entry_number: string | null;
    bill_of_entry_date: string | null;
    port: string | null;
    supplier: string | null;
    invoice_no: string | null;
    invoice_date: string | null;
    cif_fc: number;
    status: OverviewBoeStatus;
}

// ─── GET licenses/<id>/overview-allotments/ — Allotments tab ─────────────

export type OverviewAllotmentStatus = "Linked to BOE" | "Approved" | "Allotted" | "Pending";

export interface LicenseOverviewAllotmentRow {
    /** Synthesized `f"ALT-{allotment.id}"` — same convention as
     * `license_balance_ledger_builder.py:379`. */
    allotment_number: string;
    date: string | null;
    customer: string | null;
    /** Free-text `AllotmentModel.item_name` — no product FK exists. */
    product: string | null;
    quantity: number;
    /** Gross allotted CIF (includes allotments already represented by BOEs). */
    cif_fc: number;
    /** Still-reserved CIF counted in ALLOTMENT CIF — the Balance Engine's
     * per-row `contributed` (0 once a BOE represents the allotment). Sum this,
     * not `cif_fc`, for an allotment utilisation total. */
    outstanding_cif_fc: number;
    status: OverviewAllotmentStatus;
}

// ─── GET licenses/<id>/overview-items/ — Items tab ────────────────────────

export interface LicenseOverviewItemRow {
    id: number;
    description: string | null;
    hs_code: string | null;
    unit: string | null;
    total_qty: number;
    total_cif: number;
    debited_qty: number;
    debited_cif: number;
    allotted_qty: number;
    allotted_cif: number;
    /** `total_qty - debited_qty - allotted_qty`. */
    balance_qty: number;
    /**
     * `total_cif - debited_cif - allotted_cif` — a NEW, display-only figure
     * deliberately different from any "balance"/"available" value shown
     * elsewhere in the app for the same item (e.g. the license accordion
     * row, or the old Balance workspace's `available_value`, which is
     * license-level-shared with a `serial_number == 1` special case). A
     * mismatch between this and those other figures for the same item is
     * intentional, not a bug — two different formulas coexist by design.
     */
    balance_cif: number;
    individual_item_cif?: boolean;
    license_balance_cif?: number;
    individual_item_balance_cif?: number;
    balance_cif_source?: "LICENSE" | "ITEM" | string;
    /** Canonical effective balance supplied by the backend selector. */
    effective_balance_cif?: number;
}

export interface LicenseOverviewItemFooterTotals {
    total_cif?: number;
    debited_cif?: number;
    allotted_cif?: number;
    planned_cif?: number;
    actual_effective_balance_cif?: number;
    balance_cif?: number;
    plan_remaining_cif?: number;
    [key: string]: number | undefined;
}

export interface LicenseOverviewItemsResponse {
    rows: LicenseOverviewItemRow[];
    footer_totals?: LicenseOverviewItemFooterTotals;
}

// ─── GET licenses/<id>/overview-invoice-ledger/ — Invoice Ledger tab ──────

export type InvoiceLedgerStatus = "Paid" | "Partial" | "Unpaid";

export interface InvoiceLedgerRow {
    invoice_number: string;
    invoice_date: string | null;
    /** Supplier for purchase rows, customer for sale rows. */
    company_name: string | null;
    /** `subtotal_amount`. */
    amount: number;
    /**
     * ALWAYS `null` — GST amount isn't tracked in this schema (`from_gst`/
     * `to_gst` are GSTIN registration numbers, not tax amounts). Render as
     * "Not tracked" in the GST column, never as `0` or blank.
     */
    gst: null;
    /** `total_amount`. */
    total: number;
    status: InvoiceLedgerStatus;
}

export interface LicenseOverviewInvoiceLedgerWarning {
    show_warning: boolean;
    message: string;
}

export interface LicenseOverviewInvoiceLedger {
    purchase: InvoiceLedgerRow[];
    sale: InvoiceLedgerRow[];
    /** Both keys are always present — `show_warning: false` is explicit,
     * never an omitted key. */
    warning: LicenseOverviewInvoiceLedgerWarning;
}

// ─── GET licenses/<id>/plan-utilization/ — Planning tab ──────────────────

export type LicenseOverviewNorm = "" | "E1" | "E5" | "E132";

export interface LicenseOverviewPlanRow {
    group_id: number;
    /** Rendered as the "Export Product" column. */
    description: string;
    hs_code: string | null;
    has_plan: boolean;
    /** Present only when `has_plan === true`. */
    original_quantity?: number;
    original_cif_fc?: number;
    /** Used for BOTH "Available Qty" and "Remaining Qty" columns — the
     * backend's `plan_status_for()` only has Original/Used/Remaining, no
     * distinct "Available" concept, so both columns intentionally show the
     * same number rather than inventing a 4th figure. */
    remaining_quantity?: number;
    /** Used for BOTH "Available CIF" and "Remaining CIF" columns — see
     * `remaining_quantity` above. */
    remaining_cif_fc?: number;
    used_quantity?: number;
    used_cif_fc?: number;
    /** Canonical planning quantities/status. Consumers must not re-derive these. */
    available_qty: number;
    planned_qty: number;
    allocated_qty: number;
    consumed_qty: number;
    remaining_qty: number;
    shortage_qty: number;
    excess_qty: number;
    feasible: boolean;
    status: "FEASIBLE" | "SHORT" | "UNPLANNED" | "BLOCKED_UNIT_MISMATCH";
}

export interface LicenseOverviewPlanUtilization {
    /** License-level SION norm — the SAME value for every row, not per-row. */
    norm: LicenseOverviewNorm;
    rows: LicenseOverviewPlanRow[];
}

// ─── GET/POST licenses/<id>/import-item-names/ — Items tab "Item Name" ────

export interface ImportItemNameItem {
    id: number;
    name: string;
}

export type ImportItemNameStatus = "MAPPED" | "NOT_MAPPED" | "CLEARED" | "MULTIPLE" | "CONFLICT";
export type ImportItemNameSource = "OVERRIDE" | "APPROVAL" | "DESCRIPTION_MAPPING" | "AUTO" | "OTHER";
/** `global` = approved decision for every import item with the same Description + HSN; `record` = this row only. */
export type ImportItemNameScope = "global" | "record";

/** Global Description + HSN approval covering a row (`USER_APPROVED_CLEAR` = deliberately no Item Name). */
export interface ImportItemNameApproval {
    id: number;
    status: "USER_APPROVED" | "USER_APPROVED_CLEAR";
    version: number;
    item: ImportItemNameItem | null;
    records: number;
    licences: number;
    updated_by: string | null;
    updated_on: string | null;
}

export interface ImportItemNameRow {
    import_item_id: number;
    serial_number: number | null;
    description: string | null;
    hs_code: string | null;
    unit: string | null;
    sion: string[];
    items: ImportItemNameItem[];
    status: ImportItemNameStatus;
    source: ImportItemNameSource | null;
    note: string;
    overridden: boolean;
    override: {
        item_ids: number[];
        previous_item_ids: number[];
        updated_by: string | null;
        updated_on: string | null;
        reason: string | null;
    } | null;
    description_mapping: {
        id: number;
        version: number;
        status: string;
        items: ImportItemNameItem[];
    } | null;
    approval?: ImportItemNameApproval | null;
}

export interface ImportItemNamesResponse {
    can_edit: boolean;
    rows: ImportItemNameRow[];
}

export interface ImportItemNameChange {
    import_item_id: number;
    item_id: number | null;
    expected_item_ids: number[];
    scope?: ImportItemNameScope;
    expected_approval_version?: number;
}

export interface ImportItemNameCombination {
    description: string;
    hsn_code: string | null;
}

export interface ImportItemNamePreview {
    import_item_id: number;
    combination: ImportItemNameCombination;
    records: number;
    licences: number;
    overridden: number;
    licence_numbers: string[];
    current_item_sets: Record<string, number>;
}

export interface ImportItemNamePropagation {
    import_item_id: number;
    combination: ImportItemNameCombination;
    records: number;
    licences: number;
    applied: number;
    unchanged: number;
    overridden: number;
    conflicts: number;
    conflict_licences: { id: number; license_number: string }[];
}

export interface ImportItemNameHistoryEvent {
    /** ISO timestamp (backend `time`). */
    time: string;
    user: string | null;
    action: string;
    previous_items: ImportItemNameItem[];
    new_items: ImportItemNameItem[];
    note: string;
}
