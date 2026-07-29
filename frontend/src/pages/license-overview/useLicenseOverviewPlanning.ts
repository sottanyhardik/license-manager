import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import type { LicenseOverviewPlanUtilization } from "./types";

/**
 * Fetches `GET /licenses/<id>/plan-utilization/` for the Planning tab —
 * a thin action wrapping `plan_utilization_rows(license_obj)` verbatim, so
 * this avoids paying for the full license-detail payload on every Planning
 * tab activation. Only fetched once that tab is activated.
 */
export function useLicenseOverviewPlanning(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<LicenseOverviewPlanUtilization>({
        queryKey: licenseOverviewKeys.planning(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/plan-utilization/`);
            return data as LicenseOverviewPlanUtilization;
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
