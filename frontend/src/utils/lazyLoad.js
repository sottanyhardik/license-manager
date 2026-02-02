import { lazy } from 'react';

/**
 * Enhanced lazy loading with retry logic
 *
 * This utility wraps React.lazy with automatic retry on chunk load failure.
 * Useful for handling network issues or cache problems during code splitting.
 *
 * @param {Function} importFunc - Dynamic import function
 * @param {number} retries - Number of retry attempts (default: 3)
 * @param {number} interval - Delay between retries in ms (default: 1000)
 * @returns {React.LazyExoticComponent}
 *
 * @example
 * const MyComponent = lazyLoadWithRetry(() => import('./MyComponent'));
 */
export function lazyLoadWithRetry(importFunc, retries = 3, interval = 1000) {
    return lazy(() => {
        return new Promise((resolve, reject) => {
            const attemptImport = (attemptsLeft) => {
                importFunc()
                    .then(resolve)
                    .catch((error) => {
                        // Check if this is a chunk load error
                        const isChunkError = /Loading chunk [\d]+ failed/.test(error.message);

                        if (attemptsLeft === 0) {
                            reject(error);
                            return;
                        }

                        if (isChunkError) {
                            console.warn(
                                `Chunk load failed. Retrying... (${retries - attemptsLeft + 1}/${retries})`
                            );

                            setTimeout(() => {
                                attemptImport(attemptsLeft - 1);
                            }, interval);
                        } else {
                            reject(error);
                        }
                    });
            };

            attemptImport(retries);
        });
    });
}

/**
 * Lazy load component with preload capability
 *
 * Returns both the lazy component and a preload function.
 * Useful for preloading components on hover or navigation.
 *
 * @param {Function} importFunc - Dynamic import function
 * @returns {Object} { Component, preload }
 *
 * @example
 * const { Component: MyModal, preload } = lazyLoadWithPreload(() => import('./MyModal'));
 *
 * <button onMouseEnter={preload}>Open Modal</button>
 * <MyModal show={showModal} />
 */
export function lazyLoadWithPreload(importFunc) {
    let modulePromise = null;

    const preload = () => {
        if (!modulePromise) {
            modulePromise = importFunc();
        }
        return modulePromise;
    };

    const Component = lazy(() => {
        return preload();
    });

    return { Component, preload };
}

/**
 * Prefetch components on idle
 *
 * Uses requestIdleCallback to prefetch components when browser is idle.
 * Falls back to setTimeout if requestIdleCallback is not available.
 *
 * @param {Array<Function>} importFunctions - Array of dynamic import functions
 *
 * @example
 * prefetchOnIdle([
 *   () => import('./HeavyModal'),
 *   () => import('./Chart'),
 *   () => import('./ReportComponent')
 * ]);
 */
export function prefetchOnIdle(importFunctions) {
    if (typeof window === 'undefined') return;

    const prefetch = () => {
        importFunctions.forEach(importFunc => {
            importFunc().catch(err => {
                console.warn('Prefetch failed:', err);
            });
        });
    };

    if ('requestIdleCallback' in window) {
        window.requestIdleCallback(prefetch);
    } else {
        setTimeout(prefetch, 1);
    }
}

/**
 * Lazy load based on route
 *
 * Creates route-based code splitting with named chunks.
 * Improves debugging and cache management.
 *
 * @param {string} routeName - Name for the chunk
 * @param {Function} importFunc - Dynamic import function
 * @returns {React.LazyExoticComponent}
 *
 * @example
 * const Dashboard = lazyLoadRoute('dashboard', () => import('./pages/Dashboard'));
 */
export function lazyLoadRoute(routeName, importFunc) {
    return lazy(() =>
        importFunc()
            .then(module => {
                // Log successful load in development
                if (process.env.NODE_ENV === 'development') {
                    console.log(`Route "${routeName}" loaded`);
                }
                return module;
            })
            .catch(error => {
                console.error(`Failed to load route "${routeName}":`, error);
                throw error;
            })
    );
}

/**
 * Lazy load modal component
 *
 * Special handling for modal components that may not be rendered immediately.
 *
 * @param {Function} importFunc - Dynamic import function
 * @returns {React.LazyExoticComponent}
 *
 * @example
 * const MyModal = lazyLoadModal(() => import('./MyModal'));
 *
 * {showModal && <MyModal show={showModal} onHide={handleClose} />}
 */
export function lazyLoadModal(importFunc) {
    return lazyLoadWithRetry(importFunc, 2, 500);
}

/**
 * Preload critical routes on app load
 *
 * Preloads important routes after initial page load to improve navigation speed.
 *
 * @param {Object} routes - Map of route names to import functions
 * @param {number} delay - Delay before starting preload in ms (default: 2000)
 *
 * @example
 * preloadCriticalRoutes({
 *   dashboard: () => import('./pages/Dashboard'),
 *   reports: () => import('./pages/Reports')
 * }, 2000);
 */
export function preloadCriticalRoutes(routes, delay = 2000) {
    if (typeof window === 'undefined') return;

    setTimeout(() => {
        Object.entries(routes).forEach(([name, importFunc]) => {
            importFunc()
                .then(() => {
                    if (process.env.NODE_ENV === 'development') {
                        console.log(`Preloaded route: ${name}`);
                    }
                })
                .catch(err => {
                    console.warn(`Failed to preload route ${name}:`, err);
                });
        });
    }, delay);
}

export default lazyLoadWithRetry;
