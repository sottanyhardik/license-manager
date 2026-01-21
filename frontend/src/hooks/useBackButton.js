import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Custom hook to handle browser back button with filter preservation
 * This ensures that when users click the browser back button,
 * they return to the previous page with filters intact
 *
 * @param {string} entityName - Entity name for filter restoration
 * @param {boolean} enabled - Whether to enable the back button handler (default: true)
 */
export const useBackButton = (entityName, enabled = true) => {
    const navigate = useNavigate();

    useEffect(() => {
        if (!enabled) return;

        const handlePopState = (event) => {
            // Set flag to restore filters when using browser back button
            try {
                sessionStorage.setItem(`${entityName}ListFilters`, JSON.stringify({
                    returnTo: 'list',
                    timestamp: new Date().getTime(),
                    source: 'browser-back'
                }));
            } catch (error) {
                console.error('Failed to save navigation state:', error);
            }
        };

        // Listen for browser back/forward button
        window.addEventListener('popstate', handlePopState);

        return () => {
            window.removeEventListener('popstate', handlePopState);
        };
    }, [entityName, enabled]);
};

/**
 * Custom hook to detect if user navigated via browser back button
 * Useful for triggering specific behaviors on back navigation
 *
 * @param {function} callback - Function to call when back navigation detected
 */
export const useBackNavigation = (callback) => {
    useEffect(() => {
        const handlePopState = () => {
            if (typeof callback === 'function') {
                callback();
            }
        };

        window.addEventListener('popstate', handlePopState);

        return () => {
            window.removeEventListener('popstate', handlePopState);
        };
    }, [callback]);
};
