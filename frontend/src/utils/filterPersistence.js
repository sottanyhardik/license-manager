/**
 * Utility functions for persisting and restoring filter state
 * Uses sessionStorage to maintain filters across navigation
 */

const STORAGE_KEY_PREFIX = 'filterState_';

/**
 * Save filter state to sessionStorage
 * @param {string} pageKey - Unique identifier for the page (e.g., 'allotments', 'licenses')
 * @param {object} filters - Filter object to persist
 * @param {object} pagination - Pagination state to persist (optional)
 * @param {string} search - Search string to persist (optional)
 */
export const saveFilterState = (pageKey, { filters, pagination, search }) => {
    try {
        const state = {
            filters: filters || {},
            pagination: pagination || {},
            search: search || '',
            timestamp: new Date().getTime()
        };
        sessionStorage.setItem(`${STORAGE_KEY_PREFIX}${pageKey}`, JSON.stringify(state));
    } catch (error) {
        // Silently handle error
    }
};

/**
 * Restore filter state from sessionStorage
 * @param {string} pageKey - Unique identifier for the page
 * @returns {object|null} - Restored state or null if not found/expired
 */
export const restoreFilterState = (pageKey) => {
    try {
        const stored = sessionStorage.getItem(`${STORAGE_KEY_PREFIX}${pageKey}`);
        if (!stored) return null;

        const state = JSON.parse(stored);

        // Check if state is not too old (expire after 1 hour)
        const ONE_HOUR = 60 * 60 * 1000;
        if (state.timestamp && (new Date().getTime() - state.timestamp > ONE_HOUR)) {
            clearFilterState(pageKey);
            return null;
        }

        return state;
    } catch (error) {
        return null;
    }
};

/**
 * Clear filter state from sessionStorage
 * @param {string} pageKey - Unique identifier for the page
 */
export const clearFilterState = (pageKey) => {
    try {
        sessionStorage.removeItem(`${STORAGE_KEY_PREFIX}${pageKey}`);
    } catch (error) {
        // Silently handle error
    }
};

/**
 * Check if we should restore filters (coming back from edit/create)
 * @returns {boolean}
 */
export const shouldRestoreFilters = () => {
    try {
        const returnFlag = sessionStorage.getItem('allotmentListFilters');
        if (returnFlag) {
            const { returnTo } = JSON.parse(returnFlag);
            sessionStorage.removeItem('allotmentListFilters');
            return returnTo === 'list';
        }
        return false;
    } catch (error) {
        return false;
    }
};

/**
 * Mark that a new item was created to scroll to it
 * @param {string|number} itemId - ID of newly created item
 */
export const markNewItemCreated = (itemId) => {
    try {
        sessionStorage.setItem('newlyCreatedItem', JSON.stringify({
            id: itemId,
            timestamp: new Date().getTime()
        }));
    } catch (error) {
        // Silently handle error
    }
};

/**
 * Get and clear newly created item marker
 * @returns {string|number|null} - ID of newly created item or null
 */
export const getNewlyCreatedItem = () => {
    try {
        const stored = sessionStorage.getItem('newlyCreatedItem');
        if (!stored) return null;

        const { id, timestamp } = JSON.parse(stored);

        // Only return if less than 10 seconds old
        if (new Date().getTime() - timestamp < 10000) {
            sessionStorage.removeItem('newlyCreatedItem');
            return id;
        }

        sessionStorage.removeItem('newlyCreatedItem');
        return null;
    } catch (error) {
        return null;
    }
};
