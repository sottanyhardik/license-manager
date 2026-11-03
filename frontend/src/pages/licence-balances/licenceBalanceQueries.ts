/**
 * TanStack Query hooks for the licence balance API. Every key is built from
 * normalised params, so one committed URL state maps to one cache entry.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { toApiParams, type BalanceListParams } from "./listParams";
import type { BalanceListResponse, ItemDrilldown, ItemLedger, LicenceDetail } from "./types";

export const LICENCE_BALANCES_QUERY_ROOT = ["licence-balances"] as const;

/** Ledgers are reopened often while reviewing one item; a short freshness window avoids refetching on every open. */
const LEDGER_STALE_MS = 60_000;

/**
 * `withLegacy` asks the server for the legacy engine comparison (`legacy=1`). The server computes it once
 * per licence, so it is requested only while the legacy column is visible.
 */
export function useLicenceBalanceList(params: BalanceListParams, withLegacy = false) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "list", params, withLegacy],
    queryFn: async ({ signal }) => {
      const response = await api.get<BalanceListResponse>("licence-balances/", {
        params: { ...toApiParams(params), ...(withLegacy ? { legacy: "1" } : {}) },
        signal,
      });
      return response.data;
    },
    placeholderData: keepPreviousData,
  });
}

export function useLicenceBalanceDetail(licenceId: number | null) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "detail", licenceId],
    queryFn: async ({ signal }) => {
      if (licenceId === null) throw new Error("Licence id is missing");
      const response = await api.get<LicenceDetail>(`licence-balances/${licenceId}/`, { signal });
      return response.data;
    },
    enabled: licenceId !== null,
  });
}

/** Mounted only while a ledger is open, so the item endpoint is fetched lazily. */
export function useItemLedger(licenceId: number, itemId: number) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "item", licenceId, itemId],
    queryFn: async ({ signal }) => {
      const response = await api.get<ItemLedger>(`licence-balances/${licenceId}/items/${itemId}/`, { signal });
      return response.data;
    },
    staleTime: LEDGER_STALE_MS,
  });
}

/**
 * Drill-down for one item: the BOE debits, customer allotments and invoices behind its figures.
 * Fetched only while the item is expanded or its drawer is open.
 */
export function useItemDrilldown(licenceId: number, itemId: number, enabled: boolean) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "drilldown", licenceId, itemId],
    queryFn: async ({ signal }) => {
      const response = await api.get<ItemDrilldown>(`licence-balances/${licenceId}/items/${itemId}/drilldown/`, { signal });
      return response.data;
    },
    enabled,
    staleTime: LEDGER_STALE_MS,
  });
}
