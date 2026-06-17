import React, {useEffect, useState, useMemo, useCallback} from "react";
import {useNavigate} from "react-router-dom";
import AsyncSelectField from "../../components/AsyncSelectField";
import ConditionBadge from "../../components/ConditionBadge";
import api from "../../api/axios";
import {formatDate} from "../../utils/dateFormatter";
import {toast} from "sonner";
import Select from "react-select";
import {useDebouncedFilters} from "../../hooks/useDebounce";
import { Button } from "@/components/ui/button";
import { Bell, Building2, CalendarCheck, CalendarDays, CalendarRange, Check, DollarSign, FileSpreadsheet, FileText, Filter, Inbox, Loader2, MinusCircle, Package, Pencil, ScanBarcode, ShieldCheck, ShoppingCart, SlidersHorizontal, Tag, Tags, X, XCircle } from "lucide-react";

export default function ItemReport() {
    const navigate = useNavigate();
    const [reportData, setReportData] = useState<Record<string, any> | null>(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    // Filter states
    const [selectedItemNames, setSelectedItemNames] = useState([]);
    const [availableItems, setAvailableItems] = useState([]);
    const [minBalance, setMinBalance] = useState(200);
    const [minAvailQty, setMinAvailQty] = useState(0);
    const [licenseStatus, setLicenseStatus] = useState('active');
    const [selectedCompanies, setSelectedCompanies] = useState([]);
    const [excludeCompanies, setExcludeCompanies] = useState([]);
    const [isRestricted, setIsRestricted] = useState('all'); // 'all', 'true', 'false'
    const [purchaseStatus, setPurchaseStatus] = useState(['GE', 'MI', 'SM']); // Default: GE, MI, SM
    const [productDescSearch, setProductDescSearch] = useState('');
    const [hsnCodeSearch, setHsnCodeSearch] = useState('');
    const [selectedNorms, setSelectedNorms] = useState([]);
    const [selectedNotifications, setSelectedNotifications] = useState([]);
    const [notificationOptions, setNotificationOptions] = useState([]);
    const [expiryDateFrom, setExpiryDateFrom] = useState('');
    const [expiryDateTo, setExpiryDateTo] = useState('');

    // Inline edit states
    const [editingCell, setEditingCell] = useState(null); // {itemId, field}
    const [editValue, setEditValue] = useState("");

    // Debounce all filters together - wait 500ms after last change
    const filters = useMemo(() => ({
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
        expiryDateTo
    }), [selectedItemNames, minBalance, minAvailQty, licenseStatus, selectedCompanies, excludeCompanies, isRestricted, purchaseStatus, productDescSearch, hsnCodeSearch, selectedNorms, selectedNotifications, expiryDateFrom, expiryDateTo]);

    const { debouncedFilters, isPending } = useDebouncedFilters(filters, 500);

    useEffect(() => {
        let isMounted = true;

        const fetchItems = async () => {
            try {
                const response = await api.get('item-report/available-items/');
                const items = response.data || [];
                if (isMounted) {
                    setAvailableItems(items.map(item => ({value: item.id, label: item.name})));
                }
            } catch (error) {
                console.error('Failed to load available items:', error);
                if (isMounted) {
                    setAvailableItems([]);
                }
            }
        };

        const fetchNotificationOptions = async () => {
            try {
                const response = await api.get('masters/notification-numbers/', {
                    params: {page_size: 200, ordering: 'code'},
                });
                const results = response.data?.results ?? response.data ?? [];
                if (isMounted) {
                    setNotificationOptions(
                        results.map(({code, label}) => ({
                            value: code,
                            label: label ? `${code} — ${label}` : code,
                        }))
                    );
                }
            } catch (error) {
                console.error('Failed to load notification options:', error);
                if (isMounted) {
                    setNotificationOptions([]);
                }
            }
        };

        fetchItems();
        fetchNotificationOptions();

        return () => {
            isMounted = false;
        };
    }, []);

    const loadReport = useCallback(async () => {
        setLoading(true);
        try {
            let url = `reports/item-report/?format=json`;

            // Use debounced filter values
            const {
                selectedItemNames: items,
                selectedCompanies: companies,
                excludeCompanies: excluded,
                minBalance: minBal,
                minAvailQty: minQty,
                licenseStatus: status,
                isRestricted: restricted,
                purchaseStatus: pStatus,
                productDescSearch: prodDesc,
                hsnCodeSearch: hsnCode,
                selectedNorms: norms,
                selectedNotifications: notifications,
                expiryDateFrom: expFrom,
                expiryDateTo: expTo
            } = debouncedFilters;

            if (items.length > 0) {
                url += `&item_names=${items.join(',')}`;
            }

            if (companies.length > 0) {
                url += `&company_ids=${companies.join(',')}`;
            }

            if (excluded.length > 0) {
                url += `&exclude_company_ids=${excluded.join(',')}`;
            }

            url += `&min_balance=${minBal}`;
            url += `&min_avail_qty=${minQty}`;
            url += `&license_status=${status}`;

            if (restricted !== 'all') {
                url += `&is_restricted=${restricted}`;
            }

            if (pStatus.length > 0) {
                url += `&purchase_status=${pStatus.join(',')}`;
            }

            if (prodDesc) {
                url += `&product_description=${encodeURIComponent(prodDesc)}`;
            }

            if (hsnCode) {
                url += `&hsn_code=${encodeURIComponent(hsnCode)}`;
            }

            if (norms.length > 0) {
                url += `&norms=${norms.join(',')}`;
            }

            if (notifications.length > 0) {
                url += `&notification_numbers=${notifications.join(',')}`;
            }

            if (expFrom) url += `&expiry_date_from=${expFrom}`;
            if (expTo) url += `&expiry_date_to=${expTo}`;

            const response = await api.get(url);
            setReportData(response.data);
        } catch (error) {
            toast.error('Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            setLoading(false);
        }
    }, [debouncedFilters]);

    useEffect(() => {
        if (debouncedFilters.selectedItemNames.length > 0 || debouncedFilters.productDescSearch || debouncedFilters.hsnCodeSearch) {
            loadReport();
        } else {
            setReportData(null);
        }
    }, [debouncedFilters, loadReport]);

    const handleExport = async () => {
        setDownloading(true);
        try {
            let url = `reports/item-report/?format=excel`;

            if (selectedItemNames.length > 0) {
                url += `&item_names=${selectedItemNames.join(',')}`;
            }

            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }

            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }

            url += `&min_balance=${minBalance}`;
            url += `&min_avail_qty=${minAvailQty}`;
            url += `&license_status=${licenseStatus}`;

            if (isRestricted !== 'all') {
                url += `&is_restricted=${isRestricted}`;
            }

            if (purchaseStatus.length > 0) {
                url += `&purchase_status=${purchaseStatus.join(',')}`;
            }

            if (productDescSearch) {
                url += `&product_description=${encodeURIComponent(productDescSearch)}`;
            }

            if (hsnCodeSearch) {
                url += `&hsn_code=${encodeURIComponent(hsnCodeSearch)}`;
            }

            if (selectedNorms.length > 0) {
                url += `&norms=${selectedNorms.join(',')}`;
            }

            if (selectedNotifications.length > 0) {
                url += `&notification_numbers=${selectedNotifications.join(',')}`;
            }

            if (expiryDateFrom) url += `&expiry_date_from=${expiryDateFrom}`;
            if (expiryDateTo) url += `&expiry_date_to=${expiryDateTo}`;

            const response = await api.get(url, {
                responseType: 'blob',
            });

            const downloadUrl = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.setAttribute('download', `item_report.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            toast.error('Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    };

    const handleItemNameChange = (values) => {
        setSelectedItemNames(values || []);
    };

    const handleCompanyChange = (values) => {
        setSelectedCompanies(values || []);
    };

    const handleExcludeCompanyChange = (values) => {
        setExcludeCompanies(values || []);
    };

    const handlePurchaseStatusChange = (values) => {
        setPurchaseStatus(values || []);
    };

    const handleNormsChange = (values) => {
        setSelectedNorms(values || []);
    };

    const handleNotificationsChange = (values) => {
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

    // Inline editing handlers
    const startEdit = (itemId, field, currentValue) => {
        setEditingCell({itemId, field});
        setEditValue(currentValue || "");
    };

    const cancelEdit = () => {
        setEditingCell(null);
        setEditValue("");
    };

    const saveEdit = async (item) => {
        if (!editingCell) return;

        const {field} = editingCell;

        try {
            // Update notes or condition_sheet on the license
            const updateData: Record<string, any> = {};
            if (field === 'notes') {
                updateData.balance_report_notes = editValue;
            } else if (field === 'condition_sheet') {
                updateData.condition_sheet = editValue;
            }
            await api.patch(`licenses/${item.license_id}/`, updateData);

            toast.success('Updated successfully');
            cancelEdit();

            // Update only the current row instead of reloading entire report
            const updatedItems = reportData.items.map(i => {
                if (i.id === item.id) {
                    return {
                        ...i,
                        notes: field === 'notes' ? editValue : i.notes,
                        condition_sheet: field === 'condition_sheet' ? editValue : i.condition_sheet
                    };
                }
                return i;
            });

            setReportData({
                ...reportData,
                items: updatedItems
            });
        } catch (error) {
            toast.error('Failed to update. Please try again.');
        }
    };

    const handleItemNamesEdit = async (item, selectedOptions) => {
        try {
            const itemNameIds = selectedOptions ? selectedOptions.map(v => v.value) : [];
            await api.patch(`license-items/${item.id}/`, {
                items: itemNameIds
            });
            toast.success('Item names updated successfully');

            // Fetch updated item data to check if it still matches filters
            let url = `reports/item-report/?format=json`;
            if (selectedItemNames.length > 0) {
                url += `&item_names=${selectedItemNames.join(',')}`;
            }
            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            url += `&min_balance=${minBalance}`;
            url += `&license_status=${licenseStatus}`;
            if (isRestricted !== 'all') {
                url += `&is_restricted=${isRestricted}`;
            }

            const response = await api.get(url);
            const updatedReportData = response.data;

            // Find the updated item in the new data
            const updatedItem = updatedReportData.items.find(i => i.id === item.id);

            if (updatedItem) {
                // Item still matches filters - update the row
                const updatedItems = reportData.items.map(i =>
                    i.id === item.id ? updatedItem : i
                );
                setReportData({
                    ...reportData,
                    items: updatedItems
                });
            } else {
                // Item no longer matches filters - remove it from the list
                const filteredItems = reportData.items.filter(i => i.id !== item.id);
                setReportData({
                    ...reportData,
                    items: filteredItems,
                    total_items: filteredItems.length
                });
                toast.info('Item removed from list as it no longer matches the filters');
            }
        } catch (error) {
            toast.error('Failed to update item names. Please try again.');
        }
    };

    const itemNameOptions = availableItems;

    return (
        <div style={{ minHeight: '100vh', background: 'var(--tb-body-bg)' }}>
            {/* Tabler-style page header */}
            <div className="page-header">
                <div style={{ minWidth: 0 }}>
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span style={{ margin: '0 6px', opacity: 0.5 }}>/</span>
                        Reports
                        <span style={{ margin: '0 6px', opacity: 0.5 }}>/</span>
                        Item Report
                    </div>
                    <h1>Item Report</h1>
                    {reportData && (
                        <div style={{ marginTop: 4, fontSize: 12.5, color: 'var(--tb-text-secondary)' }}>
                            <CalendarDays className="size-4" aria-hidden="true" />
                            {reportData.report_date}
                            <span style={{ margin: '0 8px', opacity: 0.5 }}>•</span>
                            <Package className="size-4" aria-hidden="true" />
                            {reportData.total_items} items
                        </div>
                    )}
                </div>
                <div className="page-actions">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleExport}
                        disabled={downloading || (selectedItemNames.length === 0 && !productDescSearch && !hsnCodeSearch)}
                    >
                        {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                        {downloading ? 'Generating…' : 'Excel'}
                    </Button>
                </div>
            </div>

            {/* Filters Section */}
            <div className="row mb-3">
                <div className="col-span-full">
                    <div className="surface-card">
                        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--tb-border)' }}
                             className="flex justify-between items-center">
                            <h5 className="mb-0" style={{ fontWeight: 600, fontSize: 15 }}>
                                <SlidersHorizontal className="size-4" aria-hidden="true" />
                                Filters
                                {isPending && (
                                    <span className="ms-2" style={{ fontSize: 13.5, color: 'var(--tb-text-secondary)' }}>
                                        <span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                        Updating...
                                    </span>
                                )}
                            </h5>
                            {hasActiveFilters && (
                                <Button variant="outline" size="sm" onClick={handleClearFilters}>
                                    <XCircle className="size-3.5" />
                                    Clear Filters
                                </Button>
                            )}
                        </div>
                        <div style={{ padding: '14px 16px' }}>
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <DollarSign className="size-4" aria-hidden="true" />
                                        Min Balance (CIF)
                                    </label>
                                    <select
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={minBalance}
                                        onChange={(e) => setMinBalance(parseInt(e.target.value))}
                                    >
                                        <option value="100">₹ 100</option>
                                        <option value="200">₹ 200</option>
                                        <option value="500">₹ 500</option>
                                        <option value="1000">₹ 1,000</option>
                                        <option value="5000">₹ 5,000</option>
                                        <option value="10000">₹ 10,000</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <Package className="size-4" aria-hidden="true" />
                                        Min Avail Qty
                                    </label>
                                    <select
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={minAvailQty}
                                        onChange={(e) => setMinAvailQty(parseInt(e.target.value))}
                                    >
                                        <option value="0">0</option>
                                        <option value="100">100</option>
                                        <option value="500">500</option>
                                        <option value="1000">1,000</option>
                                        <option value="5000">5,000</option>
                                        <option value="10000">10,000</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <CalendarCheck className="size-4" aria-hidden="true" />
                                        License Status
                                    </label>
                                    <select
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={licenseStatus}
                                        onChange={(e) => setLicenseStatus(e.target.value)}
                                    >
                                        <option value="active">Active</option>
                                        <option value="expiring_soon">Expiring Soon</option>
                                        <option value="expired">Expired</option>
                                        <option value="all">All</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <CalendarRange className="size-4" aria-hidden="true" />
                                        Expiry Date From
                                    </label>
                                    <input
                                        type="date"
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={expiryDateFrom}
                                        onChange={(e) => setExpiryDateFrom(e.target.value)}
                                    />
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <CalendarRange className="size-4" aria-hidden="true" />
                                        Expiry Date To
                                    </label>
                                    <input
                                        type="date"
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={expiryDateTo}
                                        onChange={(e) => setExpiryDateTo(e.target.value)}
                                    />
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <Building2 className="size-4" aria-hidden="true" />
                                        Include Companies
                                    </label>
                                    <div style={{minHeight: '38px'}}>
                                        <AsyncSelectField
                                            endpoint="masters/companies/"
                                            labelField="name"
                                            valueField="id"
                                            value={selectedCompanies}
                                            onChange={handleCompanyChange}
                                            isMulti={true}
                                            placeholder="All companies..."
                                            loadOnMount={false}
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <MinusCircle className="size-4" aria-hidden="true" />
                                        Exclude Companies
                                    </label>
                                    <div style={{minHeight: '38px'}}>
                                        <AsyncSelectField
                                            endpoint="masters/companies/"
                                            labelField="name"
                                            valueField="id"
                                            value={excludeCompanies}
                                            onChange={handleExcludeCompanyChange}
                                            isMulti={true}
                                            placeholder="None excluded..."
                                            loadOnMount={false}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <ShieldCheck className="size-4" aria-hidden="true" />
                                        Is Restricted
                                    </label>
                                    <select
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={isRestricted}
                                        onChange={(e) => setIsRestricted(e.target.value)}
                                    >
                                        <option value="all">All</option>
                                        <option value="true">Restricted</option>
                                        <option value="false">Not Restricted</option>
                                    </select>
                                </div>

                                <div className="sm:col-span-2">
                                    <label className="form-label font-bold mb-2">
                                        <ShoppingCart className="size-4" aria-hidden="true" />
                                        Purchase Status
                                    </label>
                                    <Select
                                        isMulti
                                        value={[
                                            {value: 'GE', label: 'GE Purchase'},
                                            {value: 'GO', label: 'GE Operating'},
                                            {value: 'SM', label: 'SM Purchase'},
                                            {value: 'MI', label: 'Conversion'},
                                            {value: 'IP', label: 'IP'},
                                            {value: 'CO', label: 'CO'}
                                        ].filter(opt => purchaseStatus.includes(opt.value))}
                                        onChange={(selected) => handlePurchaseStatusChange(selected ? selected.map(s => s.value) : [])}
                                        options={[
                                            {value: 'GE', label: 'GE Purchase'},
                                            {value: 'GO', label: 'GE Operating'},
                                            {value: 'SM', label: 'SM Purchase'},
                                            {value: 'MI', label: 'Conversion'},
                                            {value: 'IP', label: 'IP'},
                                            {value: 'CO', label: 'CO'}
                                        ]}
                                        placeholder="Select purchase status..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <Tags className="size-4" aria-hidden="true" />
                                        Norms
                                    </label>
                                    <Select
                                        isMulti
                                        value={[
                                            {value: 'E1', label: 'E1'},
                                            {value: 'E5', label: 'E5'},
                                            {value: 'E126', label: 'E126'},
                                            {value: 'E132', label: 'E132'}
                                        ].filter(opt => selectedNorms.includes(opt.value))}
                                        onChange={(selected) => handleNormsChange(selected ? selected.map(s => s.value) : [])}
                                        options={[
                                            {value: 'E1', label: 'E1'},
                                            {value: 'E5', label: 'E5'},
                                            {value: 'E126', label: 'E126'},
                                            {value: 'E132', label: 'E132'}
                                        ]}
                                        placeholder="Select norms..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2">
                                        <Bell className="size-4" aria-hidden="true" />
                                        Notification
                                    </label>
                                    <Select
                                        isMulti
                                        value={notificationOptions.filter(opt => selectedNotifications.includes(opt.value))}
                                        onChange={(selected) => handleNotificationsChange(selected ? selected.map(s => s.value) : [])}
                                        options={notificationOptions}
                                        placeholder="Select notification..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>
                            </div>

                            <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                <div className="sm:col-span-full">
                                    <label className="form-label font-bold mb-2">
                                        <FileText className="size-4" aria-hidden="true" />
                                        Product Description
                                    </label>
                                    <input
                                        type="text"
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        placeholder="Search by product description..."
                                        value={productDescSearch}
                                        onChange={(e) => setProductDescSearch(e.target.value)}
                                    />
                                </div>
                                <div className="sm:col-span-full">
                                    <label className="form-label font-bold mb-2">
                                        <ScanBarcode className="size-4" aria-hidden="true" />
                                        HSN Code
                                    </label>
                                    <input
                                        type="text"
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        placeholder="Search by HSN code..."
                                        value={hsnCodeSearch}
                                        onChange={(e) => setHsnCodeSearch(e.target.value)}
                                    />
                                </div>
                            </div>

                            <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                <div className="col-span-full">
                                    <label className="form-label font-bold mb-2">
                                        <Tag className="size-4" aria-hidden="true" />
                                        Filter by Item Name (Multi-select)
                                    </label>
                                    <Select
                                        isMulti
                                        value={itemNameOptions.filter(opt => selectedItemNames.includes(opt.value))}
                                        onChange={(selected) => handleItemNameChange(selected ? selected.map(s => s.value) : [])}
                                        options={itemNameOptions}
                                        placeholder="Select item names..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>
                            </div>

                            {hasActiveFilters && (
                                <div className="mt-3">
                                    <div
                                        className="alert alert-info flex justify-between items-center py-2 mb-0">
                                        <div>
                                            <Filter className="size-4" aria-hidden="true" />
                                            <strong>Active Filters:</strong>
                                            {minBalance !== 200 && <span className="chip chip-primary ml-2">Min Balance: ₹{minBalance}</span>}
                                            {minAvailQty !== 0 && <span className="chip chip-primary ml-2">Min Qty: {minAvailQty}</span>}
                                            {licenseStatus !== 'active' && <span
                                                className="badge bg-primary ml-2">Status: {licenseStatus.replace('_', ' ')}</span>}
                                            {selectedCompanies.length > 0 && <span className="chip chip-primary ml-2">Incl. Companies: {selectedCompanies.length}</span>}
                                            {excludeCompanies.length > 0 && <span className="chip chip-primary ml-2">Excl. Companies: {excludeCompanies.length}</span>}
                                            {isRestricted !== 'all' && <span className="chip chip-primary ml-2">Is Restricted: {isRestricted === 'true' ? 'Yes' : 'No'}</span>}
                                            {purchaseStatus.length > 0 && purchaseStatus.length < 6 && <span className="chip chip-primary ml-2">Purchase Status: {purchaseStatus.length}</span>}
                                            {selectedItemNames.length > 0 && <span className="chip chip-primary ml-2">Item Names: {selectedItemNames.length}</span>}
                                            {productDescSearch !== '' && <span className="chip chip-primary ml-2">Product Desc: "{productDescSearch}"</span>}
                                            {hsnCodeSearch !== '' && <span className="chip chip-primary ml-2">HSN Code: "{hsnCodeSearch}"</span>}
                                            {selectedNorms.length > 0 && <span className="chip chip-primary ml-2">Norms: {selectedNorms.length}</span>}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Sticky Totals Bar */}
            {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length > 0 && (
                <div className="row mb-3">
                    <div className="col-span-full">
                        <div className="card" style={{
                            position: 'sticky',
                            top: '70px',
                            zIndex: 1020
                        }}>
                            <div className="card-body py-2">
                                <div className="flex justify-end items-center gap-4">
                                    <div className="font-bold">Total:</div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted small">Avail Qty:</span>
                                        <span className="font-bold">
                                            {reportData.items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toLocaleString('en-IN', {
                                                minimumFractionDigits: 3,
                                                maximumFractionDigits: 3
                                            })}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted small">Avail Bal:</span>
                                        <span className="font-bold text-success">
                                            {(() => {
                                                const uniqueLicenses: Record<string, number> = {};
                                                reportData.items.forEach((item: any) => {
                                                    if (!uniqueLicenses[item.license_id]) {
                                                        uniqueLicenses[item.license_id] = item.available_balance || 0;
                                                    }
                                                });
                                                return Object.values(uniqueLicenses).reduce((sum: number, val: number) => sum + val, 0).toLocaleString('en-IN', {
                                                    minimumFractionDigits: 2,
                                                    maximumFractionDigits: 2
                                                });
                                            })()}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted small">Balance CIF:</span>
                                        <span className="font-bold text-primary">
                                            {(() => {
                                                const uniqueLicenses: Record<string, number> = {};
                                                reportData.items.forEach((item: any) => {
                                                    if (!uniqueLicenses[item.license_id]) {
                                                        uniqueLicenses[item.license_id] = item.balance_cif || 0;
                                                    }
                                                });
                                                return Object.values(uniqueLicenses).reduce((sum: number, val: number) => sum + val, 0).toLocaleString('en-IN', {
                                                    minimumFractionDigits: 2,
                                                    maximumFractionDigits: 2
                                                });
                                            })()}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Report Table */}
            <div className="row">
                <div className="col-span-full">
                    {loading && (
                        <div className="card">
                            <div className="card-body flex flex-col items-center py-12 text-center">
                                <Loader2 className="mb-3 size-10 animate-spin text-primary" />
                                <h5 className="text-muted">Loading Item Report…</h5>
                                <p className="text-muted small">Please wait while we fetch the data</p>
                            </div>
                        </div>
                    )}

                    {!loading && selectedItemNames.length === 0 && !productDescSearch && !hsnCodeSearch && (
                        <div className="card">
                            <div className="card-body text-center py-5">
                                <Tag className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-primary">Select Filters to View Report</h5>
                                <p className="text-muted">Please select item names, search by product description, or search by HSN code to load the report data</p>
                            </div>
                        </div>
                    )}

                    {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length === 0 && (
                        <div className="card">
                            <div className="card-body text-center py-5">
                                <Inbox className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-muted-foreground">No items found</h5>
                                <p className="text-muted">Try adjusting your filters to see more results.</p>
                                <div className="mt-3 text-start" style={{maxWidth: '600px', margin: '0 auto'}}>
                                    <p className="small text-muted-foreground mb-2"><strong>Tip:</strong> When searching by Product Description or HSN Code, consider:</p>
                                    <ul className="small text-muted-foreground">
                                        <li>Setting License Status to "All"</li>
                                        <li>Lowering the Min Balance (CIF) to 100</li>
                                        <li>Checking if your search term matches exactly (case-insensitive partial match)</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}

                    {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length > 0 && (
                        <div className="card">
                            <div className="card-body" style={{padding:0}}>
                                <div className="table-responsive" style={{overflowX: 'auto'}}>
                                    <table className="table table-hover table-sm mb-0"
                                           style={{tableLayout: 'auto', minWidth: '1400px'}}>
                                        <thead style={{position: 'sticky', top: 0, zIndex: 10}}>
                                        <tr className="table-light">
                                            <th className="text-center" style={{
                                                position: 'sticky',
                                                left: 0,
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '60px'
                                            }}>Sr No
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '60px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '150px'
                                            }}>License No
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '210px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '120px'
                                            }}>License Date
                                            </th>
                                            <th style={{
                                                position: 'sticky',
                                                left: '330px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '140px',
                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                borderRight: '2px solid var(--tb-border)'
                                            }}>Expiry Date
                                            </th>
                                            <th style={{minWidth: '200px'}}>Exporter Name</th>
                                            <th style={{minWidth: '100px'}}>Serial No</th>
                                            <th style={{minWidth: '100px'}}>HSN Code</th>
                                            <th style={{minWidth: '250px'}}>Product Description</th>
                                            <th style={{minWidth: '200px'}}>Item Name</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Avail Qty</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Avail Bal</th>
                                            <th className="text-end" style={{minWidth: '140px'}}>Balance CIF</th>
                                            <th className="text-center" style={{minWidth: '120px'}}>Is Restricted</th>
                                            <th style={{minWidth: '200px'}}>Notes</th>
                                            <th style={{minWidth: '200px'}}>Condition Sheet</th>
                                            <th style={{minWidth: '250px'}}>Transfer Status</th>
                                        </tr>
                                        </thead>
                                        <tbody>
                                        {(() => {
                                            // Group items by license_id
                                            const groupedByLicense = {};
                                            reportData.items.forEach(item => {
                                                if (!groupedByLicense[item.license_id]) {
                                                    groupedByLicense[item.license_id] = [];
                                                }
                                                groupedByLicense[item.license_id].push(item);
                                            });

                                            let srNo = 0;
                                            return Object.values(groupedByLicense as Record<string, any[]>).map((licenseItems: any[]) => {
                                                const firstItem = licenseItems[0];
                                                const rowSpan = licenseItems.length;

                                                return licenseItems.map((item, itemIdx) => {
                                                    srNo++;
                                                    const isFirstRow = itemIdx === 0;

                                                    return (
                                                        <tr key={item.id} style={{
                                                            borderBottom: itemIdx === licenseItems.length - 1 ? '2px solid var(--tb-border)' : '',
                                                            verticalAlign: 'middle'
                                                        }}>
                                                            {isFirstRow && (
                                                                <>
                                                                    <td className="text-center" rowSpan={rowSpan}
                                                                        style={{
                                                                            position: 'sticky',
                                                                            left: 0,
                                                                            zIndex: 9,
                                                                            verticalAlign: 'middle',
                                                                            backgroundColor: 'var(--tb-sunken)',
                                                                            fontWeight: '500'
                                                                        }}>{srNo - itemIdx}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '60px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)',
                                                                        fontWeight: '600'
                                                                    }}>
                                                                        <div
                                                                            className="flex items-center justify-between">
                                                                            <span>{firstItem.license_number}</span>
                                                                            <button
                                                                                className="ml-2 flex items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                                                style={{
                                                                                    padding: '2px 8px',
                                                                                    fontSize: 12
                                                                                }}
                                                                                onClick={() => {
                                                                                    window.open(`/api/licenses/${firstItem.license_id}/merged-documents/`, '_blank');
                                                                                }}
                                                                                title="View/Download merged documents"
                                                                            >
                                                                                Docs
                                                                            </button>
                                                                        </div>
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '210px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)'
                                                                    }}>{formatDate(firstItem.license_date)}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        position: 'sticky',
                                                                        left: '330px',
                                                                        zIndex: 9,
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)',
                                                                        boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                                        borderRight: '2px solid var(--tb-border)'
                                                                    }}>{formatDate(firstItem.license_expiry_date)}</td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)'
                                                                    }}>{firstItem.exporter_name || '-'}</td>
                                                                </>
                                                            )}
                                                            <td className="text-center"
                                                                style={{verticalAlign: 'middle'}}>
                                                                {item.serial_number}
                                                                <ConditionBadge type={item.condition_type} size="xs" />
                                                            </td>
                                                            <td style={{verticalAlign: 'middle'}}>{item.hs_code || '-'}</td>
                                                            <td style={{verticalAlign: 'middle'}}>{item.product_description || '-'}</td>
                                                            <td>
                                                                <Select
                                                                    isMulti
                                                                    value={(item.item_names || []).map(i => ({
                                                                        value: i.id,
                                                                        label: i.name
                                                                    }))}
                                                                    onChange={(selected) => handleItemNamesEdit(item, selected)}
                                                                    options={itemNameOptions}
                                                                    placeholder="Select item names..."
                                                                    className="basic-multi-select"
                                                                    classNamePrefix="select"
                                                                    styles={{
                                                                        control: (base) => ({
                                                                            ...base,
                                                                            minHeight: '32px',
                                                                            fontSize: 14
                                                                        })
                                                                    }}
                                                                />
                                                            </td>
                                                            <td className="text-end">{Number(item.available_quantity || 0).toFixed(3)}</td>
                                                            {isFirstRow && (
                                                                <>
                                                                    <td className="text-end text-success font-semibold"
                                                                        rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)'
                                                                    }}>{Number(firstItem.available_balance || 0).toFixed(2)}</td>
                                                                    <td className="text-end text-primary font-semibold"
                                                                        rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)'
                                                                    }}>{Number(firstItem.balance_cif || 0).toFixed(2)}</td>
                                                                    <td className="text-center" rowSpan={rowSpan}
                                                                        style={{
                                                                            verticalAlign: 'middle',
                                                                            backgroundColor: 'var(--tb-sunken)'
                                                                        }}>
                                                                        {/* Restriction is derived from condition_type (licence's
                                                                            condition sheet) — read-only display. */}
                                                                        {firstItem.condition_type
                                                                            ? <ConditionBadge type={firstItem.condition_type} />
                                                                            : <span className="badge bg-success">
                                                                                  <ShieldCheck className="size-4" aria-hidden="true" />Open
                                                                              </span>}
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)'
                                                                    }}>
                                                                        {editingCell?.itemId === firstItem.id && editingCell?.field === 'notes' ? (
                                                                            <div className="flex gap-1">
                                                                                <input
                                                                                    type="text"
                                                                                    className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                                                    value={editValue}
                                                                                    onChange={(e) => setEditValue(e.target.value)}
                                                                                    autoFocus
                                                                                />
                                                                                <button
                                                                                    className="flex items-center gap-1.5 rounded bg-success px-2 py-1 text-xs font-medium text-white cursor-pointer"
                                                                                    onClick={() => saveEdit(firstItem)}
                                                                                >
                                                                                    <Check className="size-4" aria-hidden="true" />
                                                                                </button>
                                                                                <button
                                                                                    className="flex items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                                                    onClick={cancelEdit}
                                                                                >
                                                                                    <X className="size-4" aria-hidden="true" />
                                                                                </button>
                                                                            </div>
                                                                        ) : (
                                                                            <div
                                                                                className="flex items-center justify-between"
                                                                                style={{cursor: 'pointer'}}
                                                                                onClick={() => startEdit(firstItem.id, 'notes', firstItem.notes)}
                                                                            >
                                                                                <span>{firstItem.notes || '-'}</span>
                                                                                <Pencil className="size-4" aria-hidden="true" />
                                                                            </div>
                                                                        )}
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)'
                                                                    }}>
                                                                        {editingCell?.itemId === firstItem.id && editingCell?.field === 'condition_sheet' ? (
                                                                            <div className="flex gap-1">
                                                                                <input
                                                                                    type="text"
                                                                                    className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                                                    value={editValue}
                                                                                    onChange={(e) => setEditValue(e.target.value)}
                                                                                    autoFocus
                                                                                />
                                                                                <button
                                                                                    className="flex items-center gap-1.5 rounded bg-success px-2 py-1 text-xs font-medium text-white cursor-pointer"
                                                                                    onClick={() => saveEdit(firstItem)}
                                                                                >
                                                                                    <Check className="size-4" aria-hidden="true" />
                                                                                </button>
                                                                                <button
                                                                                    className="flex items-center gap-1.5 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                                                    onClick={cancelEdit}
                                                                                >
                                                                                    <X className="size-4" aria-hidden="true" />
                                                                                </button>
                                                                            </div>
                                                                        ) : (
                                                                            <div
                                                                                className="flex items-center justify-between"
                                                                                style={{cursor: 'pointer'}}
                                                                                onClick={() => startEdit(firstItem.id, 'condition_sheet', firstItem.condition_sheet)}
                                                                            >
                                                                                <span>{firstItem.condition_sheet || '-'}</span>
                                                                                <Pencil className="size-4" aria-hidden="true" />
                                                                            </div>
                                                                        )}
                                                                    </td>
                                                                    <td rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)',
                                                                        fontSize: 13.5,
                                                                        lineHeight: '1.4'
                                                                    }}>
                                                                        {firstItem.latest_transfer ? (
                                                                            <div>{firstItem.latest_transfer}</div>
                                                                        ) : (
                                                                            <span className="text-muted">-</span>
                                                                        )}
                                                                    </td>
                                                                </>
                                                            )}
                                                        </tr>
                                                    );
                                                });
                                            });
                                        })()}
                                        </tbody>
                                        <tfoot style={{position: 'sticky', bottom: 0, zIndex: 10}}>
                                        <tr className="table-secondary font-bold">
                                            <td colSpan={10} className="text-end" style={{
                                                position: 'sticky',
                                                left: 0,
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-border)',
                                                fontWeight: '600'
                                            }}>
                                                Total:
                                            </td>
                                            <td className="text-end" style={{fontWeight: '600'}}>
                                                {reportData.items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toFixed(3)}
                                            </td>
                                            <td className="text-end text-success" style={{fontWeight: '600'}}>
                                                {(() => {
                                                    // Calculate unique license balance total (don't double count licenses with multiple items)
                                                    const uniqueLicenses: Record<string, number> = {};
                                                    reportData.items.forEach((item: any) => {
                                                        if (!uniqueLicenses[item.license_id]) {
                                                            uniqueLicenses[item.license_id] = item.available_balance || 0;
                                                        }
                                                    });
                                                    return Object.values(uniqueLicenses).reduce((sum: number, val: number) => sum + val, 0).toFixed(2);
                                                })()}
                                            </td>
                                            <td colSpan={4}></td>
                                        </tr>
                                        </tfoot>
                                    </table>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
