import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery, type QueryKey } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import api from "@/api/axios";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import {
    clampPageSize,
    normalizeList,
    parseListParams,
    toQuery,
    writeListParams,
    type FilterValue,
    type ListParams,
    type ListResult,
} from "@/lib/listContract";

export type ListFetcher<T> = (p: ListParams, signal: AbortSignal) => Promise<ListResult<T>>;

/** GET `endpoint` with the list query string; forwards the AbortSignal to axios. */
export function fetchList<T>(endpoint: string, maxPageSize?: number): ListFetcher<T> {
    return async (p, signal) => {
        const res = await api.get(endpoint, { params: toQuery(p, maxPageSize), signal });
        return normalizeList<T>(res.data, p);
    };
}

export interface UseListQueryOptions<T> {
    /** From the qk factory, e.g. `qk.licenses.list`. */
    key: (p: ListParams) => QueryKey;
    /** Either a custom fetcher, or an `endpoint` (GET via shared axios instance). */
    fetcher?: ListFetcher<T>;
    endpoint?: string;
    defaults?: Partial<Omit<ListParams, "page">>;
    /** Allow-list of URL params owned by this list. */
    filterKeys: string[];
    /** Subset of filterKeys holding arrays; comma-split on parse so they round-trip via the URL. */
    multiKeys?: string[];
    urlPrefix?: string;
    /** Default and hard cap: 200. */
    maxPageSize?: number;
    enabled?: boolean;
}

export interface UseListQueryResult<T> {
    params: ListParams;
    result: ListResult<T> | undefined;
    status: "loading" | "error" | "success";
    isFetching: boolean;
    error: unknown;
    refetch: () => void;
    setPage: (n: number) => void;
    setPageSize: (n: number) => void;
    /** Debounced 300ms internally. */
    setSearch: (s: string) => void;
    setFilters: (f: Record<string, FilterValue>) => void;
    setOrdering: (o: string | undefined) => void;
    reset: () => void;
}

export function useListQuery<T>(opts: UseListQueryOptions<T>): UseListQueryResult<T> {
    const { key, fetcher, endpoint, defaults, filterKeys, multiKeys, urlPrefix, maxPageSize, enabled = true } = opts;
    const [sp, setSp] = useSearchParams();

    // Options are read through a ref so callers can pass inline literals.
    const optsRef = useRef({ defaults, filterKeys, multiKeys, urlPrefix, maxPageSize });
    optsRef.current = { defaults, filterKeys, multiKeys, urlPrefix, maxPageSize };
    const spKey = sp.toString();
    const filterKeysId = filterKeys.join("|");
    const multiKeysId = (multiKeys ?? []).join("|");
    const defaultsId = JSON.stringify(defaults ?? {});
    const params = useMemo(
        () => parseListParams(new URLSearchParams(spKey), optsRef.current),
        // eslint-disable-next-line react-hooks/exhaustive-deps
        [spKey, filterKeysId, multiKeysId, urlPrefix, maxPageSize, defaultsId],
    );
    const paramsRef = useRef(params);
    paramsRef.current = params;

    const commit = useCallback(
        (patch: Partial<ListParams>, resetPage: boolean, push: boolean) => {
            setSp(
                (prev) => {
                    const current = parseListParams(prev, optsRef.current);
                    const next: ListParams = { ...current, ...patch };
                    if (resetPage) next.page = 1;
                    return writeListParams(prev, next, optsRef.current);
                },
                { replace: !push },
            );
        },
        [setSp],
    );

    const fn = useMemo<ListFetcher<T>>(() => {
        if (fetcher) return fetcher;
        if (!endpoint) throw new Error("useListQuery requires `fetcher` or `endpoint`");
        return fetchList<T>(endpoint, maxPageSize);
    }, [fetcher, endpoint, maxPageSize]);

    const query = useQuery({
        queryKey: key(params),
        queryFn: ({ signal }) => fn(params, signal),
        placeholderData: keepPreviousData,
        enabled,
        refetchOnWindowFocus: false,
    });

    // Debounced search draft -> URL (replace: typing must not fill history).
    const [draft, setDraft] = useState<string | null>(null);
    const debouncedDraft = useDebouncedValue(draft, 300);
    useEffect(() => {
        if (debouncedDraft === null) return;
        if ((debouncedDraft || undefined) !== (paramsRef.current.search || undefined)) {
            commit({ search: debouncedDraft || undefined }, true, false);
        }
    }, [debouncedDraft, commit]);

    const setPage = useCallback((n: number) => commit({ page: Math.max(1, Math.floor(n) || 1) }, false, true), [commit]);
    const setPageSize = useCallback(
        (n: number) => commit({ pageSize: clampPageSize(n, optsRef.current.maxPageSize) }, true, false),
        [commit],
    );
    const setSearch = useCallback((s: string) => setDraft(s), []);
    const setFilters = useCallback((f: Record<string, FilterValue>) => commit({ filters: f }, true, false), [commit]);
    const setOrdering = useCallback((o: string | undefined) => commit({ ordering: o }, true, false), [commit]);
    const reset = useCallback(() => {
        setDraft(null);
        commit({ page: 1, search: undefined, ordering: undefined, filters: {}, pageSize: optsRef.current.defaults?.pageSize ?? 25 }, false, false);
    }, [commit]);
    const refetch = useCallback(() => void query.refetch(), [query]);

    return {
        params,
        result: query.data,
        status: query.status === "pending" ? "loading" : query.status,
        isFetching: query.isFetching,
        error: query.error,
        refetch,
        setPage, setPageSize, setSearch, setFilters, setOrdering, reset,
    };
}
