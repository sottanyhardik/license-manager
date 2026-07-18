/**
 * Custom hook for debouncing values.
 *
 * Delays updating a value until after a specified delay has elapsed
 * since the last time it was changed.
 *
 * @example
 * const [searchTerm, setSearchTerm] = useState('');
 * const debouncedSearchTerm = useDebounce(searchTerm, 500);
 *
 * useEffect(() => {
 *   // This will only run when debouncedSearchTerm changes
 *   // (500ms after user stops typing)
 *   fetchSearchResults(debouncedSearchTerm);
 * }, [debouncedSearchTerm]);
 */

import {useCallback, useEffect, useRef, useState} from 'react';

export const useDebounce = (value, delay = 300) => {
    const [debouncedValue, setDebouncedValue] = useState(value);

    useEffect(() => {
        // Set up the timeout
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        // Clean up the timeout if value changes before delay expires
        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);

    return debouncedValue;
};

/**
 * Custom hook for debouncing callbacks.
 *
 * Returns a debounced version of the callback that only executes
 * after the specified delay has elapsed since the last call.
 *
 * @example
 * const handleSearch = useDebouncedCallback((term) => {
 *   fetchSearchResults(term);
 * }, 500);
 *
 * // In component:
 * <input onChange={(e) => handleSearch(e.target.value)} />
 */

export const useDebouncedCallback = (callback, delay = 300) => {
    const timeoutRef = useRef(null);
    // Keep callback ref fresh without needing it in the useCallback deps
    const callbackRef = useRef(callback);
    useEffect(() => { callbackRef.current = callback; });

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
        };
    }, []);

    const debouncedCallback = useCallback((...args) => {
        return new Promise((resolve, reject) => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            timeoutRef.current = setTimeout(async () => {
                timeoutRef.current = null;
                try {
                    const result = await callbackRef.current(...args);
                    resolve(result);
                } catch (error) {
                    reject(error);
                }
            }, delay);
        });
    }, [delay]); // only changes when delay changes

    return debouncedCallback;
};

/**
 * Custom hook for debouncing multiple filter values together.
 *
 * Useful for forms with multiple filters that should all debounce together.
 *
 * @example
 * const filters = useMemo(() => ({
 *   search, minPrice, maxPrice, category
 * }), [search, minPrice, maxPrice, category]);
 *
 * const debouncedFilters = useDebouncedFilters(filters, 500);
 *
 * useEffect(() => {
 *   fetchData(debouncedFilters);
 * }, [debouncedFilters]);
 */
export const useDebouncedFilters = (filters, delay = 500) => {
    const [debouncedFilters, setDebouncedFilters] = useState(filters);
    const [isPending, setIsPending] = useState(false);

    useEffect(() => {
        setIsPending(true);

        const handler = setTimeout(() => {
            setDebouncedFilters(filters);
            setIsPending(false);
        }, delay);

        return () => {
            clearTimeout(handler);
        };
    }, [filters, delay]);

    return { debouncedFilters, isPending };
};

/**
 * Hook for debouncing with loading state.
 *
 * Provides both debounced value and a boolean indicating if debounce is pending.
 * Useful for showing loading indicators during debounce period.
 *
 * @example
 * const { debouncedValue, isPending } = useDebouncedState(searchTerm, 500);
 *
 * return (
 *   <div>
 *     <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
 *     {isPending && <Spinner />}
 *   </div>
 * );
 */
export const useDebouncedState = (value, delay = 300) => {
    const [debouncedValue, setDebouncedValue] = useState(value);
    const [isPending, setIsPending] = useState(false);

    useEffect(() => {
        setIsPending(true);

        const handler = setTimeout(() => {
            setDebouncedValue(value);
            setIsPending(false);
        }, delay);

        return () => {
            clearTimeout(handler);
        };
    }, [value, delay]);

    return { debouncedValue, isPending };
};

export default useDebounce;
