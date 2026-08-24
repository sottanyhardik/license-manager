import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import type { LicenseOverviewItemsResponse, LicenseOverviewItemRow } from "./types";

/**
 * Fetches `GET /licenses/<id>/overview-items/` for the Items tab. Only
 * fetched once that tab is activated.
 */
export function useLicenseOverviewItems(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<LicenseOverviewItemsResponse>({
        queryKey: licenseOverviewKeys.items(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/overview-items/`, {
                params: { include_canonical: 1 },
            });
            // Preserve the deployed array contract for legacy servers while
            // accepting the additive canonical rows/footer projection.
            return Array.isArray(data)
                ? { rows: data as LicenseOverviewItemRow[] }
                : data as LicenseOverviewItemsResponse;
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
