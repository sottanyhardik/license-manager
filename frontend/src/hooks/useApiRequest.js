/**
 * useApiRequest Hook
 *
 * Enhanced API request hook with comprehensive features for handling API calls.
 * Provides loading states, error handling, success callbacks, toast notifications,
 * request cancellation, retry logic, and cache support.
 *
 * Features:
 * - Loading states
 * - Error handling with detailed error messages
 * - Success/error callbacks
 * - Automatic toast notifications
 * - Request cancellation (AbortController)
 * - Retry logic with exponential backoff
 * - Simple in-memory cache support
 * - Request deduplication
 * - Timeout support
 *
 * @example
 * const { execute, loading, error, data, cancel } = useApiRequest({
 *   onSuccess: (data) => console.log('Success!', data),
 *   onError: (error) => console.error('Error:', error),
 *   showSuccessToast: true,
 *   successMessage: 'Data saved successfully',
 *   retry: 3,
 *   retryDelay: 1000,
 *   cache: true,
 *   cacheTime: 5 * 60 * 1000 // 5 minutes
 * });
 *
 * // Execute request
 * const result = await execute(() => api.post('/users', userData));
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { toast } from "sonner";
import PropTypes from 'prop-types';
import { getErrorMessage } from '../utils/errorUtils';

// Simple in-memory cache
const requestCache = new Map();

/**
 * Generate cache key from request config
 */
const getCacheKey = (url, method = 'GET', params = {}) => {
  return `${method.toUpperCase()}:${url}:${JSON.stringify(params)}`;
};

/**
 * Sleep utility for retry delays
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Extract error message from error object
 */
const extractErrorMessage = (error, defaultMessage = 'An error occurred') => {
  if (typeof error === 'string') return error;
  return getErrorMessage(error) || defaultMessage;
};

/**
 * useApiRequest Hook
 *
 * @param {Object} options - Configuration options
 * @param {Function} options.onSuccess - Success callback
 * @param {Function} options.onError - Error callback
 * @param {boolean} options.showSuccessToast - Show success toast notification (default: false)
 * @param {boolean} options.showErrorToast - Show error toast notification (default: true)
 * @param {string} options.successMessage - Success toast message
 * @param {string} options.errorMessage - Error toast message
 * @param {number} options.retry - Number of retry attempts (default: 0)
 * @param {number} options.retryDelay - Delay between retries in ms (default: 1000)
 * @param {boolean} options.retryExponential - Use exponential backoff for retries (default: true)
 * @param {boolean} options.cache - Enable caching for GET requests (default: false)
 * @param {number} options.cacheTime - Cache duration in ms (default: 5 minutes)
 * @param {number} options.timeout - Request timeout in ms (default: 0, no timeout)
 * @param {boolean} options.deduplicate - Prevent duplicate concurrent requests (default: false)
 * @returns {Object} API request state and methods
 */
export const useApiRequest = (options = {}) => {
  const {
    onSuccess,
    onError,
    showSuccessToast = false,
    showErrorToast = true,
    successMessage = 'Operation completed successfully',
    errorMessage = 'Operation failed',
    retry = 0,
    retryDelay = 1000,
    retryExponential = true,
    cache = false,
    cacheTime = 5 * 60 * 1000, // 5 minutes
    timeout = 0,
    deduplicate = false
  } = options;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  const abortControllerRef = useRef(null);
  const pendingRequestsRef = useRef(new Map());

  /**
   * Cancel ongoing request
   */
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  /**
   * Clean up on unmount
   */
  useEffect(() => {
    return () => {
      cancel();
    };
  }, [cancel]);

  /**
   * Execute API request
   */
  const execute = useCallback(async (apiFunction, config = {}) => {
    const {
      cacheKey: customCacheKey,
      skipCache = false,
      skipToast = false
    } = config;

    // Check for cached data (only for GET requests)
    if (cache && !skipCache) {
      const cached = requestCache.get(customCacheKey || 'default');
      if (cached && Date.now() - cached.timestamp < cacheTime) {
        setData(cached.data);
        setError(null);
        setLoading(false);
        return { success: true, data: cached.data, fromCache: true };
      }
    }

    // Check for duplicate requests
    if (deduplicate && customCacheKey) {
      const pending = pendingRequestsRef.current.get(customCacheKey);
      if (pending) {
        return pending;
      }
    }

    // Create promise for execution
    const executePromise = (async () => {
      setLoading(true);
      setError(null);
      setRetryCount(0);

      // Create abort controller
      abortControllerRef.current = new AbortController();

      let lastError = null;
      let attempts = 0;

      while (attempts <= retry) {
        try {
          // Set timeout if specified
          let timeoutId;
          if (timeout > 0) {
            timeoutId = setTimeout(() => {
              abortControllerRef.current?.abort();
            }, timeout);
          }

          // Execute API call with abort signal
          const response = await apiFunction({
            signal: abortControllerRef.current.signal
          });

          // Clear timeout
          if (timeoutId) clearTimeout(timeoutId);

          const responseData = response?.data || response;

          // Update state
          setData(responseData);
          setError(null);
          setLoading(false);

          // Cache successful response
          if (cache && customCacheKey) {
            requestCache.set(customCacheKey, {
              data: responseData,
              timestamp: Date.now()
            });
          }

          // Show success toast
          if (showSuccessToast && !skipToast) {
            toast.success(successMessage);
          }

          // Call success callback
          if (onSuccess) {
            onSuccess(responseData);
          }

          // Clear from pending requests
          if (deduplicate && customCacheKey) {
            pendingRequestsRef.current.delete(customCacheKey);
          }

          return { success: true, data: responseData, attempts };

        } catch (err) {
          // Request was cancelled
          if (err.name === 'AbortError' || err.name === 'CanceledError') {
            setLoading(false);
            if (deduplicate && customCacheKey) {
              pendingRequestsRef.current.delete(customCacheKey);
            }
            return { success: false, cancelled: true };
          }

          lastError = err;
          attempts++;

          // Retry logic
          if (attempts <= retry) {
            setRetryCount(attempts);
            const delay = retryExponential
              ? retryDelay * Math.pow(2, attempts - 1)
              : retryDelay;

            await sleep(delay);
            continue;
          }

          // All retries exhausted
          break;
        }
      }

      // Handle final error
      const errorMsg = extractErrorMessage(lastError, errorMessage);
      const errorData = lastError?.response?.data || { detail: errorMsg };

      setError(errorMsg);
      setData(null);
      setLoading(false);

      // Show error toast
      if (showErrorToast && !skipToast) {
        toast.error(errorMsg);
      }

      // Call error callback
      if (onError) {
        onError(lastError);
      }

      // Clear from pending requests
      if (deduplicate && customCacheKey) {
        pendingRequestsRef.current.delete(customCacheKey);
      }

      return {
        success: false,
        error: errorMsg,
        errorData,
        attempts
      };
    })();

    // Store in pending requests
    if (deduplicate && customCacheKey) {
      pendingRequestsRef.current.set(customCacheKey, executePromise);
    }

    return executePromise;
  }, [
    onSuccess,
    onError,
    showSuccessToast,
    showErrorToast,
    successMessage,
    errorMessage,
    retry,
    retryDelay,
    retryExponential,
    cache,
    cacheTime,
    timeout,
    deduplicate
  ]);

  /**
   * Execute GET request with caching
   */
  const get = useCallback(async (url, params = {}, config = {}) => {
    const cacheKey = getCacheKey(url, 'GET', params);

    return execute(
      ({ signal }) => {
        // Assuming axios-like API
        return window.api.get(url, { params, signal });
      },
      { ...config, cacheKey }
    );
  }, [execute]);

  /**
   * Execute POST request
   */
  const post = useCallback(async (url, data = {}, config = {}) => {
    return execute(
      ({ signal }) => window.api.post(url, data, { signal }),
      config
    );
  }, [execute]);

  /**
   * Execute PUT request
   */
  const put = useCallback(async (url, data = {}, config = {}) => {
    return execute(
      ({ signal }) => window.api.put(url, data, { signal }),
      config
    );
  }, [execute]);

  /**
   * Execute PATCH request
   */
  const patch = useCallback(async (url, data = {}, config = {}) => {
    return execute(
      ({ signal }) => window.api.patch(url, data, { signal }),
      config
    );
  }, [execute]);

  /**
   * Execute DELETE request
   */
  const del = useCallback(async (url, config = {}) => {
    return execute(
      ({ signal }) => window.api.delete(url, { signal }),
      config
    );
  }, [execute]);

  /**
   * Reset state
   */
  const reset = useCallback(() => {
    setLoading(false);
    setError(null);
    setData(null);
    setRetryCount(0);
    cancel();
  }, [cancel]);

  /**
   * Clear cache for specific key or all
   */
  const clearCache = useCallback((cacheKey) => {
    if (cacheKey) {
      requestCache.delete(cacheKey);
    } else {
      requestCache.clear();
    }
  }, []);

  return {
    // State
    loading,
    error,
    data,
    retryCount,

    // Methods
    execute,
    get,
    post,
    put,
    patch,
    delete: del,
    cancel,
    reset,
    clearCache,

    // Setters
    setData,
    setError
  };
};

/**
 * Clear all cached requests
 */
export const clearAllCache = () => {
  requestCache.clear();
};

/**
 * Get cache statistics
 */
export const getCacheStats = () => {
  return {
    size: requestCache.size,
    keys: Array.from(requestCache.keys())
  };
};

// PropTypes for documentation
useApiRequest.propTypes = {
  options: PropTypes.shape({
    onSuccess: PropTypes.func,
    onError: PropTypes.func,
    showSuccessToast: PropTypes.bool,
    showErrorToast: PropTypes.bool,
    successMessage: PropTypes.string,
    errorMessage: PropTypes.string,
    retry: PropTypes.number,
    retryDelay: PropTypes.number,
    retryExponential: PropTypes.bool,
    cache: PropTypes.bool,
    cacheTime: PropTypes.number,
    timeout: PropTypes.number,
    deduplicate: PropTypes.bool
  })
};

export default useApiRequest;
