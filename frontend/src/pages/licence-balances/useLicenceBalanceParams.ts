/**
 * The only hook that reads or writes the `/licence-balances` URL.
 *
 * - Filter, page-size and page commits push one history entry. A commit that
 *   does not change the canonical URL is a no-op, so no extra request fires.
 * - Typed search is a local draft committed once, SEARCH_DEBOUNCE_MS after the
 *   last keystroke. A committed search resets the page to 1.
 * - A search change from the URL (Back/Forward) replaces the draft.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  SEARCH_DEBOUNCE_MS,
  parseListParams,
  serializeListParams,
  type BalanceListParams,
  type ExpiryFilter,
  type PageSize,
} from "./listParams";

export interface LicenceBalanceParams {
  params: BalanceListParams;
  searchDraft: string;
  setSearchDraft: (text: string) => void;
  setExpiry: (expiry: ExpiryFilter) => void;
  setPageSize: (pageSize: PageSize) => void;
  setPage: (page: number) => void;
}

export function useLicenceBalanceParams(): LicenceBalanceParams {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useMemo(() => parseListParams(searchParams), [searchParams]);

  // Callbacks and the debounce timer read the latest committed params through a ref,
  // so a deferred commit never applies a patch on top of a stale closure.
  const paramsRef = useRef(params);
  useEffect(() => {
    paramsRef.current = params;
  }, [params]);

  const commit = useCallback(
    (next: BalanceListParams) => {
      const nextQuery = serializeListParams(next).toString();
      if (nextQuery === serializeListParams(paramsRef.current).toString()) return;
      setSearchParams(new URLSearchParams(nextQuery));
    },
    [setSearchParams],
  );

  const [searchDraft, setSearchDraft] = useState(params.search);
  const [syncedSearch, setSyncedSearch] = useState(params.search);
  if (params.search !== syncedSearch) {
    // A search change that did not come from typing (URL navigation) replaces the draft.
    setSyncedSearch(params.search);
    setSearchDraft(params.search);
  }

  useEffect(() => {
    const next = searchDraft.trim();
    if (next === paramsRef.current.search) return;
    const timer = window.setTimeout(() => {
      commit({ ...paramsRef.current, search: next, page: 1 });
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchDraft, commit]);

  const setExpiry = useCallback(
    (expiry: ExpiryFilter) => commit({ ...paramsRef.current, expiry, page: 1 }),
    [commit],
  );
  const setPageSize = useCallback(
    (pageSize: PageSize) => commit({ ...paramsRef.current, pageSize, page: 1 }),
    [commit],
  );
  const setPage = useCallback((page: number) => commit({ ...paramsRef.current, page }), [commit]);

  return { params, searchDraft, setSearchDraft, setExpiry, setPageSize, setPage };
}
