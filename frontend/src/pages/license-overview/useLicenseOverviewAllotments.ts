import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import type { LicenseOverviewAllotmentRow } from "./types";

/**
 * Fetches `GET /licenses/<id>/overview-allotments/` for the Allotments tab.
 * Only fetched once that tab is activated.
 */
export function useLicenseOverviewAllotments(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<LicenseOverviewAllotmentRow[]>({
        queryKey: licenseOverviewKeys.allotments(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/overview-allotments/`);
            return data as LicenseOverviewAllotmentRow[];
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
