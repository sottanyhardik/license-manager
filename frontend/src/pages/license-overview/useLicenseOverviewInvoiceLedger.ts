import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import type { LicenseOverviewInvoiceLedger } from "./types";

/**
 * Fetches `GET /licenses/<id>/overview-invoice-ledger/` for the Invoice
 * Ledger tab (Purchase/Sale tables + the conditional warning banner). Only
 * fetched once that tab is activated.
 */
export function useLicenseOverviewInvoiceLedger(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<LicenseOverviewInvoiceLedger>({
        queryKey: licenseOverviewKeys.invoiceLedger(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/overview-invoice-ledger/`);
            return data as LicenseOverviewInvoiceLedger;
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
