/**
 * Navigation utilities for consistent back button behavior
 * Ensures filters are restored when navigating back to list pages
 */

/**
 * Navigate back to list page with filter restoration
 * @param {function} navigate - React Router navigate function
 * @param {string} entityName - Entity name (e.g., 'licenses', 'allotments', 'trades', 'bill-of-entries')
 * @param {object} options - Additional options
 */
export const navigateToList = (navigate, entityName, options = {}) => {
    const { preserveFilters = true } = options;

    // Set flag to restore filters if needed
    if (preserveFilters) {
        try {
            sessionStorage.setItem(`${entityName}ListFilters`, JSON.stringify({
                returnTo: 'list',
                timestamp: new Date().getTime()
            }));
        } catch (error) {
            console.error('Failed to save navigation state:', error);
        }
    }

    // Navigate to appropriate list page
    const routes = {
        'licenses': '/licenses',
        'allotments': '/allotments',
        'trades': '/trades',
        'bill-of-entries': '/bill-of-entries',
        'incentive-licenses': '/incentive-licenses',
        'companies': '/masters/companies',
        'items': '/masters/items',
        'ports': '/masters/ports',
        'currencies': '/masters/currencies',
        'sion-classes': '/masters/sion-classes'
    };

    const path = routes[entityName] || `/masters/${entityName}`;
    navigate(path);
};

/**
 * Navigate to edit page while preserving current filters
 * @param {function} navigate - React Router navigate function
 * @param {string} entityName - Entity name
 * @param {string|number} id - Record ID
 * @param {object} currentFilters - Current filter state to preserve
 */
export const navigateToEdit = (navigate, entityName, id, currentFilters = {}) => {
    try {
        // Save current filters before navigating
        sessionStorage.setItem(`${entityName}ListFilters`, JSON.stringify({
            returnTo: 'edit',
            filters: currentFilters,
            timestamp: new Date().getTime()
        }));
    } catch (error) {
        console.error('Failed to save filters:', error);
    }

    // Navigate to edit page
    const routes = {
        'licenses': `/licenses/${id}/edit`,
        'allotments': `/allotments/${id}/edit`,
        'trades': `/trades/${id}/edit`,
        'bill-of-entries': `/masters/bill-of-entries/${id}/edit`,
        'incentive-licenses': `/incentive-licenses/${id}/edit`
    };

    const path = routes[entityName] || `/masters/${entityName}/${id}/edit`;
    navigate(path);
};

/**
 * Navigate to create page while preserving current filters
 * @param {function} navigate - React Router navigate function
 * @param {string} entityName - Entity name
 * @param {object} currentFilters - Current filter state to preserve
 */
export const navigateToCreate = (navigate, entityName, currentFilters = {}) => {
    try {
        // Save current filters before navigating
        sessionStorage.setItem(`${entityName}ListFilters`, JSON.stringify({
            returnTo: 'create',
            filters: currentFilters,
            timestamp: new Date().getTime()
        }));
    } catch (error) {
        console.error('Failed to save filters:', error);
    }

    // Navigate to create page
    const routes = {
        'licenses': '/licenses/create',
        'allotments': '/allotments/create',
        'trades': '/trades/create',
        'bill-of-entries': '/masters/bill-of-entries/create',
        'incentive-licenses': '/incentive-licenses/create'
    };

    const path = routes[entityName] || `/masters/${entityName}/create`;
    navigate(path);
};

/**
 * Check if we should restore filters when returning to list
 * @param {string} entityName - Entity name
 * @returns {boolean}
 */
export const shouldRestoreListFilters = (entityName) => {
    try {
        const stored = sessionStorage.getItem(`${entityName}ListFilters`);
        if (!stored) return false;

        const { returnTo } = JSON.parse(stored);
        return returnTo === 'list';
    } catch (error) {
        return false;
    }
};

/**
 * Get stored filters for restoration
 * @param {string} entityName - Entity name
 * @returns {object|null} - Stored filters or null
 */
export const getStoredFilters = (entityName) => {
    try {
        const stored = sessionStorage.getItem(`${entityName}ListFilters`);
        if (!stored) return null;

        const data = JSON.parse(stored);

        // Check if not too old (expire after 1 hour)
        const ONE_HOUR = 60 * 60 * 1000;
        if (data.timestamp && (new Date().getTime() - data.timestamp > ONE_HOUR)) {
            sessionStorage.removeItem(`${entityName}ListFilters`);
            return null;
        }

        return data.filters || null;
    } catch (error) {
        return null;
    }
};

/**
 * Clear stored filters
 * @param {string} entityName - Entity name
 */
export const clearStoredFilters = (entityName) => {
    try {
        sessionStorage.removeItem(`${entityName}ListFilters`);
    } catch (error) {
        console.error('Failed to clear filters:', error);
    }
};

/**
 * Navigate with browser back button support
 * This respects the browser's back button while preserving filter state
 * @param {function} navigate - React Router navigate function
 */
export const navigateBack = (navigate) => {
    // Check if there's history to go back to
    if (window.history.length > 1) {
        navigate(-1);
    } else {
        // Fallback to home if no history
        navigate('/');
    }
};
