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
 *
 * `showHidden` is folded into the key as an extra element ONLY when true, so
 * `licenseBalanceKeys.ledger(licenseId)` (no second arg — every existing
 * invalidate call site) still produces the exact same 2-element key as
 * before and, via TanStack Query's default prefix-matching invalidation,
 * still invalidates BOTH the default and `show_hidden=true` query variants.
 */
export const licenseBalanceKeys = {
    ledger: (licenseId: string | number, showHidden?: boolean) =>
        (showHidden
            ? (["license-balance-ledger", String(licenseId), "show-hidden"] as const)
            : (["license-balance-ledger", String(licenseId)] as const)),
};

/**
 * Fetches the single source-of-truth dataset for the Licence Balance &
 * Financial Reconciliation Workspace — `GET /licenses/<id>/balance-ledger/`,
 * backed by `LicenseBalanceLedgerBuilder` (see `types.ts` for the exact
 * shape). Same `api.get` + return-data pattern as
 * `pages/reconciliation/useReconTabQuery.ts`.
 *
 * `showHidden` maps to the `?show_hidden=true` query param — when true, the
 * Customs Ledger section's `rows`/`summary` include previous-owner "hidden"
 * BOE debits (see `types.ts`'s `CustomsLedgerRow.is_hidden` docstring).
 * Every other section of the response is unaffected regardless of this flag.
 */
export function useLicenseBalanceLedger(licenseId: string | number | undefined, showHidden = false) {
    return useQuery<LicenseBalanceLedgerData>({
        queryKey: licenseBalanceKeys.ledger(licenseId ?? "", showHidden),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/balance-ledger/`, {
                params: showHidden ? { show_hidden: true } : undefined,
            });
            return data as LicenseBalanceLedgerData;
        },
        enabled: licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
