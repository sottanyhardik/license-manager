import { useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import type { LicenseOverviewBoeRow } from "./types";

/**
 * Fetches `GET /licenses/<id>/overview-boes/` — one row per distinct BOE
 * linked to this license (not one row per ledger entry). Only fetched once
 * the BOEs tab is activated (`isActive`) — some licenses have 1000+ BOEs, so
 * this must never be part of an eager multi-tab fetch.
 */
export function useLicenseOverviewBoes(licenseId: string | number | undefined, isActive: boolean = true) {
    return useQuery<LicenseOverviewBoeRow[]>({
        queryKey: licenseOverviewKeys.boes(licenseId ?? ""),
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/overview-boes/`);
            return data as LicenseOverviewBoeRow[];
        },
        enabled: isActive && licenseId !== undefined && licenseId !== null && licenseId !== "",
    });
}
