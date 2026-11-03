/**
 * The ONLY hook that reads or writes the licence list URL.
 *
 * - Reads: `useSearchParams` -> `parseLicenseListSearch` (never throws).
 * - Filter commits and page changes PUSH a history entry, so Back restores the
 *   previous state. A commit that does not change the canonical URL is a no-op.
 * - A malformed or non-canonical URL is normalised with REPLACE (no new entry).
 * - The open licence workspace is not in the URL. The list page closes it when the
 *   filters or search change, and a reload starts with none open.
 * - Typed search is held as a draft and committed once, 350 ms after the last
 *   keystroke (or immediately on Enter).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import {
  normaliseSearch,
  parseLicenseListSearch,
  serializeLicenseListSearch,
  withFilters,
  baselineFilters,
  type LicenseListFilters,
  type LicenseListPageSize,
  type LicenseListState,
} from "./licenseListFilters";

export const SEARCH_COMMIT_DELAY_MS = 350;

export interface LicenseListUrlState {
  /** Parsed, normalised state for the current URL. */
  state: LicenseListState;
  /** Notes about values dropped from the URL while parsing. */
  warnings: string[];
  /** Search text as typed. Committed to the URL after a pause. */
  searchDraft: string;
  setSearchDraft: (text: string) => void;
  /** Commits the search draft immediately (used on Enter). */
  commitSearchNow: () => void;
  /** Applies an update to the latest state. Pushes only when the canonical URL changes. */
  commit: (update: (current: LicenseListState) => LicenseListState) => void;
  /** Patches filters. Resets page to 1 and pushes a history entry. */
  setFilters: (patch: Partial<LicenseListFilters>) => void;
  /** Changes page. Keeps filters. Pushes a history entry. */
  setPage: (page: number) => void;
  /** Changes page size. Keeps filters and resets page to 1. */
  setPageSize: (pageSize: LicenseListPageSize) => void;
  /** Returns to the baseline view (not an empty URL) and resets page to 1. */
  clearToBaseline: () => void;
}

export function useLicenseListState(): LicenseListUrlState {
  const [searchParams, setSearchParams] = useSearchParams();
  const raw = searchParams.toString();
  const parsed = useMemo(() => parseLicenseListSearch(raw), [raw]);
  const { state, warnings } = parsed;
  const urlSearch = state.filters.search;
  const targetQuery = serializeLicenseListSearch(state);

  // The latest state is read by deferred callers (debounced search, numeric
  // commits) so they never apply a patch on top of a stale closure.
  const latestRef = useRef(state);
  latestRef.current = state;
  const setParamsRef = useRef(setSearchParams);
  setParamsRef.current = setSearchParams;

  const commit = useCallback((update: (current: LicenseListState) => LicenseListState) => {
    const current = latestRef.current;
    const next = update(current);
    const nextQuery = serializeLicenseListSearch(next);
    if (nextQuery === serializeLicenseListSearch(current)) return;
    latestRef.current = next;
    setParamsRef.current(nextQuery);
  }, []);

  // Normalise a malformed or non-canonical URL in place (REPLACE, no new entry).
  useEffect(() => {
    if (targetQuery === raw) return;
    setParamsRef.current(new URLSearchParams(targetQuery), { replace: true });
    if (warnings.length > 0) {
      toast.message("Some filter values in this link were ignored", {
        description: warnings.slice(0, 3).join(" "),
      });
    }
  }, [targetQuery, raw, warnings]);

  // Search draft: follows the URL when the URL changes from outside (Back,
  // Forward, a chip removal) and is committed once after a pause while typing.
  const [draft, setDraft] = useState(urlSearch);
  const [syncedSearch, setSyncedSearch] = useState(urlSearch);
  if (syncedSearch !== urlSearch) {
    setSyncedSearch(urlSearch);
    setDraft(urlSearch);
  }

  useEffect(() => {
    if (normaliseSearch(draft) === urlSearch) return;
    const timer = setTimeout(() => {
      commit((current) => withFilters(current, { search: draft }));
    }, SEARCH_COMMIT_DELAY_MS);
    return () => clearTimeout(timer);
  }, [draft, urlSearch, commit]);

  const commitSearchNow = useCallback(() => {
    if (normaliseSearch(draft) === urlSearch) return;
    commit((current) => withFilters(current, { search: draft }));
  }, [draft, urlSearch, commit]);

  const setFilters = useCallback(
    (patch: Partial<LicenseListFilters>) => commit((current) => withFilters(current, patch)),
    [commit],
  );

  const setPage = useCallback((page: number) => commit((current) => ({ ...current, page })), [commit]);

  const setPageSize = useCallback(
    (pageSize: LicenseListPageSize) => commit((current) => ({ ...current, pageSize, page: 1 })),
    [commit],
  );

  const clearToBaseline = useCallback(
    () => commit((current) => withFilters(current, baselineFilters())),
    [commit],
  );

  return {
    state,
    warnings,
    searchDraft: draft,
    setSearchDraft: setDraft,
    commitSearchNow,
    commit,
    setFilters,
    setPage,
    setPageSize,
    clearToBaseline,
  };
}
