/**
 * The ONLY place dashboard URLs are built.
 *
 * Licence-list parameters verified against the backend (2026-11-02):
 *   backend/apps/license/views/license.py  `LicenseDetailsViewSet`
 *   - `exporter`                  FK filter from `filter_config` (company scope; comma-separated ids)
 *   - `license_expiry_date_from`  generic `date_range` filter (`apply_advanced_filters`)
 *   - `license_expiry_date_to`    generic `date_range` filter
 *   - `is_active`                 `true` / `false`, from the `LicenseDetailsViewSet` override
 *   - `is_expired`                date-based override (`expiry < today`). When omitted it
 *                                 defaults to `False`, so every licence link sets it explicitly.
 *   - `is_null`                   override on live balance < 200 (not the stored flag, < 500)
 *   - `search`                    EnhancedSearchFilter over licence_number, file_number, exporter name
 *
 * NOT accepted by the licence list, so never emitted here: `company_id`,
 * `status`. The filterset that declares them is not in the viewset's
 * `filter_backends`.
 *
 * Unverified targets (no declared filter known): `/bill-of-entries` and
 * `/trades` are linked without filters.
 */
export const LICENCE_LIST_FILTERS = [
    "exporter",
    "is_active",
    "license_expiry_date_from",
    "license_expiry_date_to",
    "is_expired",
    "is_null",
    "search",
] as const;

export type LicenceListFilter = (typeof LICENCE_LIST_FILTERS)[number];

type LinkParams = Partial<Record<LicenceListFilter, string | number | boolean>> & { is_expired?: boolean | "all" };

function withQuery(path: string, params: Record<string, string | number | boolean | undefined>): string {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value === undefined || value === "") continue;
        search.set(key, String(value));
    }
    const query = search.toString();
    return query ? `${path}?${query}` : path;
}

/** Adds days to an ISO `YYYY-MM-DD` date. Pure calendar arithmetic, UTC-safe. */
export function addDays(isoDate: string, days: number): string {
    const date = new Date(`${isoDate}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
}

export function licenceList(params: LinkParams = {}, companyId?: number | null): string {
    return withQuery("/licenses", {
        exporter: companyId ?? params.exporter,
        is_active: params.is_active,
        license_expiry_date_from: params.license_expiry_date_from,
        license_expiry_date_to: params.license_expiry_date_to,
        is_expired: params.is_expired,
        is_null: params.is_null,
        search: params.search,
    });
}

/** Licences expiring between `asOf + fromDays` and `asOf + toDays`, not expired. */
export function expiryWindow(asOf: string, fromDays: number, toDays: number | null, companyId?: number | null): string {
    return licenceList(
        {
            license_expiry_date_from: addDays(asOf, fromDays),
            ...(toDays === null ? {} : { license_expiry_date_to: addDays(asOf, toDays) }),
            is_expired: false,
        },
        companyId,
    );
}

export const licenceEditPath = (licenceId: number) => `/licenses/${licenceId}/edit`;
/** Licence workspace: balances, items, transactions and reconciliation. Opens inline on `/licenses?licence=ID`. */
export const licenceOverviewPath = (licenceId: number) => `/licenses?licence=${licenceId}`;

/** Active licences: `is_active=true` and not expired, the same predicate as the count. */
export function activeLicencesTarget(companyId?: number | null): string {
    return licenceList({ is_active: true, is_expired: false }, companyId);
}
export const allotmentPath = (allotmentId: number) => `/allotments/${allotmentId}/allocate`;
export const boeEditPath = (boeId: number) => `/bill-of-entries/${boeId}/edit`;
export const tradeEditPath = (tradeId: number) => `/trades/${tradeId}/edit`;

export const LIST_PATHS = {
    licences: "/licenses",
    allotments: "/allotments",
    boes: "/bill-of-entries",
    trades: "/trades",
} as const;

export const QUICK_ACTION_PATHS = {
    newLicence: "/licenses/create",
    newAllotment: "/allotments/create",
    newBoe: "/bill-of-entries/create",
    newInvoice: "/trades/create",
    reconciliation: "/reconciliation",
    reports: "/reports/item-report",
} as const;

/** In-page anchors for sections that have no list page of their own. */
export const SECTION_ANCHORS = {
    financial: "#dashboard-financial",
    expiring: "#dashboard-expiring-licences",
    c969: "#dashboard-c969",
    attention: "#dashboard-attention",
} as const;

/**
 * Click-through for each attention key. Keys the page does not know yet return
 * `null` and are rendered without a link (never with a guessed URL).
 * `is_expired=true` is explicit because the licence list's default is `false`.
 */
export function attentionTarget(key: string, companyId?: number | null): string | null {
    switch (key) {
        // These three open the per-licence lists inside the attention centre.
        case "expired_with_balance":
        case "stale_expiry_flags":
        case "over_utilised":
            return SECTION_ANCHORS.attention;
        case "expiring_7d_usable":
            return SECTION_ANCHORS.expiring;
        case "missing_dgft":
            // `is_expired=all` lifts the list default so expired licences are included, as in the count.
            return licenceList({ is_null: true, is_expired: "all" }, companyId);
        case "c969_link_review":
            return SECTION_ANCHORS.c969;
        case "boe_pending_licence_mapping":
        case "boe_without_invoice_no":
            return "/bill-of-entries";
        case "invoices_outstanding":
            return "/trades";
        default:
            return null;
    }
}

/** Click-through for one expiry band of the distribution chart. */
export function bandTarget(key: string, asOf: string, companyId?: number | null): string | null {
    switch (key) {
        case "expired":
            return licenceList({ is_expired: true }, companyId);
        case "d0_7":
            return expiryWindow(asOf, 0, 7, companyId);
        case "d8_15":
            return expiryWindow(asOf, 8, 15, companyId);
        case "d16_30":
            return expiryWindow(asOf, 16, 30, companyId);
        case "d31_60":
            return expiryWindow(asOf, 31, 60, companyId);
        case "over_60":
            return expiryWindow(asOf, 61, null, companyId);
        default:
            // `inactive` (is_active=false) and `no_expiry` cannot be expressed with the declared filters.
            return null;
    }
}

/** Click-through for the cumulative "within N days" chips. */
export function withinTarget(days: 7 | 15 | 30 | 60, asOf: string, companyId?: number | null): string {
    return expiryWindow(asOf, 0, days, companyId);
}
