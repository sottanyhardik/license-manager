import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { qk } from "@/lib/queryKeys";
import type { LicenseOverviewSummary } from "./types";

/**
 * Query key factory for all 6 License Overview endpoints — mirrors
 * `licenseBalanceKeys` in `pages/license-balance/useLicenseBalanceLedger.ts`
 * one-for-one, just with one key per tab instead of one shared ledger key,
 * since each tab is fetched independently and lazily.
 */
export const licenseOverviewKeys = {
    summary: (licenseId: string | number) => qk.licenses.overview(String(licenseId), "summary"),
    boes: (licenseId: string | number) => qk.licenses.overview(String(licenseId), "boes"),
    allotments: (licenseId: string | number) => qk.licenses.overview(String(licenseId), "allotments"),
    items: (licenseId: string | number) => qk.licenses.overview(String(licenseId), "items"),
    invoiceLedger: (licenseId: string | number) => qk.licenses.overview(String(licenseId), "invoice-ledger"),
    /**
     * Was a dead key (never queried). Now the shared licence-detail key
     * (`licenses/:id/`, the data PlanningEditor and the SION/documents readers
     * use), so existing `planning` invalidations refetch real queries.
     */
    planning: (licenseId: string | number) => qk.licenses.detail(String(licenseId)),
};

/**
 * Fetches `GET /licenses/<id>/overview-summary/` — the Overview tab's header
 * fields + 9-card summary. `enabled` additionally gates on `isActive` so this
 * (like the other 5 overview hooks) is not fetched until its tab is opened.
 */
export function useLicenseOverviewSummary(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<LicenseOverviewSummary>({
        queryKey: licenseOverviewKeys.summary(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/overview-summary/`);
            return data as LicenseOverviewSummary;
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
