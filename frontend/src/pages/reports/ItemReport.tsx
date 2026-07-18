import React, {useEffect, useState, useMemo, useCallback, useId} from "react";
import {useNavigate} from "react-router-dom";
import AsyncSelectField from "../../components/AsyncSelectField";
import { Card, CardContent } from "@/components/ui/card";
import ConditionBadge from "../../components/ConditionBadge";
import api from "../../api/axios";
import { openAuthedFile } from "../../utils/documentDownload";
import {formatDate} from "../../utils/dateFormatter";
import {clickable} from "../../utils/clickable";
import {toast} from "sonner";
import Select from "react-select";
import {useDebouncedFilters} from "../../hooks/useDebounce";
import { Button } from "@/components/ui/button";
import { Bell, Building2, CalendarCheck, CalendarDays, CalendarRange, Check, DollarSign, FileSpreadsheet, FileText, Filter, Inbox, Loader2, MinusCircle, Package, Pencil, ScanBarcode, ShieldCheck, ShoppingCart, SlidersHorizontal, Tag, Tags, X, XCircle } from "lucide-react";

type ItemReportPathOptions = {
    format: "json" | "excel";
    selectedItemNames?: unknown[];
    selectedCompanies?: unknown[];
    excludeCompanies?: unknown[];
    minBalance?: unknown;
    minAvailQty?: unknown;
    licenseStatus?: unknown;
    isRestricted?: unknown;
    purchaseStatus?: unknown[];
    productDescSearch?: unknown;
    hsnCodeSearch?: unknown;
    selectedNorms?: unknown[];
    selectedNotifications?: unknown[];
    expiryDateFrom?: unknown;
    expiryDateTo?: unknown;
};

const PURCHASE_STATUS_OPTIONS = [
    {value: 'GE', label: 'GE Purchase'},
    {value: 'GO', label: 'GE Operating'},
    {value: 'SM', label: 'SM Purchase'},
    {value: 'MI', label: 'Conversion'},
    {value: 'IP', label: 'IP'},
    {value: 'CO', label: 'CO'}
];

const NORM_OPTIONS = [
    {value: 'E1', label: 'E1'},
    {value: 'E5', label: 'E5'},
    {value: 'E126', label: 'E126'},
    {value: 'E132', label: 'E132'}
];

export function normalizeReportNumber(value: unknown, fallback = 0): number {
    const parsed = Number.parseInt(String(value ?? ""), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
}

export function normalizeFilterValues(values?: unknown[]): string[] {
    if (!Array.isArray(values)) {
        return [];
    }

    return values
        .map((value) => String(value ?? "").trim())
        .filter(Boolean);
}

export function buildItemReportPath({
    format,
    selectedItemNames = [],
    selectedCompanies = [],
    excludeCompanies = [],
    minBalance = 200,
    minAvailQty = 0,
    licenseStatus = "active",
    isRestricted = "all",
    purchaseStatus = [],
    productDescSearch,
    hsnCodeSearch,
    selectedNorms = [],
    selectedNotifications = [],
    expiryDateFrom,
    expiryDateTo,
}: ItemReportPathOptions): string {
    const params = new URLSearchParams({format});
    const itemNames = normalizeFilterValues(selectedItemNames);
    const companyIds = normalizeFilterValues(selectedCompanies);
    const excludedCompanyIds = normalizeFilterValues(excludeCompanies);
    const purchaseStatuses = normalizeFilterValues(purchaseStatus);
    const norms = normalizeFilterValues(selectedNorms);
    const notifications = normalizeFilterValues(selectedNotifications);
    const productDescription = String(productDescSearch ?? "").trim();
    const hsnCode = String(hsnCodeSearch ?? "").trim();
    const restricted = String(isRestricted ?? "all").trim();
    const expiryFrom = String(expiryDateFrom ?? "").trim();
    const expiryTo = String(expiryDateTo ?? "").trim();

    if (itemNames.length > 0) params.set("item_names", itemNames.join(","));
    if (companyIds.length > 0) params.set("company_ids", companyIds.join(","));
    if (excludedCompanyIds.length > 0) params.set("exclude_company_ids", excludedCompanyIds.join(","));
    params.set("min_balance", String(normalizeReportNumber(minBalance, 200)));
    params.set("min_avail_qty", String(normalizeReportNumber(minAvailQty, 0)));
    params.set("license_status", String(licenseStatus || "active"));
    if (restricted && restricted !== "all") params.set("is_restricted", restricted);
    if (purchaseStatuses.length > 0) params.set("purchase_status", purchaseStatuses.join(","));
    if (productDescription) params.set("product_description", productDescription);
    if (hsnCode) params.set("hsn_code", hsnCode);
    if (norms.length > 0) params.set("norms", norms.join(","));
    if (notifications.length > 0) params.set("notification_numbers", notifications.join(","));
    if (expiryFrom) params.set("expiry_date_from", expiryFrom);
    if (expiryTo) params.set("expiry_date_to", expiryTo);

    return `reports/item-report/?${params.toString()}`;
}

export default function ItemReport() {
    const navigate = useNavigate();
    const minBalanceId = useId();
    const minAvailQtyId = useId();
    const licenseStatusId = useId();
    const expiryDateFromId = useId();
    const expiryDateToId = useId();
    const purchaseStatusId = useId();
    const normsId = useId();
    const notificationId = useId();
    const restrictedId = useId();
    const productDescriptionId = useId();
    const hsnCodeId = useId();
    const itemNameFilterId = useId();
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
            } catch {
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
            } catch {
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

            const response = await api.get(buildItemReportPath({
                format: "json",
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
                expiryDateTo: expTo,
            }));
            setReportData(response.data);
        } catch {
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
            await openAuthedFile(buildItemReportPath({
                format: "excel",
                selectedItemNames,
                selectedCompanies,
                excludeCompanies,
                minBalance,
                minAvailQty,
                licenseStatus,
                isRestricted,
                purchaseStatus,
                productDescSearch,
                hsnCodeSearch,
                selectedNorms,
                selectedNotifications,
                expiryDateFrom,
                expiryDateTo,
            }), "item_report.xlsx");
        } catch {
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
        } catch {
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
            const response = await api.get(buildItemReportPath({
                format: "json",
                selectedItemNames,
                selectedCompanies,
                excludeCompanies,
                minBalance,
                minAvailQty,
                licenseStatus,
                isRestricted,
                purchaseStatus,
                productDescSearch,
                hsnCodeSearch,
                selectedNorms,
                selectedNotifications,
                expiryDateFrom,
                expiryDateTo,
            }));
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
        } catch {
            toast.error('Failed to update item names. Please try again.');
        }
    };

    const itemNameOptions = availableItems;

    return (
        <div className="min-h-screen bg-background">
            {/* Tabler-style page header */}
            <div className="page-header">
                <div className="min-w-0">
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span className="mx-1.5 opacity-50">/</span>
                        Reports
                        <span className="mx-1.5 opacity-50">/</span>
                        Item Report
                    </div>
                    <h1>Item Report</h1>
                    {reportData && (
                        <div className="mt-1 flex items-center gap-1 text-[12.5px] text-muted-foreground">
                            <CalendarDays className="size-3.5" aria-hidden="true" />
                            {reportData.report_date}
                            <span className="mx-2 opacity-50">•</span>
                            <Package className="size-3.5" aria-hidden="true" />
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
                        <div className="flex items-center justify-between border-b border-border px-4 py-3.5">
                            <h5 className="mb-0 flex items-center gap-1.5 text-[15px] font-semibold">
                                <SlidersHorizontal className="size-4" aria-hidden="true" />
                                Filters
                                {isPending && (
                                    <span className="ml-2 flex items-center gap-1 text-[13.5px] text-muted-foreground">
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
                                    <label className="form-label font-bold mb-2" htmlFor={minBalanceId}>
                                        <DollarSign className="size-4" aria-hidden="true" />
                                        Min Balance (CIF)
                                    </label>
                                    <select
                                        id={minBalanceId}
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={minBalance}
                                        onChange={(e) => setMinBalance(normalizeReportNumber(e.target.value, minBalance))}
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
                                    <label className="form-label font-bold mb-2" htmlFor={minAvailQtyId}>
                                        <Package className="size-4" aria-hidden="true" />
                                        Min Avail Qty
                                    </label>
                                    <select
                                        id={minAvailQtyId}
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={minAvailQty}
                                        onChange={(e) => setMinAvailQty(normalizeReportNumber(e.target.value, minAvailQty))}
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
                                    <label className="form-label font-bold mb-2" htmlFor={licenseStatusId}>
                                        <CalendarCheck className="size-4" aria-hidden="true" />
                                        License Status
                                    </label>
                                    <select
                                        id={licenseStatusId}
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
                                    <label className="form-label font-bold mb-2" htmlFor={expiryDateFromId}>
                                        <CalendarRange className="size-4" aria-hidden="true" />
                                        Expiry Date From
                                    </label>
                                    <input
                                        id={expiryDateFromId}
                                        type="date"
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        value={expiryDateFrom}
                                        onChange={(e) => setExpiryDateFrom(e.target.value)}
                                    />
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2" htmlFor={expiryDateToId}>
                                        <CalendarRange className="size-4" aria-hidden="true" />
                                        Expiry Date To
                                    </label>
                                    <input
                                        id={expiryDateToId}
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
                                    <label className="form-label font-bold mb-2" htmlFor={restrictedId}>
                                        <ShieldCheck className="size-4" aria-hidden="true" />
                                        Is Restricted
                                    </label>
                                    <select
                                        id={restrictedId}
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
                                    <label className="form-label font-bold mb-2" htmlFor={purchaseStatusId}>
                                        <ShoppingCart className="size-4" aria-hidden="true" />
                                        Purchase Status
                                    </label>
                                    <Select
                                        inputId={purchaseStatusId}
                                        isMulti
                                        value={PURCHASE_STATUS_OPTIONS.filter(opt => purchaseStatus.includes(opt.value))}
                                        onChange={(selected) => handlePurchaseStatusChange(selected ? selected.map(s => s.value) : [])}
                                        options={PURCHASE_STATUS_OPTIONS}
                                        placeholder="Select purchase status..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2" htmlFor={normsId}>
                                        <Tags className="size-4" aria-hidden="true" />
                                        Norms
                                    </label>
                                    <Select
                                        inputId={normsId}
                                        isMulti
                                        value={NORM_OPTIONS.filter(opt => selectedNorms.includes(opt.value))}
                                        onChange={(selected) => handleNormsChange(selected ? selected.map(s => s.value) : [])}
                                        options={NORM_OPTIONS}
                                        placeholder="Select norms..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>

                                <div>
                                    <label className="form-label font-bold mb-2" htmlFor={notificationId}>
                                        <Bell className="size-4" aria-hidden="true" />
                                        Notification
                                    </label>
                                    <Select
                                        inputId={notificationId}
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
                                    <label className="form-label font-bold mb-2" htmlFor={productDescriptionId}>
                                        <FileText className="size-4" aria-hidden="true" />
                                        Product Description
                                    </label>
                                    <input
                                        id={productDescriptionId}
                                        type="text"
                                        className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                        placeholder="Search by product description..."
                                        value={productDescSearch}
                                        onChange={(e) => setProductDescSearch(e.target.value)}
                                    />
                                </div>
                                <div className="sm:col-span-full">
                                    <label className="form-label font-bold mb-2" htmlFor={hsnCodeId}>
                                        <ScanBarcode className="size-4" aria-hidden="true" />
                                        HSN Code
                                    </label>
                                    <input
                                        id={hsnCodeId}
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
                                    <label className="form-label font-bold mb-2" htmlFor={itemNameFilterId}>
                                        <Tag className="size-4" aria-hidden="true" />
                                        Filter by Item Name (Multi-select)
                                    </label>
                                    <Select
                                        inputId={itemNameFilterId}
                                        isMulti
                                        value={itemNameOptions.filter(opt => selectedItemNames.includes(opt.value))}
                                        onChange={(selected) => handleItemNameChange(selected ? selected.map(s => s.value) : [])}
                                        options={itemNameOptions}
                                        placeholder="Select item names..."
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                        // Portal the menu to <body> so it isn't clipped/hidden behind the
                                        // report card below the filter panel.
                                        menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
                                        menuPosition="fixed"
                                        styles={{ menuPortal: (base) => ({ ...base, zIndex: 9999 }) }}
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
                        <Card style={{ position: 'sticky', top: '70px', zIndex: 1020 }}>
                            <CardContent className="py-2">
                                <div className="flex justify-end items-center gap-4">
                                    <div className="font-bold">Total:</div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted-foreground text-sm">Avail Qty:</span>
                                        <span className="font-bold">
                                            {reportData.items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toLocaleString('en-IN', {
                                                minimumFractionDigits: 3,
                                                maximumFractionDigits: 3
                                            })}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-muted-foreground text-sm">Avail Bal:</span>
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
                                        <span className="text-muted-foreground text-sm">Balance CIF:</span>
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
                            </CardContent>
                        </Card>
                    </div>
                </div>
            )}

            {/* Report Table */}
            <div className="row">
                <div className="col-span-full">
                    {loading && (
                        <Card>
                            <CardContent className="flex flex-col items-center py-12 text-center">
                                <Loader2 className="mb-3 size-10 animate-spin text-primary" />
                                <h5 className="text-muted-foreground">Loading Item Report…</h5>
                                <p className="text-muted-foreground text-sm">Please wait while we fetch the data</p>
                            </CardContent>
                        </Card>
                    )}

                    {!loading && selectedItemNames.length === 0 && !productDescSearch && !hsnCodeSearch && (
                        <Card>
                            <CardContent className="py-5 text-center">
                                <Tag className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-primary">Select Filters to View Report</h5>
                                <p className="text-muted-foreground">Please select item names, search by product description, or search by HSN code to load the report data</p>
                            </CardContent>
                        </Card>
                    )}

                    {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length === 0 && (
                        <Card>
                            <CardContent className="py-5 text-center">
                                <Inbox className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-muted-foreground">No items found</h5>
                                <p className="text-muted-foreground">Try adjusting your filters to see more results.</p>
                                <div className="mt-3 text-left" style={{maxWidth: '600px', margin: '0 auto'}}>
                                    <p className="text-sm text-muted-foreground mb-2"><strong>Tip:</strong> When searching by Product Description or HSN Code, consider:</p>
                                    <ul className="text-sm text-muted-foreground">
                                        <li>Setting License Status to "All"</li>
                                        <li>Lowering the Min Balance (CIF) to 100</li>
                                        <li>Checking if your search term matches exactly (case-insensitive partial match)</li>
                                    </ul>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {!loading && (selectedItemNames.length > 0 || productDescSearch || hsnCodeSearch) && reportData && reportData.items.length > 0 && (
                        <Card>
                            <CardContent className="p-0">
                                <div className="overflow-x-auto">
                                    <table className="table table-hover table-sm mb-0"
                                           style={{tableLayout: 'auto', minWidth: '1400px'}}>
                                        <thead style={{position: 'sticky', top: 0, zIndex: 10}}>
                                        <tr className="table-light">
                                            <th scope="col" className="text-center" style={{
                                                position: 'sticky',
                                                left: 0,
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '60px'
                                            }}>Sr No
                                            </th>
                                            <th scope="col" style={{
                                                position: 'sticky',
                                                left: '60px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '150px'
                                            }}>License No
                                            </th>
                                            <th scope="col" style={{
                                                position: 'sticky',
                                                left: '210px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '120px'
                                            }}>License Date
                                            </th>
                                            <th scope="col" style={{
                                                position: 'sticky',
                                                left: '330px',
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-sunken)',
                                                minWidth: '140px',
                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                borderRight: '2px solid var(--tb-border)'
                                            }}>Expiry Date
                                            </th>
                                            <th scope="col" style={{minWidth: '200px'}}>Exporter Name</th>
                                            <th scope="col" style={{minWidth: '100px'}}>Serial No</th>
                                            <th scope="col" style={{minWidth: '100px'}}>HSN Code</th>
                                            <th scope="col" style={{minWidth: '250px'}}>Product Description</th>
                                            <th scope="col" style={{minWidth: '200px'}}>Item Name</th>
                                            <th scope="col" className="text-right" style={{minWidth: '140px'}}>Avail Qty</th>
                                            <th scope="col" className="text-right" style={{minWidth: '120px'}}>Plan Qty</th>
                                            <th scope="col" className="text-right" style={{minWidth: '120px'}}>Plan CIF</th>
                                            <th scope="col" className="text-right" style={{minWidth: '140px'}}>Avail Bal</th>
                                            <th scope="col" className="text-right" style={{minWidth: '140px'}}>Balance CIF</th>
                                            <th scope="col" className="text-center" style={{minWidth: '120px'}}>Is Restricted</th>
                                            <th scope="col" style={{minWidth: '200px'}}>Notes</th>
                                            <th scope="col" style={{minWidth: '200px'}}>Condition Sheet</th>
                                            <th scope="col" style={{minWidth: '250px'}}>Transfer Status</th>
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
                                                                                    openAuthedFile(`licenses/${firstItem.license_id}/merged-documents/`);
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
                                                            <td className="text-right">{Number(item.available_quantity || 0).toFixed(3)}</td>
                                                            <td className="text-right" title={(item.planned_splits || []).map(s => `${s.item_name || '—'}: ${Number(s.planned_quantity).toFixed(3)} @ ${Number(s.unit_price).toFixed(2)} = ${Number(s.planned_cif_fc).toFixed(2)}`).join('\n')}>
                                                                {Number(item.planned_quantity || 0) > 0 ? Number(item.planned_quantity).toFixed(3) : '-'}
                                                            </td>
                                                            <td className="text-right">
                                                                {Number(item.planned_cif || 0) > 0 ? Number(item.planned_cif).toFixed(2) : '-'}
                                                            </td>
                                                            {isFirstRow && (
                                                                <>
                                                                    <td className="text-right text-success font-semibold"
                                                                        rowSpan={rowSpan} style={{
                                                                        verticalAlign: 'middle',
                                                                        backgroundColor: 'var(--tb-sunken)'
                                                                    }}>{Number(firstItem.available_balance || 0).toFixed(2)}</td>
                                                                    <td className="text-right text-primary font-semibold"
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
                                                                                {...clickable(() => startEdit(firstItem.id, 'notes', firstItem.notes))}
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
                                                                                {...clickable(() => startEdit(firstItem.id, 'condition_sheet', firstItem.condition_sheet))}
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
                                                                            <span className="text-muted-foreground">-</span>
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
                                            <td colSpan={10} className="text-right" style={{
                                                position: 'sticky',
                                                left: 0,
                                                zIndex: 11,
                                                backgroundColor: 'var(--tb-border)',
                                                fontWeight: '600'
                                            }}>
                                                Total:
                                            </td>
                                            <td className="text-right" style={{fontWeight: '600'}}>
                                                {reportData.items.reduce((sum, item) => sum + (item.available_quantity || 0), 0).toFixed(3)}
                                            </td>
                                            <td className="text-right text-success" style={{fontWeight: '600'}}>
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
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </div>
    );
}
