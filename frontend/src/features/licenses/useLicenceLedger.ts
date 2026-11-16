import { useLicenseBalanceLedger } from "@/pages/license-balance/useLicenseBalanceLedger";

/**
 * The card's single per-licence detail query: `licenses/:id/balance-ledger/`
 * under the existing `licenseBalanceKeys.ledger(id)` key. The financial
 * summary, the Overview ledger section and the Reconciliation tab all read
 * this one cache entry, so expanding a card issues one request for all three,
 * and existing invalidations (recalculate, CIF switch, auto-plan) refresh it.
 */
export function useLicenceLedger(licenseId: number) {
    return useLicenseBalanceLedger(licenseId, false);
}
