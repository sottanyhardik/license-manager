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
        if (timeoutId) {
            clearTimeout(timeoutId);
        }

        const newTimeoutId = setTimeout(() => {
            callback(...args);
        }, delay);

        setTimeoutId(newTimeoutId);
    };

    return debouncedCallback;
};

export default useDebounce;
