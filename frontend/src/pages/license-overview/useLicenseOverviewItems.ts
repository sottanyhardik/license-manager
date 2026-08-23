import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import type { LicenseOverviewItemRow } from "./types";

/**
 * Fetches `GET /licenses/<id>/overview-items/` for the Items tab. Only
 * fetched once that tab is activated.
 */
export function useLicenseOverviewItems(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<LicenseOverviewItemRow[]>({
        queryKey: licenseOverviewKeys.items(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/overview-items/`);
            return data as LicenseOverviewItemRow[];
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
