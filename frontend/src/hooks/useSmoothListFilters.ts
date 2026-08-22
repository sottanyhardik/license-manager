import { useCallback, useEffect, useMemo, useRef, useState } from "react";

function sameFilters<T extends Record<string, unknown>>(left: T, right: T) {
    const leftEntries = Object.entries(left);
    return leftEntries.length === Object.keys(right).length
        && leftEntries.every(([key, value]) => right[key] === value);
}

/**
 * Keeps a list's filter controls responsive while deliberately delaying only
 * free-text criteria.  Pages use `appliedFilters` as their React Query key;
 * select/date/toggle changes call `setImmediateFilter` and therefore fetch at
 * once.  A monotonically increasing generation makes it straightforward for
 * consumers to ignore any non-cancellable legacy request response.
 */
export function useSmoothListFilters<T extends Record<string, unknown>>(
    initialFilters: T,
    { delay = 400 } = {},
) {
    const [filters, setFilters] = useState<T>(initialFilters);
    const [appliedFilters, setAppliedFilters] = useState<T>(initialFilters);
    const [isDebouncing, setIsDebouncing] = useState(false);
    const [generation, setGeneration] = useState(0);
    const initialRef = useRef(initialFilters);

    // Changing the logical list (for example a routed entity) replaces both
    // draft and applied filters exactly once, rather than reinitialising while
    // a user is typing.
    useEffect(() => {
        if (sameFilters(initialRef.current, initialFilters)) return;
        initialRef.current = initialFilters;
        setFilters(initialFilters);
        setAppliedFilters(initialFilters);
        setGeneration(value => value + 1);
        setIsDebouncing(false);
    }, [initialFilters]);

    const setImmediateFilter = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
        setFilters(previous => {
            const next = { ...previous, [key]: value };
            setAppliedFilters(next);
            setGeneration(current => current + 1);
            return next;
        });
        setIsDebouncing(false);
    }, []);

    const setTextFilter = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
        setFilters(previous => ({ ...previous, [key]: value }));
        setIsDebouncing(true);
    }, []);

    useEffect(() => {
        if (!isDebouncing) return;
        const timer = window.setTimeout(() => {
            setAppliedFilters(filters);
            setGeneration(current => current + 1);
            setIsDebouncing(false);
        }, delay);
        return () => window.clearTimeout(timer);
    }, [delay, filters, isDebouncing]);

    const replaceFilters = useCallback((next: T, immediate = true) => {
        setFilters(next);
        if (immediate) {
            setAppliedFilters(next);
            setGeneration(current => current + 1);
            setIsDebouncing(false);
        } else {
            setIsDebouncing(true);
        }
    }, []);

    const result = useMemo(() => ({
        filters,
        appliedFilters,
        isDebouncing,
        generation,
        setTextFilter,
        setImmediateFilter,
        replaceFilters,
    }), [appliedFilters, filters, generation, isDebouncing, replaceFilters, setImmediateFilter, setTextFilter]);

    return result;
}
