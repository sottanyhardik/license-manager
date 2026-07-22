import { useEffect, useMemo, useState } from "react";
import api from "@/api/axios";
import { useDebouncedFilters } from "@/hooks/useDebounce";
import type { ReportFilterValues } from "./reportQueryString";

export type SelectOption = { value: string; label: string };

/**
 * Encapsulates every filter used by the Item Report and Planned Report
 * pages: state, change handlers, "clear filters", and the shared 500ms
 * debounce wiring that drives when the report actually reloads.
 *
 * Both reports use the exact same filter set (item names, companies,
 * balance thresholds, license status, purchase status, norms,
 * notifications, product description / HSN search, expiry range).
 */
export function useItemReportFilters() {
    const [selectedItemNames, setSelectedItemNames] = useState<unknown[]>([]);
    const [minBalance, setMinBalance] = useState(200);
    const [minAvailQty, setMinAvailQty] = useState(0);
    const [licenseStatus, setLicenseStatus] = useState('active');
    const [selectedCompanies, setSelectedCompanies] = useState<unknown[]>([]);
    const [excludeCompanies, setExcludeCompanies] = useState<unknown[]>([]);
    const [isRestricted, setIsRestricted] = useState('all'); // 'all', 'true', 'false'
    const [purchaseStatus, setPurchaseStatus] = useState(['GE', 'MI', 'SM']); // Default: GE, MI, SM
    const [productDescSearch, setProductDescSearch] = useState('');
    const [hsnCodeSearch, setHsnCodeSearch] = useState('');
    const [selectedNorms, setSelectedNorms] = useState<string[]>([]);
    const [selectedNotifications, setSelectedNotifications] = useState<string[]>([]);
    const [notificationOptions, setNotificationOptions] = useState<SelectOption[]>([]);
    const [expiryDateFrom, setExpiryDateFrom] = useState('');
    const [expiryDateTo, setExpiryDateTo] = useState('');

    useEffect(() => {
        let isMounted = true;

        const fetchNotificationOptions = async () => {
            try {
                const response = await api.get('masters/notification-numbers/', {
                    params: {page_size: 200, ordering: 'code'},
                });
                const results = response.data?.results ?? response.data ?? [];
                if (isMounted) {
                    setNotificationOptions(
                        results.map(({code, label}: {code: string; label?: string}) => ({
                            value: code,
                            label: label ? `${code} — ${label}` : code,
                        }))
                    );
                }
            } catch {
                if (isMounted) {
                    setNotificationOptions([]);
                }
            }
        };

        fetchNotificationOptions();

        return () => {
            isMounted = false;
        };
    }, []);

    // Debounce all filters together - wait 500ms after last change
    const filters: Required<ReportFilterValues> = useMemo(() => ({
        selectedItemNames,
        minBalance,
        minAvailQty,
        licenseStatus,
        selectedCompanies,
        excludeCompanies,
        isRestricted,
        purchaseStatus,
        productDescSearch,
        hsnCodeSearch,
        selectedNorms,
        selectedNotifications,
        expiryDateFrom,
        expiryDateTo,
    }), [selectedItemNames, minBalance, minAvailQty, licenseStatus, selectedCompanies, excludeCompanies, isRestricted, purchaseStatus, productDescSearch, hsnCodeSearch, selectedNorms, selectedNotifications, expiryDateFrom, expiryDateTo]);

    const { debouncedFilters, isPending } = useDebouncedFilters(filters, 500);

    const handleItemNameChange = (values: unknown[] | null) => {
        setSelectedItemNames(values || []);
    };

    const handleCompanyChange = (values: unknown[] | null) => {
        setSelectedCompanies(values || []);
    };

    const handleExcludeCompanyChange = (values: unknown[] | null) => {
        setExcludeCompanies(values || []);
    };

    const handlePurchaseStatusChange = (values: string[] | null) => {
        setPurchaseStatus(values || []);
    };

    const handleNormsChange = (values: string[] | null) => {
        setSelectedNorms(values || []);
    };

    const handleNotificationsChange = (values: string[] | null) => {
        setSelectedNotifications(values || []);
    };

    const handleClearFilters = () => {
        setSelectedItemNames([]);
        setMinBalance(200);
        setMinAvailQty(0);
        setLicenseStatus('active');
        setSelectedCompanies([]);
        setExcludeCompanies([]);
        setIsRestricted('all');
        setPurchaseStatus(['GE', 'MI', 'SM']);
        setProductDescSearch('');
        setHsnCodeSearch('');
        setSelectedNorms([]);
        setSelectedNotifications([]);
        setExpiryDateFrom('');
        setExpiryDateTo('');
    };

    const hasActiveFilters = selectedItemNames.length > 0 || minBalance !== 200 || minAvailQty !== 0 || licenseStatus !== 'active' || selectedCompanies.length > 0 || excludeCompanies.length > 0 || isRestricted !== 'all' || (purchaseStatus.length !== 3 || !purchaseStatus.includes('GE') || !purchaseStatus.includes('MI') || !purchaseStatus.includes('SM')) || productDescSearch !== '' || hsnCodeSearch !== '' || selectedNorms.length > 0 || selectedNotifications.length > 0 || expiryDateFrom !== '' || expiryDateTo !== '';

    // Whether there's enough of a query to actually load/show a report —
    // matches the "select filters to view report" gating used by both pages.
    const hasQuery = selectedItemNames.length > 0 || Boolean(productDescSearch) || Boolean(hsnCodeSearch);

    return {
        // Values
        selectedItemNames,
        minBalance,
        minAvailQty,
        licenseStatus,
        selectedCompanies,
        excludeCompanies,
        isRestricted,
        purchaseStatus,
        productDescSearch,
        hsnCodeSearch,
        selectedNorms,
        selectedNotifications,
        notificationOptions,
        expiryDateFrom,
        expiryDateTo,

        // Setters (for plain-value controls)
        setSelectedItemNames,
        setMinBalance,
        setMinAvailQty,
        setLicenseStatus,
        setIsRestricted,
        setProductDescSearch,
        setHsnCodeSearch,
        setExpiryDateFrom,
        setExpiryDateTo,

        // Change handlers (for react-select / AsyncSelectField controls)
        handleItemNameChange,
        handleCompanyChange,
        handleExcludeCompanyChange,
        handlePurchaseStatusChange,
        handleNormsChange,
        handleNotificationsChange,
        handleClearFilters,

        // Derived
        hasActiveFilters,
        hasQuery,

        // Raw (non-debounced) filters — used for Excel export and the
        // Item Name inline-edit refetch, which both act on the filters as
        // currently displayed rather than the debounced snapshot.
        filters,

        // Debounced filters — drive the actual report GET request.
        debouncedFilters,
        isPending,
    };
}
