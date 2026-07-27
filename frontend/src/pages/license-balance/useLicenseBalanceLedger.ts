import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import type { LicenseBalanceLedgerData } from "./types";

/**
 * Query key factory — mirrors `reconKeys` in
 * `pages/reconciliation/reconciliationHelpers.ts`. All write actions in this
 * workspace invalidate `licenseBalanceKeys.ledger(licenseId)` after a
 * successful POST rather than using `useMutation` (matches the established
 * convention in `pages/reconciliation/MissingBoeTab.tsx` /
 * `DuplicateBoesTab.tsx`: plain `api.post(...)` + toast + invalidate).
 */
export const licenseBalanceKeys = {
    ledger: (licenseId: string | number) => ["license-balance-ledger", String(licenseId)] as const,
};

/**
 * Fetches the single source-of-truth dataset for the Licence Balance &
 * Financial Reconciliation Workspace — `GET /licenses/<id>/balance-ledger/`,
 * backed by `LicenseBalanceLedgerBuilder` (see `types.ts` for the exact
 * shape). Same `api.get` + return-data pattern as
 * `pages/reconciliation/useReconTabQuery.ts`.
 */
export function useLicenseBalanceLedger(licenseId: string | number | undefined) {
    return useQuery<LicenseBalanceLedgerData>({
        queryKey: licenseBalanceKeys.ledger(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/balance-ledger/`);
            return data as LicenseBalanceLedgerData;
        },
        enabled: licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
