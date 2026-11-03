/**
 * Option sources for the licence filters, backed by the TanStack query cache.
 *
 * - Option lists are fetched on the first menu open and searched server-side
 *   (`search`, `page_size=50`). Purchase statuses are fetched WITHOUT an
 *   `is_active` filter so that inactive labels still resolve (marked inactive).
 * - Labels for selected values come from the cached option lists first. Only
 *   values with no cached label are fetched, once each, as a query.
 * - A value with no authoritative label is shown as "Unknown #<id>" (or
 *   "Unknown code <code>" for code-keyed masters). Labels are never invented.
 */
import { keepPreviousData, useQueries, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { useEffect, useMemo, useReducer, useState } from "react";
import api from "@/api/axios";
import type { LicenseListFilters, MultiField } from "./licenseListFilters";

export type OptionSourceKey =
  | "companies"
  | "ports"
  | "purchase-statuses"
  | "sion-classes"
  | "scheme-codes"
  | "notification-numbers";

interface OptionSourceConfig {
  path: string;
  labelField: string;
  /** Code-keyed masters are filtered by code; id-keyed masters by primary key. */
  valueField: "id" | "code";
}

const OPTION_SOURCES: Record<OptionSourceKey, OptionSourceConfig> = {
  companies: { path: "masters/companies/", labelField: "name", valueField: "id" },
  ports: { path: "masters/ports/", labelField: "name", valueField: "id" },
  "purchase-statuses": { path: "masters/purchase-statuses/", labelField: "label", valueField: "id" },
  "sion-classes": { path: "masters/sion-classes/", labelField: "norm_class", valueField: "id" },
  "scheme-codes": { path: "masters/scheme-codes/", labelField: "code", valueField: "code" },
  "notification-numbers": { path: "masters/notification-numbers/", labelField: "code", valueField: "code" },
};

/** Which option source backs each multi-select filter. */
export const FIELD_SOURCE: Record<MultiField, OptionSourceKey> = {
  exporter: "companies",
  exclude_exporter: "companies",
  port: "ports",
  exclude_port: "ports",
  purchase_status: "purchase-statuses",
  export_license__norm_class: "sion-classes",
  scheme_code: "scheme-codes",
  notification_number: "notification-numbers",
};

export const OPTION_STALE_TIME_MS = 5 * 60 * 1000;
const OPTION_PAGE_SIZE = 50;
const OPTION_SEARCH_DEBOUNCE_MS = 300;

export interface LicenseFilterOption {
  /** String form of the id (or the code). This is what the URL stores. */
  value: string;
  /** Raw label from the master record. */
  label: string;
  inactive: boolean;
}

export type OptionLookupStatus = "ok" | "loading" | "unknown";

export interface ResolvedLicenseOption {
  value: string;
  /** Display text, including the "(inactive)" suffix. */
  label: string;
  status: OptionLookupStatus;
}

type RawRecord = Record<string, unknown>;

function extractResults(data: unknown): RawRecord[] {
  if (Array.isArray(data)) return data as RawRecord[];
  if (data && typeof data === "object") {
    const results = (data as { results?: unknown }).results;
    if (Array.isArray(results)) return results as RawRecord[];
  }
  return [];
}

function normaliseRecord(source: OptionSourceKey, raw: RawRecord): LicenseFilterOption | null {
  const config = OPTION_SOURCES[source];
  const rawValue = raw[config.valueField];
  if (rawValue === undefined || rawValue === null) return null;
  const rawLabel = raw[config.labelField];
  const label = typeof rawLabel === "string" ? rawLabel.trim() : "";
  if (label === "") return null;
  return { value: String(rawValue), label, inactive: raw.is_active === false };
}

function normaliseList(source: OptionSourceKey, data: unknown): LicenseFilterOption[] {
  const options: LicenseFilterOption[] = [];
  for (const record of extractResults(data)) {
    const option = normaliseRecord(source, record);
    if (option) options.push(option);
  }
  return options;
}

export const optionListKey = (source: OptionSourceKey, search: string) =>
  ["licences", "options", source, "list", search] as const;

export const optionByIdKey = (source: OptionSourceKey, value: string) =>
  ["licences", "options", source, "id", value] as const;

function isOptionListKey(key: readonly unknown[]): key is readonly ["licences", "options", OptionSourceKey, "list", string] {
  return key[0] === "licences" && key[1] === "options" && key[3] === "list" && typeof key[2] === "string";
}

/** Fetches the option list for a source. Runs only once `enabled` (first menu open). */
export function useLicenseOptionSearch(source: OptionSourceKey, search: string, enabled: boolean) {
  const path = OPTION_SOURCES[source].path;
  return useQuery({
    queryKey: optionListKey(source, search),
    queryFn: async ({ signal }) => {
      const params: Record<string, string | number> = { page_size: OPTION_PAGE_SIZE };
      if (search !== "") params.search = search;
      const response = await api.get(path, { params, signal });
      return normaliseList(source, response.data);
    },
    enabled,
    staleTime: OPTION_STALE_TIME_MS,
    placeholderData: keepPreviousData,
  });
}

/**
 * Looks up one value outside the cached lists. Id-keyed masters use the detail
 * endpoint; code-keyed masters have none, so an exact-match search is used.
 * A 404 resolves to null (no authoritative record), not an error.
 */
async function fetchOptionById(
  source: OptionSourceKey,
  value: string,
  signal: AbortSignal,
): Promise<LicenseFilterOption | null> {
  const config = OPTION_SOURCES[source];
  try {
    if (config.valueField === "id") {
      const response = await api.get(`${config.path}${value}/`, { signal });
      const record = response.data;
      if (!record || typeof record !== "object") return null;
      return normaliseRecord(source, record as RawRecord);
    }
    const response = await api.get(config.path, {
      params: { search: value, page_size: OPTION_PAGE_SIZE },
      signal,
    });
    return normaliseList(source, response.data).find((option) => option.value === value) ?? null;
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 404) return null;
    throw error;
  }
}

/** Debounces a fast-changing value (used for server-side option search). */
export function useDebouncedValue<T>(value: T, delayMs: number = OPTION_SEARCH_DEBOUNCE_MS): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** Re-renders when option queries succeed, so labels resolve as lists arrive. */
function useOptionCacheSubscription(queryClient: QueryClient): void {
  const [, bump] = useReducer((n: number) => n + 1, 0);
  useEffect(
    () =>
      queryClient.getQueryCache().subscribe((event) => {
        if (event.type === "updated" && event.action.type === "success" && event.query.queryKey[0] === "licences") {
          if (event.query.queryKey[1] === "options") bump();
        }
      }),
    [queryClient],
  );
}

type ListIndex = Record<OptionSourceKey, Map<string, LicenseFilterOption>>;

function buildListIndex(queryClient: QueryClient): ListIndex {
  const index: ListIndex = {
    companies: new Map(),
    ports: new Map(),
    "purchase-statuses": new Map(),
    "sion-classes": new Map(),
    "scheme-codes": new Map(),
    "notification-numbers": new Map(),
  };
  for (const [key, data] of queryClient.getQueriesData<LicenseFilterOption[]>({ queryKey: ["licences", "options"] })) {
    if (!data || !isOptionListKey(key)) continue;
    const bucket = index[key[2]];
    for (const option of data) bucket.set(option.value, option);
  }
  return index;
}

interface LookupTarget {
  field: MultiField;
  source: OptionSourceKey;
  value: string;
}

function buildTargets(filters: LicenseListFilters): LookupTarget[] {
  const pairs: Array<[MultiField, readonly (number | string)[]]> = [
    ["exporter", filters.exporter],
    ["exclude_exporter", filters.exclude_exporter],
    ["port", filters.port],
    ["exclude_port", filters.exclude_port],
    ["purchase_status", filters.purchase_status],
    ["export_license__norm_class", filters.export_license__norm_class],
    ["scheme_code", filters.scheme_code],
    ["notification_number", filters.notification_number],
  ];
  const targets: LookupTarget[] = [];
  for (const [field, values] of pairs) {
    for (const value of values) {
      targets.push({ field, source: FIELD_SOURCE[field], value: String(value) });
    }
  }
  return targets;
}

function unknownLabel(field: MultiField, value: string): string {
  const keyedByCode = OPTION_SOURCES[FIELD_SOURCE[field]].valueField === "code";
  return keyedByCode ? `Unknown code ${value}` : `Unknown #${value}`;
}

export interface LicenseLabelLookup {
  /** Resolved option for a selected value. Never invents a label. */
  resolve: (field: MultiField, value: string) => ResolvedLicenseOption;
  /** Chip text for a selected value. */
  labelFor: (field: MultiField, value: string) => string;
}

/**
 * Resolves labels for every selected multi-select value. Cached list entries
 * win; only uncached values trigger a `masters/<source>/<id>/` (or exact-match
 * search) query, deduplicated by the query cache.
 */
export function useLicenseLabelLookup(filters: LicenseListFilters): LicenseLabelLookup {
  const queryClient = useQueryClient();
  useOptionCacheSubscription(queryClient);
  const targets = useMemo(() => buildTargets(filters), [filters]);
  const listIndex = buildListIndex(queryClient);
  // The purchase-status master is small and authoritative: it is loaded whole and
  // never fetched per id. An id missing from it is unknown, and a per-id request
  // would also be toasted as "Resource not found" by the global axios interceptor.
  const statusList = useLicenseOptionSearch("purchase-statuses", "", true);
  const statusListSettled = statusList.isSuccess || statusList.isError;
  const isAuthoritativeMiss = (target: LookupTarget) => target.source === "purchase-statuses" && statusListSettled;

  const queries = useQueries({
    queries: targets.map((target) => ({
      queryKey: optionByIdKey(target.source, target.value),
      queryFn: ({ signal }: { signal: AbortSignal }) => fetchOptionById(target.source, target.value, signal),
      enabled: listIndex[target.source].get(target.value) === undefined && target.source !== "purchase-statuses",
      staleTime: OPTION_STALE_TIME_MS,
      retry: false,
    })),
  });

  const resolved = new Map<string, ResolvedLicenseOption>();
  targets.forEach((target, index) => {
    const key = `${target.field}\u0000${target.value}`;
    const cached = listIndex[target.source].get(target.value);
    if (cached) {
      resolved.set(key, toResolved(cached, "ok"));
      return;
    }
    if (isAuthoritativeMiss(target)) {
      resolved.set(key, { value: target.value, label: unknownLabel(target.field, target.value), status: "unknown" });
      return;
    }
    const query = queries[index];
    if (query.data) {
      resolved.set(key, toResolved(query.data, "ok"));
    } else if (query.isError || query.data === null) {
      resolved.set(key, { value: target.value, label: unknownLabel(target.field, target.value), status: "unknown" });
    } else {
      resolved.set(key, { value: target.value, label: "Loading…", status: "loading" });
    }
  });

  const resolve = (field: MultiField, value: string): ResolvedLicenseOption =>
    resolved.get(`${field}\u0000${value}`) ?? {
      value,
      label: unknownLabel(field, value),
      status: "unknown",
    };

  return {
    resolve,
    labelFor: (field, value) => resolve(field, value).label,
  };
}

function toResolved(option: LicenseFilterOption, status: OptionLookupStatus): ResolvedLicenseOption {
  return {
    value: option.value,
    label: option.inactive ? `${option.label} (inactive)` : option.label,
    status,
  };
}
