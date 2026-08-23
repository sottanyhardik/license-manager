import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import type { LicenseOverviewSummary } from "./types";

/**
 * Query key factory for all 6 License Overview endpoints — mirrors
 * `licenseBalanceKeys` in `pages/license-balance/useLicenseBalanceLedger.ts`
 * one-for-one, just with one key per tab instead of one shared ledger key,
 * since each tab is fetched independently and lazily.
 */
export const licenseOverviewKeys = {
    summary: (licenseId: string | number) => ["license-overview-summary", String(licenseId)] as const,
    boes: (licenseId: string | number) => ["license-overview-boes", String(licenseId)] as const,
    allotments: (licenseId: string | number) => ["license-overview-allotments", String(licenseId)] as const,
    items: (licenseId: string | number) => ["license-overview-items", String(licenseId)] as const,
    invoiceLedger: (licenseId: string | number) => ["license-overview-invoice-ledger", String(licenseId)] as const,
    planning: (licenseId: string | number) => ["license-overview-planning", String(licenseId)] as const,
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
