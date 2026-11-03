/**
 * List query for `/licenses`. One committed URL state maps to one query key,
 * so a stale response can never overwrite a newer one; the axios signal
 * cancels superseded requests.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import api from "@/api/axios";
import { serializeLicenseListSearch, toApiParams, type LicenseListState } from "./licenseListFilters";

/** One row of `GET licenses/`. Fields the list does not name stay `unknown`. */
export interface LicenseListItem {
  id: number;
  license_number: string;
  license_date: string | null;
  license_expiry_date: string | null;
  ledger_date: string | null;
  port_name: string | null;
  exporter_name: string | null;
  exporter_iec: string | null;
  get_norm_class: string | null;
  get_balance_cif: string | number | null;
  individual_item_cif_override?: boolean | null;
  latest_transfer: string | null;
  purchase_status_label: string | null;
  purchase_status_code: string | null;
  is_manually_planned: boolean;
  has_tl: boolean;
  has_copy: boolean;
  has_condition_sheet: boolean;
  /** Owner's name from the stored ownership record. Null when none is recorded. */
  current_owner_name: string | null;
  /** The stored status code (ACTIVE, EXPIRED, ...) and its display label, from the server. */
  licence_status_code: string;
  licence_status_label: string;
  /** Canonical available CIF as a decimal string: the figure the licence workspace shows. Null when not computed. */
  available_cif: string | null;
  [key: string]: unknown;
}

export interface LicenseListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  total_pages: number;
  current_page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
  results: LicenseListItem[];
}

/** Prefix for every licence list query. Invalidate this to refresh all pages of results. */
export const LICENSE_LIST_QUERY_ROOT = ["licences", "list"] as const;

export function useLicenseListQuery(state: LicenseListState) {
  const canonicalQuery = serializeLicenseListSearch(state);
  return useQuery({
    queryKey: [...LICENSE_LIST_QUERY_ROOT, canonicalQuery],
    queryFn: async ({ signal }) => {
      const response = await api.get<LicenseListResponse>("licenses/", {
        params: toApiParams(state),
        signal,
      });
      return response.data;
    },
    placeholderData: keepPreviousData,
  });
}
