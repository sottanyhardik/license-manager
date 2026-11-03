/**
 * Frozen, frontend-visible Dashboard API contract (version 3).
 *
 * Source of truth: docs/09-module-implementation/dashboard.md §4. Backend and
 * frontend implement the same shape. A change requires editing that document
 * first and bumping `version`.
 *
 * Money values are decimal strings with 2 dp. The frontend formats them and
 * never recomputes them. `null` means "not available"; it is never shown as 0.
 */
export const dashboardApiContract = {
    version: 3,
    endpoint: "dashboard/",
    method: "GET",
    queryParameters: ["company_id", "date_from", "date_to", "refresh"] as const,
    sections: [
        "meta",
        "licence_portfolio",
        "financial",
        "expiring_licences",
        "licence_exceptions",
        "c969_link_review",
        "allotment_activity",
        "boe_activity",
        "invoice_activity",
        "attention",
        "not_monitored",
    ] as const,
} as const;

export type DashboardQueryParams = {
    company_id?: number;
    date_from?: string;
    date_to?: string;
    refresh?: "1";
};

/** Returned in place of a section whose backend computation failed. */
export type SectionError = { error: string };

export type DashboardMeta = {
    generated_at: string;
    as_of: string;
    as_of_timezone: string;
    cached: boolean;
    scope: {
        company_id: number | null;
        company_name: string | null;
        date_from: string | null;
        date_to: string | null;
    };
    units: { cif: "FC"; invoice: "INR" };
};

export type ExpiryBandKey =
    | "expired"
    | "d0_7"
    | "d8_15"
    | "d16_30"
    | "d31_60"
    | "over_60"
    | "inactive"
    | "no_expiry";

export type LicencePortfolio = {
    total: number;
    active: number;
    expired: number;
    missing_dgft: number;
    expiring_usable_30d: number;
    stale_expiry_flags: number;
    bands: { key: ExpiryBandKey; count: number }[];
    within: { "7": number; "15": number; "30": number; "60": number };
};

export type FinancialBridge = {
    authorized: string;
    previous_owner_utilisation: string;
    purchased_cif: string;
    sale_utilisation: string;
    boe_utilisation: string;
    reserved: string;
    rounding: string;
    raw_available: string;
    over_utilisation_floor: string;
    available: string;
};

export type Financial = {
    engine: "financial_available_balance";
    authorized_cif: string;
    utilized_cif: string;
    reserved_cif: string;
    available_cif: string;
    expired_available_cif: string;
    committed_pct: number | null;
    licences_in_scope: number;
    over_utilised_licences: number;
    bridge: FinancialBridge;
};

export type ExpiringLicence = {
    id: number;
    license_number: string;
    license_expiry_date: string;
    days_to_expiry: number;
    balance_cif: string;
    sion_norms: string[];
};

/** A licence behind a verified exception. Capped at 25 per list, sorted by licence number. */
export type LicenceRef = { id: number; license_number: string };

export type LicenceExceptions = {
    over_utilised: LicenceRef[];
    expired_with_balance: LicenceRef[];
    stale_expiry_flags: LicenceRef[];
};

export type C969LinkReviewRow = {
    import_item_id: number;
    licence_id: number;
    licence_number: string;
    description: string;
    saved_items: string[];
    expected_item: string;
};

export type C969LinkReview = {
    count: number;
    rows: C969LinkReviewRow[];
    error?: string;
};

export type AllotmentStatus = "open" | "partly_consumed" | "consumed" | "boe_linked";

/**
 * One allotment. Every figure is an engine annotation summed over its items, except `not_reserved_cif`.
 * That value is `allotted - consumed - reserved`: the CIF the engine neither reserves nor counts as
 * consumed (ISS-008 for a BOE-linked allotment). Quantities are 2-dp strings.
 */
export type AllotmentActivityRow = {
    id: number;
    /** Display reference, `#<id>`. */
    reference: string;
    item_name: string;
    company_name: string | null;
    created_on: string;
    /** Distinct licences behind the allotment's items, capped at 5. */
    licences: LicenceRef[];
    licence_count: number;
    /** The quantity the allotment asked for (`required_quantity`). */
    original_quantity: string;
    /** The quantity placed on licence items (sum of item quantities). */
    allocated_quantity: string;
    /** Requested but not yet placed on any licence item: original minus placed, never negative. */
    unplaced_quantity: string;
    /** CIF placed on licence items. */
    allotted_cif: string;
    /** CIF matched by BOE allocation records (capped per item at the item CIF). */
    consumed_cif: string;
    /** CIF still reserved by the engine. Zero for any BOE-linked allotment (ISS-008). */
    reserved_cif: string;
    not_reserved_cif: string;
    /** Quantity still reserved by the engine. */
    remaining_quantity: string;
    /** BOEs linked to this allotment, each counted once. */
    boe_count: number;
    status: AllotmentStatus;
};

export type AllotmentActivity = {
    total: number;
    counts: Record<AllotmentStatus, number>;
    /** Sums over every allotment in scope, not only the recent rows. */
    totals: {
        allotted_cif: string;
        consumed_cif: string;
        reserved_cif: string;
        not_reserved_cif: string;
    };
    recent: AllotmentActivityRow[];
};

export type BoeMappingStatus = "mapped" | "pending_licence_mapping";

export type BoeRow = {
    id: number;
    bill_of_entry_number: string;
    bill_of_entry_date: string | null;
    company_name: string | null;
    invoice_no: string | null;
    modified_on: string;
    allotment_links: number;
    licence_items: number;
    mapping_status: BoeMappingStatus;
};

export type BoeActivity = {
    total: number;
    linked_to_allotment: number;
    direct: number;
    pending_licence_mapping: number;
    without_invoice_no: number;
    recent: BoeRow[];
    /** Up to 10 BOEs with no licence rows, same shape as `recent`. */
    pending_mapping: BoeRow[];
    recently_modified: BoeRow[];
    /** Returned for compatibility. Not rendered by V1. */
    monthly_trend: { month: string; count: number }[];
};

export type InvoiceStatus = "paid" | "partially_paid" | "unpaid";

export type InvoiceActivity = {
    total: number;
    paid: number;
    partially_paid: number;
    unpaid: number;
    open: number;
    total_amount_inr: string;
    paid_inr: string;
    outstanding_inr: string;
    by_direction: {
        sale: { total: number; outstanding_inr: string };
        purchase: { total: number; outstanding_inr: string };
    };
    not_tracked: ("draft" | "pending" | "confirmed" | "posted")[];
    recent: {
        id: number;
        invoice_number: string;
        invoice_date: string;
        direction: "sale" | "purchase";
        party_name: string | null;
        total_amount_inr: string;
        outstanding_inr: string;
        status: InvoiceStatus;
    }[];
};

export type AttentionSeverity = "high" | "medium" | "low";

export type AttentionKey =
    | "expired_with_balance"
    | "expiring_7d_usable"
    | "missing_dgft"
    | "over_utilised"
    | "stale_expiry_flags"
    | "c969_link_review"
    | "boe_pending_licence_mapping"
    | "boe_without_invoice_no"
    | "invoices_outstanding";

export type AttentionItem = {
    key: AttentionKey;
    count: number;
    severity: AttentionSeverity;
    section: string;
};

export type NotMonitoredItem = { key: string; reason: string };

/**
 * Full v3 payload. Every section is optional: it is absent when the caller's
 * roles do not grant it, and is `SectionError` when its computation failed.
 */
export type DashboardResponse = {
    meta: DashboardMeta;
    licence_portfolio?: LicencePortfolio | SectionError;
    financial?: Financial | SectionError;
    expiring_licences?: ExpiringLicence[] | SectionError;
    licence_exceptions?: LicenceExceptions | SectionError;
    c969_link_review?: C969LinkReview | SectionError;
    allotment_activity?: AllotmentActivity | SectionError;
    boe_activity?: BoeActivity | SectionError;
    invoice_activity?: InvoiceActivity | SectionError;
    attention: AttentionItem[];
    not_monitored: NotMonitoredItem[];
};

/** Roles that receive each section. Mirrors the backend role gates exactly. */
export const DASHBOARD_SECTION_ROLES = {
    licence: ["LICENSE_MANAGER", "LICENSE_VIEWER", "REPORT_VIEWER"],
    allotment: ["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER", "REPORT_VIEWER"],
    boe: ["BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "REPORT_VIEWER"],
    invoice: ["TRADE_MANAGER", "TRADE_VIEWER", "ACCOUNT_ACCESS", "REPORT_VIEWER"],
} as const;

/**
 * A failed section is exactly `{ error }`. `c969_link_review` may carry an
 * `error` next to its `count` and `rows`; that case is handled by the caller.
 */
export function isSectionError(value: unknown): value is SectionError {
    return typeof value === "object" && value !== null && Object.keys(value).join(",") === "error"
        && typeof (value as { error: unknown }).error === "string";
}
