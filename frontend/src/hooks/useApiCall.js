/**
 * Custom hook for API calls with loading, error, and success states.
 *
 * Provides a consistent way to handle API requests with automatic
 * state management for loading, error, and success states.
 *
 * @example
 * const { execute, loading, error, data, success } = useApiCall();
 *
 * const handleSubmit = async () => {
 *   const result = await execute(() => api.post('/endpoint', data));
 *   if (result.success) {
 *     console.log('Success!', result.data);
 *   }
 * };
 */

import {useCallback, useState} from 'react';

export const useApiCall = (options = {}) => {
    const {
        onSuccess,
        onError,
        showErrorAlert = true,
        showSuccessAlert = true,
    } = options;

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [data, setData] = useState(null);
    const [success, setSuccess] = useState(false);

    const execute = useCallback(async (apiFunction, config = {}) => {
        setLoading(true);
        setError(null);
        setSuccess(false);
        setData(null);

        try {
            const response = await apiFunction();
            const responseData = response?.data || response;

            setData(responseData);
            setSuccess(true);

            if (onSuccess) {
                onSuccess(responseData);
            }

            return {success: true, data: responseData, error: null};
        } catch (err) {
            const errorMessage = err.response?.data?.detail
                || err.response?.data?.message
                || err.message
                || 'An error occurred';

            const errorData = err.response?.data || {detail: errorMessage};

            setError(errorMessage);
            setSuccess(false);

            if (onError) {
                onError(err);
            }

            return {success: false, data: null, error: errorMessage, errorData};
        } finally {
            setLoading(false);
        }
    }, [onSuccess, onError]);

    const reset = useCallback(() => {
        setLoading(false);
        setError(null);
        setData(null);
        setSuccess(false);
    }, []);

    return {
        execute,
        loading,
        error,
        data,
        success,
        reset,
    };
};

/**
 * Custom hook for managing multiple API calls with individual states.
 *
 * Useful when you need to track loading states for different operations
 * independently (e.g., save, delete, update).
 *
 * @example
 * const {
 *   execute,
 *   isLoading,
 *   getError,
 *   isSuccess
 * } = useMultipleApiCalls();
 *
 * const handleSave = async (id) => {
 *   await execute(`save-${id}`, () => api.put(`/items/${id}`, data));
 * };
 *
 * // Check loading state for specific operation
 * {isLoading(`save-${id}`) && <Spinner />}
 */

export const useMultipleApiCalls = () => {
    const [loadingStates, setLoadingStates] = useState({});
    const [errorStates, setErrorStates] = useState({});
    const [successStates, setSuccessStates] = useState({});

    const execute = useCallback(async (key, apiFunction) => {
        setLoadingStates(prev => ({...prev, [key]: true}));
        setErrorStates(prev => ({...prev, [key]: null}));
        setSuccessStates(prev => ({...prev, [key]: false}));

        try {
            const response = await apiFunction();
            const responseData = response?.data || response;

            setSuccessStates(prev => ({...prev, [key]: true}));
            setLoadingStates(prev => ({...prev, [key]: false}));

            return {success: true, data: responseData, error: null};
        } catch (err) {
            const errorMessage = err.response?.data?.detail
                || err.response?.data?.message
                || err.message
                || 'An error occurred';

            setErrorStates(prev => ({...prev, [key]: errorMessage}));
            setSuccessStates(prev => ({...prev, [key]: false}));
            setLoadingStates(prev => ({...prev, [key]: false}));

            return {success: false, data: null, error: errorMessage};
        }
    }, []);

    const isLoading = useCallback((key) => {
        return loadingStates[key] || false;
    }, [loadingStates]);

    const getError = useCallback((key) => {
        return errorStates[key] || null;
    }, [errorStates]);

    const isSuccess = useCallback((key) => {
        return successStates[key] || false;
    }, [successStates]);

    const reset = useCallback((key) => {
        if (key) {
            setLoadingStates(prev => ({...prev, [key]: false}));
            setErrorStates(prev => ({...prev, [key]: null}));
            setSuccessStates(prev => ({...prev, [key]: false}));
        } else {
            setLoadingStates({});
            setErrorStates({});
            setSuccessStates({});
        }
    }, []);

    return {
        execute,
        isLoading,
        getError,
        isSuccess,
        reset,
    };
};

export default useApiCall;
