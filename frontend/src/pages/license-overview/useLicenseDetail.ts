import { useQuery } from "@tanstack/react-query";
import { fetchLicense } from "@/api/licenseApi";
import { qk } from "@/lib/queryKeys";

type Id = string | number | undefined;

export const licenseDetailKey = (licenseId: string | number) => qk.licenses.detail(String(licenseId));

/** Query options for the single shared `GET licenses/:id/` entry. */
export const licenseDetailQuery = (licenseId: string | number) => ({
    queryKey: licenseDetailKey(licenseId),
    queryFn: () => fetchLicense<Record<string, any>>(licenseId),
});

/**
 * The one shared licence-detail query (`licenses/:id/`). Documents, the SION
 * norm, the customs ledger and PlanningEditor all read this cache entry.
 * `select` projects without changing the cached payload.
 */
export function useLicenseDetail<T = Record<string, any>>(
    licenseId: Id,
    select?: (data: Record<string, any>) => T,
    enabled: boolean = true,
) {
    const has = licenseId !== undefined && licenseId !== null && licenseId !== "";
    return useQuery({
        ...licenseDetailQuery(licenseId ?? ""),
        select,
        enabled: enabled && has,
    });
}
