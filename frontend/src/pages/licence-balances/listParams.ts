/**
 * URL <-> list state for `/licence-balances`. Pure functions so the
 * normalisation rules are unit-testable without a router.
 */

export const EXPIRY_FILTERS = ["all", "active", "expired"] as const;
export type ExpiryFilter = (typeof EXPIRY_FILTERS)[number];

export const PAGE_SIZES = [25, 50, 100] as const;
export type PageSize = (typeof PAGE_SIZES)[number];
export const DEFAULT_PAGE_SIZE: PageSize = 25;

export const SEARCH_DEBOUNCE_MS = 350;
const SEARCH_MAX_LENGTH = 200;

export interface BalanceListParams {
  search: string;
  expiry: ExpiryFilter;
  page: number;
  pageSize: PageSize;
}

export function parseListParams(searchParams: URLSearchParams): BalanceListParams {
  const search = (searchParams.get("search") ?? "").trim().slice(0, SEARCH_MAX_LENGTH);

  const expiryRaw = searchParams.get("expiry") ?? "all";
  const expiry = (EXPIRY_FILTERS as readonly string[]).includes(expiryRaw) ? (expiryRaw as ExpiryFilter) : "all";

  const pageRaw = Number(searchParams.get("page") ?? "1");
  const page = Number.isSafeInteger(pageRaw) && pageRaw >= 1 ? pageRaw : 1;

  const sizeRaw = Number(searchParams.get("page_size") ?? DEFAULT_PAGE_SIZE);
  const pageSize = (PAGE_SIZES as readonly number[]).includes(sizeRaw) ? (sizeRaw as PageSize) : DEFAULT_PAGE_SIZE;

  return { search, expiry, page, pageSize };
}

/** Writes only non-default values so the canonical URL stays short and stable. */
export function serializeListParams(params: BalanceListParams): URLSearchParams {
  const out = new URLSearchParams();
  if (params.search) out.set("search", params.search);
  if (params.expiry !== "all") out.set("expiry", params.expiry);
  if (params.page !== 1) out.set("page", String(params.page));
  if (params.pageSize !== DEFAULT_PAGE_SIZE) out.set("page_size", String(params.pageSize));
  return out;
}

/** Query parameters sent to the API. Every value is explicit except an empty search. */
export function toApiParams(params: BalanceListParams): Record<string, string | number> {
  return {
    page: params.page,
    page_size: params.pageSize,
    expiry: params.expiry,
    ...(params.search ? { search: params.search } : {}),
  };
}
