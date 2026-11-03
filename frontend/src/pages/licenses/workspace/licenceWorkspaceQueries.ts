/**
 * Query hooks for the licence workspace. Keys follow the licence-balances
 * convention so the balance pages and the workspace share one cache entry.
 *
 *   ['licence-balances', 'detail', id]        balance summary + items
 *   ['licence-balances', 'transactions', id]  BOEs, allotments, invoices
 *   ['licence-balances', 'invoice-ledger', id] purchase and sale ledger (Invoices & Sales tab)
 *   ['licenses', 'header', id]                legacy header fields
 *   ['licenses', 'ownership', id]             current owner
 *
 * The workspace mounts only while a licence is open, so these run only then.
 * Each tab mounts its own transaction query, so a tab fetches only when it is selected.
 */
import { keepPreviousData, useQuery, type QueryClient } from "@tanstack/react-query";
import api from "@/api/axios";
import { LICENCE_BALANCES_QUERY_ROOT } from "@/pages/licence-balances/licenceBalanceQueries";
import { responseStatus } from "@/pages/licence-balances/errors";
import type { LicenceDetail } from "@/pages/licence-balances/types";
import type { InvoiceLedger, LicenceHeader, LicenceTransactions, SourceReconciliation } from "./types";

/** Re-opening a licence or switching tabs within this window reuses the cached response. */
const WORKSPACE_STALE_MS = 30_000;

/** A 4xx answer is not transient, so it is not retried. */
function retryTransient(failureCount: number, error: unknown): boolean {
  const status = responseStatus(error);
  if (status !== undefined && status >= 400 && status < 500) return false;
  return failureCount < 2;
}

/**
 * Balance summary and items. `placeholderData` keeps the previous licence on
 * screen while the next one loads, so callers must compare `licence_id` before
 * trusting the data.
 */
export function useWorkspaceDetail(licenceId: number) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "detail", licenceId],
    queryFn: async ({ signal }) => {
      const response = await api.get<LicenceDetail>(`licence-balances/${licenceId}/`, { signal });
      return response.data;
    },
    placeholderData: keepPreviousData,
    staleTime: WORKSPACE_STALE_MS,
    retry: retryTransient,
  });
}

export function useLicenceHeader(licenceId: number) {
  return useQuery({
    queryKey: ["licenses", "header", licenceId],
    queryFn: async ({ signal }) => {
      const response = await api.get<LicenceHeader>(`licenses/${licenceId}/`, { signal });
      return response.data;
    },
    placeholderData: keepPreviousData,
    staleTime: WORKSPACE_STALE_MS,
    retry: retryTransient,
  });
}

/** BOEs, allotments and invoices in one response. Reconciliation and Items & Balance share this cache entry. */
export function useLicenceTransactions(licenceId: number) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "transactions", licenceId],
    queryFn: async ({ signal }) => {
      const response = await api.get<LicenceTransactions>(`licence-balances/${licenceId}/transactions/`, { signal });
      return response.data;
    },
    staleTime: WORKSPACE_STALE_MS,
    retry: retryTransient,
  });
}

/**
 * Source-level reconciliation for the Reconciliation tab: each item's drawer totals against its item
 * figures, and the allocation records that need review. Computed by the backend from the same drill-downs.
 */
export function useSourceReconciliation(licenceId: number) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "source-reconciliation", licenceId],
    queryFn: async ({ signal }) => {
      const response = await api.get<SourceReconciliation>(`licence-balances/${licenceId}/source-reconciliation/`, { signal });
      return response.data;
    },
    staleTime: WORKSPACE_STALE_MS,
    retry: retryTransient,
  });
}

/**
 * Purchase and sale ledger for the Invoices & Sales tab. Totals and rows come
 * from the backend; the frontend never sums or converts these amounts.
 */
export function useLicenceInvoiceLedger(licenceId: number) {
  return useQuery({
    queryKey: [...LICENCE_BALANCES_QUERY_ROOT, "invoice-ledger", licenceId],
    queryFn: async ({ signal }) => {
      const response = await api.get<InvoiceLedger>(`licence-balances/${licenceId}/invoice-ledger/`, { signal });
      return response.data;
    },
    staleTime: WORKSPACE_STALE_MS,
    retry: retryTransient,
  });
}

/**
 * Invalidates the workspace data for one licence. The list queries are left
 * alone, and so are other licences' detail and item caches.
 */
export function refreshLicenceWorkspace(queryClient: QueryClient, licenceId: number) {
  return Promise.all([
    queryClient.invalidateQueries({
      queryKey: LICENCE_BALANCES_QUERY_ROOT,
      predicate: (query) => query.queryKey[1] !== "list" && query.queryKey[2] === licenceId,
    }),
    queryClient.invalidateQueries({ queryKey: ["licenses", "header", licenceId] }),
    queryClient.invalidateQueries({ queryKey: ["licenses", "ownership", licenceId] }),
  ]);
}
