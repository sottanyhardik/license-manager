import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
    fetchLicenceTransactionGroups,
    fetchLicenceTransactionRecords,
    type LicenceTransactionGroupsResponse,
    type LicenceTransactionParams,
    type LicenceTransactionRecordParams,
    type LicenceTransactionRecordsResponse,
} from "@/api/licenseApi";
import { qk } from "@/lib/queryKeys";

type LicenceId = string | number | undefined | null;

/**
 * Keys sit under `qk.licenses.detail(id)` (`["licenses","detail",id,...]`),
 * so `invalidateLicence(queryClient, id)` refetches them with every other
 * licence projection.
 */
export const licenseTransactionKeys = {
    groups: (licenseId: string | number, params: LicenceTransactionParams = {}) =>
        qk.licenses.sub(String(licenseId), "overview", "transactions", "groups", params),
    records: (licenseId: string | number, params: LicenceTransactionRecordParams) =>
        qk.licenses.sub(String(licenseId), "overview", "transactions", "records", params),
};

const hasId = (id: LicenceId): id is string | number => id !== undefined && id !== null && id !== "";

/**
 * `GET licenses/:id/overview-transactions/` — supplier groups (paged) with
 * backend-computed product summaries. Totals come from the backend only.
 */
export function useLicenseOverviewTransactions(
    licenseId: LicenceId,
    params: LicenceTransactionParams = {},
    isActive: boolean = true,
) {
    return useQuery<LicenceTransactionGroupsResponse>({
        queryKey: licenseTransactionKeys.groups(licenseId ?? "", params),
        queryFn: () => fetchLicenceTransactionGroups(licenseId as string | number, params),
        enabled: isActive && hasId(licenseId),
        placeholderData: keepPreviousData,
    });
}

/** Lazily loads the record lines of one supplier × product group. */
export function useLicenseOverviewTransactionRecords(
    licenseId: LicenceId,
    params: LicenceTransactionRecordParams | null,
    isActive: boolean = true,
) {
    return useQuery<LicenceTransactionRecordsResponse>({
        queryKey: licenseTransactionKeys.records(
            licenseId ?? "",
            params ?? { supplier_id: null, product_key: -1 },
        ),
        queryFn: () => fetchLicenceTransactionRecords(
            licenseId as string | number,
            params as LicenceTransactionRecordParams,
        ),
        enabled: isActive && hasId(licenseId) && params !== null,
        placeholderData: keepPreviousData,
    });
}
