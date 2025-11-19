/**
 * Custom hook for AllotmentAction page logic.
 *
 * Centralizes all state management and business logic for the allotment
 * action page, including fetching data, handling allocations, and filtering.
 */

import {useState, useEffect, useCallback} from 'react';
import {allotmentApi} from '../../services/api';
import {allocationCalculator} from '../../services/calculators';
import {usePagination} from '../usePagination';
import {useDebounce} from '../useDebounce';
import {useMultipleApiCalls} from '../useApiCall';

export const useAllotmentAction = (allotmentId) => {
    // State
    const [allotment, setAllotment] = useState(null);
    const [availableItems, setAvailableItems] = useState([]);
    const [allocationData, setAllocationData] = useState({});
    const [initialLoading, setInitialLoading] = useState(true);
    const [tableLoading, setTableLoading] = useState(false);
    const [search, setSearch] = useState('');
    const [notificationOptions, setNotificationOptions] = useState([]);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [isFirstLoad, setIsFirstLoad] = useState(true);

    const [filters, setFilters] = useState({
        description: '',
        exporter: '',
        available_quantity_gte: '50',
        available_quantity_lte: '',
        available_value_gte: '100',
        available_value_lte: '',
        notification_number: '',
        norm_class: '',
        hs_code: '',
        is_expired: 'false'
    });

    // Pagination
    const pagination = usePagination({initialPageSize: 20});

    // Debounced search and filters
    const debouncedSearch = useDebounce(search, 300);
    const debouncedFilters = useDebounce(filters, 300);

    // API calls tracker
    const {execute, isLoading, getError} = useMultipleApiCalls();

    // Fetch notification options on mount
    useEffect(() => {
        fetchNotificationOptions();
    }, []);

    // Auto-set description filter from allotment item_name on first load
    useEffect(() => {
        if (isFirstLoad && allotment?.item_name) {
            setFilters(prev => ({...prev, description: allotment.item_name}));
            setIsFirstLoad(false);
        }
    }, [allotment, isFirstLoad]);

    // Fetch data when filters change (reset to page 1)
    useEffect(() => {
        pagination.goToPage(1);
        fetchData(1);
    }, [debouncedSearch, debouncedFilters]);

    // Fetch data when page changes
    useEffect(() => {
        if (pagination.currentPage > 1) {
            fetchData(pagination.currentPage);
        }
    }, [pagination.currentPage]);

    // Fetch notification options
    const fetchNotificationOptions = async () => {
        try {
            const choices = await allotmentApi.fetchNotificationOptions();
            setNotificationOptions(choices);
        } catch (err) {
            console.error('Failed to load notification options:', err);
        }
    };

    // Fetch available licenses
    const fetchData = async (page = 1) => {
        if (allotment === null) {
            setInitialLoading(true);
        } else {
            setTableLoading(true);
        }
        setError('');

        try {
            const params = {
                search: debouncedSearch,
                page,
                page_size: pagination.pageSize,
                ...Object.fromEntries(
                    Object.entries(debouncedFilters).filter(([_, value]) => value)
                )
            };

            const data = await allotmentApi.fetchAvailableLicenses(allotmentId, params);

            setAllotment(data.allotment);
            setAvailableItems(data.available_items || data.results || []);

            if (data.count !== undefined) {
                pagination.setTotalItems(data.count);
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to load data');
        } finally {
            setInitialLoading(false);
            setTableLoading(false);
        }
    };

    // Calculate max allocation for an item
    const calculateMaxAllocation = useCallback((item) => {
        if (!allotment) return {qty: 0, value: 0};
        return allocationCalculator.calculateMaxAllocation(item, allotment);
    }, [allotment]);

    // Handle quantity change
    const handleQuantityChange = useCallback((itemId, qty) => {
        const item = availableItems.find(i => i.id === itemId);
        if (!item || !allotment) return;

        const unitPrice = parseFloat(allotment.unit_value_per_unit);
        let inputQty = parseInt(qty) || 0;

        // Calculate constraints
        const max = calculateMaxAllocation(item);

        // Constrain quantity
        inputQty = Math.min(inputQty, max.qty);

        // Calculate value
        let allocateCifFc = inputQty * unitPrice;

        // Ensure value doesn't exceed max
        if (allocateCifFc > max.value) {
            inputQty = Math.floor(max.value / unitPrice);
            allocateCifFc = inputQty * unitPrice;
        }

        setAllocationData(prev => ({
            ...prev,
            [itemId]: {
                qty: inputQty.toString(),
                cif_fc: allocateCifFc.toFixed(2)
            }
        }));
    }, [availableItems, allotment, calculateMaxAllocation]);

    // Handle value change
    const handleValueChange = useCallback((itemId, value) => {
        const item = availableItems.find(i => i.id === itemId);
        if (!item || !allotment) return;

        const unitPrice = parseFloat(allotment.unit_value_per_unit);
        let inputValue = parseFloat(value) || 0;

        // Calculate constraints
        const max = calculateMaxAllocation(item);

        // Constrain value
        inputValue = Math.min(inputValue, max.value);

        // Calculate quantity (round down)
        let allocateQty = Math.floor(inputValue / unitPrice);

        // Recalculate value from quantity
        const finalValue = allocateQty * unitPrice;

        setAllocationData(prev => ({
            ...prev,
            [itemId]: {
                qty: allocateQty.toString(),
                cif_fc: finalValue.toFixed(2)
            }
        }));
    }, [availableItems, allotment, calculateMaxAllocation]);

    // Allocate item
    const handleAllocate = async (itemId) => {
        const allocation = allocationData[itemId];
        if (!allocation) return;

        const item = availableItems.find(i => i.id === itemId);
        if (!item) return;

        // Validate
        const validation = allocationCalculator.validateAllocation(
            allocation.qty,
            allocation.cif_fc,
            item,
            allotment
        );

        if (!validation.isValid) {
            setError(validation.errors.join('; '));
            return;
        }

        const result = await execute(`allocate-${itemId}`, async () => {
            return await allotmentApi.allocateItem(allotmentId, itemId, allocation);
        });

        if (result.success) {
            setSuccess('Item allocated successfully');
            // Clear allocation data for this item
            setAllocationData(prev => {
                const newData = {...prev};
                delete newData[itemId];
                return newData;
            });
            // Refresh data
            fetchData(pagination.currentPage);

            // Clear success message after 3 seconds
            setTimeout(() => setSuccess(''), 3000);
        } else {
            setError(result.error);
        }
    };

    // Delete allocation
    const handleDelete = async (allocationId) => {
        const result = await execute(`delete-${allocationId}`, async () => {
            return await allotmentApi.deleteAllocation(allotmentId, allocationId);
        });

        if (result.success) {
            setSuccess('Allocation deleted successfully');
            fetchData(pagination.currentPage);
            setTimeout(() => setSuccess(''), 3000);
        } else {
            setError(result.error);
        }
    };

    // Update allocation
    const handleUpdate = async (allocationId, data) => {
        const result = await execute(`update-${allocationId}`, async () => {
            return await allotmentApi.updateAllocation(allotmentId, allocationId, data);
        });

        if (result.success) {
            setSuccess('Allocation updated successfully');
            fetchData(pagination.currentPage);
            setTimeout(() => setSuccess(''), 3000);
        } else {
            setError(result.error);
        }
    };

    // Update filter
    const updateFilter = useCallback((filterName, value) => {
        setFilters(prev => ({...prev, [filterName]: value}));
    }, []);

    // Clear filters
    const clearFilters = useCallback(() => {
        setFilters({
            description: '',
            exporter: '',
            available_quantity_gte: '50',
            available_quantity_lte: '',
            available_value_gte: '100',
            available_value_lte: '',
            notification_number: '',
            norm_class: '',
            hs_code: '',
            is_expired: 'false'
        });
    }, []);

    return {
        // State
        allotment,
        availableItems,
        allocationData,
        initialLoading,
        tableLoading,
        search,
        filters,
        notificationOptions,
        error,
        success,
        pagination,

        // Actions
        setSearch,
        updateFilter,
        clearFilters,
        handleQuantityChange,
        handleValueChange,
        handleAllocate,
        handleDelete,
        handleUpdate,
        fetchData,
        calculateMaxAllocation,

        // Loading states
        isAllocating: (itemId) => isLoading(`allocate-${itemId}`),
        isDeleting: (allocationId) => isLoading(`delete-${allocationId}`),
        isUpdating: (allocationId) => isLoading(`update-${allocationId}`),

        // Error states
        getAllocationError: (itemId) => getError(`allocate-${itemId}`),
    };
};

export default useAllotmentAction;
