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

import {useEffect, useState} from 'react';

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
    const [timeoutId, setTimeoutId] = useState(null);

    useEffect(() => {
        // Cleanup on unmount
        return () => {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
        };
    }, [timeoutId]);

    const debouncedCallback = (...args) => {
        // Return a promise for async compatibility
        return new Promise((resolve, reject) => {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }

            const newTimeoutId = setTimeout(async () => {
                try {
                    const result = await callback(...args);
                    resolve(result);
                } catch (error) {
                    reject(error);
                }
            }, delay);

            setTimeoutId(newTimeoutId);
        });
    };

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
