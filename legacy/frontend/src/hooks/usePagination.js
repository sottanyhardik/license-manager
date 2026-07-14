/**
 * Custom hook for pagination state management.
 *
 * Provides pagination state and controls for list views.
 *
 * @example
 * const {
 *   currentPage,
 *   pageSize,
 *   totalItems,
 *   totalPages,
 *   goToPage,
 *   nextPage,
 *   prevPage,
 *   setPageSize,
 *   setTotalItems,
 *   resetPagination
 * } = usePagination({ initialPageSize: 20 });
 */

import {useState, useCallback} from 'react';

export const usePagination = ({
                                  initialPage = 1,
                                  initialPageSize = 20,
                                  initialTotalItems = 0
                              } = {}) => {
    const [currentPage, setCurrentPage] = useState(initialPage);
    const [pageSize, setPageSize] = useState(initialPageSize);
    const [totalItems, setTotalItems] = useState(initialTotalItems);

    // Calculate total pages
    const totalPages = Math.ceil(totalItems / pageSize) || 1;

    // Go to specific page
    const goToPage = useCallback((page) => {
        const validPage = Math.max(1, Math.min(page, totalPages));
        setCurrentPage(validPage);
    }, [totalPages]);

    // Go to next page
    const nextPage = useCallback(() => {
        if (currentPage < totalPages) {
            setCurrentPage(prev => prev + 1);
        }
    }, [currentPage, totalPages]);

    // Go to previous page
    const prevPage = useCallback(() => {
        if (currentPage > 1) {
            setCurrentPage(prev => prev - 1);
        }
    }, [currentPage]);

    // Go to first page
    const firstPage = useCallback(() => {
        setCurrentPage(1);
    }, []);

    // Go to last page
    const lastPage = useCallback(() => {
        setCurrentPage(totalPages);
    }, [totalPages]);

    // Change page size and reset to first page
    const changePageSize = useCallback((newSize) => {
        setPageSize(newSize);
        setCurrentPage(1);
    }, []);

    // Reset pagination to initial state
    const resetPagination = useCallback(() => {
        setCurrentPage(initialPage);
        setPageSize(initialPageSize);
        setTotalItems(initialTotalItems);
    }, [initialPage, initialPageSize, initialTotalItems]);

    // Update total items (typically from API response)
    const updateTotalItems = useCallback((total) => {
        setTotalItems(total);
    }, []);

    // Check if on first page
    const isFirstPage = currentPage === 1;

    // Check if on last page
    const isLastPage = currentPage === totalPages;

    // Calculate offset for API calls
    const offset = (currentPage - 1) * pageSize;

    // Get page numbers for pagination UI
    const getPageNumbers = useCallback((maxVisible = 5) => {
        const pages = [];
        const half = Math.floor(maxVisible / 2);

        let start = Math.max(1, currentPage - half);
        let end = Math.min(totalPages, start + maxVisible - 1);

        // Adjust start if we're near the end
        if (end - start < maxVisible - 1) {
            start = Math.max(1, end - maxVisible + 1);
        }

        for (let i = start; i <= end; i++) {
            pages.push(i);
        }

        return pages;
    }, [currentPage, totalPages]);

    return {
        // State
        currentPage,
        pageSize,
        totalItems,
        totalPages,
        isFirstPage,
        isLastPage,
        offset,

        // Actions
        goToPage,
        nextPage,
        prevPage,
        firstPage,
        lastPage,
        setPageSize: changePageSize,
        setTotalItems: updateTotalItems,
        resetPagination,
        getPageNumbers,
    };
};

export default usePagination;
