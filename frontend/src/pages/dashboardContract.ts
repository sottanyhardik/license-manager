/**
 * Frozen, frontend-visible Dashboard API contract.  It is descriptive only:
 * optimizations may change server query implementation, never these inputs or
 * response semantics.
 */
export const dashboardApiContract = {
    endpoint: "dashboard/",
    method: "GET",
    queryParameters: [] as const,
    pagination: "none",
    ordering: "server-defined; preserve response order",
    response: {
        license_stats: ["total", "active", "expired", "null_dfia", "expiring_soon"],
        allotment_stats: ["total", "recent"],
        boe_stats: ["total", "pending_invoices", "recent"],
        expiring_licenses: ["license_number", "license_expiry_date", "balance_cif", "days_to_expiry"],
        boe_monthly_trend: ["month", "label", "count", "value"],
    },
} as const;
