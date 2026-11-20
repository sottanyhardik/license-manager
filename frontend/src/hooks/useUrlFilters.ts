import { useCallback, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

export type UrlFilterValues = Record<string, string>;
export type UrlFilterSetter<T extends UrlFilterValues> = (patch: Partial<T>, options?: { replace?: boolean }) => void;

/**
 * Report filters whose single source of truth is the URL query string, so they
 * survive refresh and follow browser back/forward. `normalize` turns the raw
 * params (null when absent) into valid values, applying defaults; a missing or
 * invalid param is written back once (history `replace`) so the applied default
 * is visible in the URL. Unrelated params are preserved.
 */
export function useUrlFilters<T extends UrlFilterValues>(
    keys: readonly (keyof T & string)[],
    normalize: (raw: Record<keyof T & string, string | null>) => T,
): [T, UrlFilterSetter<T>] {
    const [searchParams, setSearchParams] = useSearchParams();
    const query = searchParams.toString();

    const params = new URLSearchParams(query);
    const normalized = normalize(Object.fromEntries(keys.map(key => [key, params.get(key)])) as Record<keyof T & string, string | null>);
    // Identity follows the normalized *content*, so writing the defaults back (or changing an unrelated
    // param) does not hand consumers a new object and re-trigger their data fetches.
    const signature = JSON.stringify(keys.map(key => normalized[key]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const values = useMemo(() => normalized, [signature]);

    const setFilters = useCallback<UrlFilterSetter<T>>((patch, options) => {
        setSearchParams(prev => {
            const next = new URLSearchParams(prev);
            for (const [key, value] of Object.entries(patch)) {
                if (value !== undefined) next.set(key, value);
            }
            return next;
        }, { replace: options?.replace ?? false });
    }, [setSearchParams]);

    useEffect(() => {
        const params = new URLSearchParams(query);
        const stale = keys.filter(key => params.get(key) !== values[key]);
        if (stale.length > 0) {
            setFilters(Object.fromEntries(stale.map(key => [key, values[key]])) as Partial<T>, { replace: true });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [query, values, setFilters]);

    return [values, setFilters];
}
