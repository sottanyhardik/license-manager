import React, {useEffect, useState, useCallback} from "react";
import {useNavigate} from "react-router-dom";
import Select from "react-select";
import AsyncSelectField from "../../components/AsyncSelectField";
import ConditionBadge from "../../components/ConditionBadge";
import api from "../../api/axios";
import {formatDate} from "../../utils/dateFormatter";
import {formatIndianNumber} from "../../utils/numberFormatter";
import {openPdfPreview} from "../../utils/pdfPreview";
import {toast} from "react-toastify";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ArrowLeftRight, Bell, Building2, Calculator, CalendarCheck, CalendarDays, CalendarRange, DollarSign, FileSpreadsheet, FileText, Filter, Inbox, Info, Loader2, MinusCircle, Package, RefreshCw, ShoppingCart, SlidersHorizontal, StickyNote, Tag, TriangleAlert, XCircle } from "lucide-react";

// Default Purchase Status selection on first load — Global Exim, MITC,
// Conversion (matches the bulk License Balance report's default filter).
const DEFAULT_PURCHASE_STATUS = ['GE', 'MI', 'CO'];

// Colour palette for the per-row Purchase Status badge. Codes map to a
// pastel-on-deep-text scheme so the badge stays readable against the
// table's alternating row backgrounds. Unknown codes get a neutral grey.
const PURCHASE_STATUS_STYLES = {
    GE: { bg: '#DBEAFE', color: '#1E3A8A', short: 'GE' },  // Global Exim — blue
    MI: { bg: '#D1FAE5', color: 'var(--tb-success-text)', short: 'MI' },  // MITC         — green
    CO: { bg: '#EDE9FE', color: '#5B21B6', short: 'CO' },  // Conversion   — purple
    IP: { bg: '#FED7AA', color: '#7C2D12', short: 'IP' },  // Item Purch.  — orange
    SM: { bg: '#FCE7F3', color: '#831843', short: 'SM' },  // Snehav       — pink
    OT: { bg: '#FEF3C7', color: '#78350F', short: 'OT' },  // OT Purchase  — amber
    GO: { bg: '#E2E8F0', color: '#1E293B', short: 'GO' },  // GO Purchase  — slate
    RA: { bg: '#CCFBF1', color: '#134E4A', short: 'RA' },  // Ravi Foods   — teal
    LM: { bg: '#FEE2E2', color: '#7F1D1D', short: 'LM' },  // LM (inactive) — red
};
const UNKNOWN_PS_STYLE = { bg: '#E5E7EB', color: 'var(--tb-text)', short: '?' };

function PurchaseStatusBadge({ code, label }) {
    if (!code) return null;
    const s = PURCHASE_STATUS_STYLES[code] || UNKNOWN_PS_STYLE;
    return (
        <span
            title={label || code}
            style={{
                display: 'inline-block',
                backgroundColor: s.bg,
                color: s.color,
                fontWeight: 600,
                fontSize: 11,
                padding: '1px 6px',
                borderRadius: 'var(--tb-r-sm)',
                lineHeight: 1.4,
                whiteSpace: 'nowrap',
            }}
        >
            {s.short}
        </span>
    );
}

export default function ItemPivotReport() {
    const navigate = useNavigate();
    const [reportData, setReportData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    // Filter states
    const [selectedCompanies, setSelectedCompanies] = useState([]);
    const [excludeCompanies, setExcludeCompanies] = useState([]);
    const [, setSionNorms] = useState([]);
    const [filtersCollapsed, setFiltersCollapsed] = useState(false);
    const [activeNormTab, setActiveNormTab] = useState(null);
    const [availableNorms, setAvailableNorms] = useState([]);
    const [minBalance, setMinBalance] = useState(200);
    const [licenseStatus, setLicenseStatus] = useState('active');
    const [expiryDateFrom, setExpiryDateFrom] = useState('');
    const [expiryDateTo, setExpiryDateTo] = useState('');
    // Purchase Status filter — populated from /masters/purchase-statuses/.
    const [purchaseStatus, setPurchaseStatus] = useState(DEFAULT_PURCHASE_STATUS);
    const [purchaseStatusOptions, setPurchaseStatusOptions] = useState([]);
    const [conditionModal, setConditionModal] = useState(null); // { licenseNumber, content }

    useEffect(() => {
        loadFilterOptions();
        loadAvailableNorms();
    }, []);

    // Reload available norms when filters change (but not on initial mount)
    useEffect(() => {
        // Skip first render (already loaded above)
        if (minBalance !== 200 || licenseStatus !== 'active') {
            loadAvailableNorms();
        }
    }, [minBalance, licenseStatus]);

    const loadFilterOptions = async () => {
        try {
            // Load SION norms (only active ones)
            const normsResponse = await api.get('masters/sion-classes/?is_active=true');
            const normsData = normsResponse.data?.results || normsResponse.data || [];
            setSionNorms(Array.isArray(normsData) ? normsData : []);
        } catch (error) {
            setSionNorms([]);
        }
        try {
            // Purchase Status dropdown — show only active rows, ordered by display_order.
            const psResp = await api.get('masters/purchase-statuses/');
            const psData = psResp.data?.results || psResp.data || [];
            const opts = (Array.isArray(psData) ? psData : [])
                .filter(p => p.is_active !== false)
                .sort((a, b) => (a.display_order || 0) - (b.display_order || 0))
                .map(p => ({value: p.code, label: p.label}));
            setPurchaseStatusOptions(opts);
        } catch (error) {
            setPurchaseStatusOptions([]);
        }
    };

    const loadAvailableNorms = async () => {
        try {
            // Fetch only the list of norm classes (lightweight endpoint)
            let url = `item-pivot/available-norms/`;
            const response = await api.get(url);

            const norms = response.data || [];
            // Response is now array of {norm_class, description} objects
            setAvailableNorms(Array.isArray(norms) ? norms : []);

            // Don't automatically set first norm as active - wait for user click
        } catch (error) {
            setAvailableNorms([]);
        }
    };

    const loadReport = useCallback(async (normClass) => {
        if (!normClass) return;

        setLoading(true);
        try {
            let url = `reports/item-pivot/?format=json&days=30&sion_norm=${normClass}`;

            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            url += `&min_balance=${minBalance}`;
            url += `&license_status=${licenseStatus}`;
            if (expiryDateFrom) url += `&expiry_date_from=${expiryDateFrom}`;
            if (expiryDateTo) url += `&expiry_date_to=${expiryDateTo}`;
            if (purchaseStatus.length > 0) {
                url += `&purchase_status=${purchaseStatus.join(',')}`;
            }

            const response = await api.get(url);
            setReportData(response.data);
        } catch (error) {
            toast.error(error?.response?.data?.error || 'Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            setLoading(false);
        }
    }, [selectedCompanies, excludeCompanies, minBalance, licenseStatus, expiryDateFrom, expiryDateTo, purchaseStatus]);

    // Load report when active norm tab changes or filters change
    useEffect(() => {
        if (activeNormTab) {
            loadReport(activeNormTab);
        }
    }, [activeNormTab, loadReport]);

    const handleUpdateBalance = async () => {
        const statusText = licenseStatus === 'active' ? 'active' : licenseStatus === 'inactive' ? 'inactive' : 'all';

        try {
            // Trigger the update task with current license status filter (no confirmation, runs in background)
            const response = await api.post('item-pivot/update-balance/', {
                license_status: licenseStatus
            });
            const taskId = response.data.task_id;

            // Show immediate toast notification
            toast.info(`Balance update started for ${statusText} licenses. You'll be notified when complete.`, {
                autoClose: 5000
            });

            // Start polling for status in background
            pollUpdateStatus(taskId);
        } catch (error) {
            toast.error('Failed to start balance update. Please try again.');
        }
    };

    const pollUpdateStatus = async (taskId) => {
        try {
            const response = await api.get(`item-pivot/task-status/${taskId}/`);
            const { state, result } = response.data;

            if (state === 'SUCCESS') {
                // Show success notification
                toast.success(
                    `Balance update completed! Updated ${result.updated} licenses in ${result.elapsed_seconds.toFixed(1)}s`,
                    { autoClose: 6000 }
                );

                // Reload the report if a norm is active
                if (activeNormTab) {
                    loadReport(activeNormTab);
                }
            } else if (state === 'FAILURE') {
                toast.error('Balance update failed. Please try again.');
            } else {
                // Continue polling every 2 seconds
                setTimeout(() => pollUpdateStatus(taskId), 2000);
            }
        } catch (error) {
            // Silently fail polling errors (task might still be running)
            console.error('Polling error:', error);
        }
    };

    const handleExport = async () => {
        setDownloading(true);
        try {
            let url = `reports/item-pivot/?format=excel&days=30`;

            if (activeNormTab) {
                url += `&sion_norm=${activeNormTab}`;
            }
            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            url += `&min_balance=${minBalance}`;
            url += `&license_status=${licenseStatus}`;
            if (expiryDateFrom) url += `&expiry_date_from=${expiryDateFrom}`;
            if (expiryDateTo) url += `&expiry_date_to=${expiryDateTo}`;
            if (purchaseStatus.length > 0) {
                url += `&purchase_status=${purchaseStatus.join(',')}`;
            }

            const response = await api.get(url, {
                responseType: 'blob',
            });

            const downloadUrl = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.setAttribute('download', `item_pivot_report.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            toast.error(error?.response?.data?.error || 'Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    };

    const handleCompanyChange = (values) => {
        setSelectedCompanies(values || []);
    };

    const handleExcludeCompanyChange = (values) => {
        setExcludeCompanies(values || []);
    };

    const handleClearFilters = () => {
        setSelectedCompanies([]);
        setExcludeCompanies([]);
        setMinBalance(200);
        setLicenseStatus('active');
        setExpiryDateFrom('');
        setExpiryDateTo('');
        setPurchaseStatus(DEFAULT_PURCHASE_STATUS);
    };

    // Purchase Status is "active" only when it differs from the default trio.
    const isDefaultPurchaseStatus =
        purchaseStatus.length === DEFAULT_PURCHASE_STATUS.length &&
        DEFAULT_PURCHASE_STATUS.every(v => purchaseStatus.includes(v));
    const hasActiveFilters = selectedCompanies.length > 0 || excludeCompanies.length > 0 || minBalance !== 200 || licenseStatus !== 'active' || expiryDateFrom || expiryDateTo || !isDefaultPurchaseStatus;

    const getTotalLicenseCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            Object.values(notifications).forEach(licenses => {
                total += licenses.length;
            });
        });
        return total;
    };

    const getTotalNotificationCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            total += Object.keys(notifications).length;
        });
        return total;
    };

    // Calculate summary for a notification
    const calculateNotificationSummary = (licenses) => {
        const summary = {
            openingBalance: 0,
            regularItems: {},
            restrictedItemsByPercentage: {}, // Group by restriction percentage
            totalAvailable: 0
        };

        // Calculate opening balance (sum of all license balances)
        licenses.forEach(license => {
            const balance = parseFloat(license.balance_cif || 0);
            summary.openingBalance += balance;
        });

        // First pass: Calculate restriction values per license (not per item, as it's shared)
        const processedRestrictions = new Set(); // Track processed license+percentage combinations
        licenses.forEach(license => {
            if (reportData?.items) {
                reportData.items.forEach(item => {
                    const itemData = license.items?.[item.name];
                    if (itemData && itemData.restriction !== null && itemData.restriction !== undefined) {
                        const restrictionPercentage = parseFloat(itemData.restriction || 0);
                        const restrictionKey = `${license.license_number}_${restrictionPercentage}`;

                        // Only add restriction value once per license per percentage
                        if (!processedRestrictions.has(restrictionKey)) {
                            processedRestrictions.add(restrictionKey);

                            if (!summary.restrictedItemsByPercentage[restrictionPercentage]) {
                                summary.restrictedItemsByPercentage[restrictionPercentage] = {
                                    items: {},
                                    sharedRestrictionValue: 0
                                };
                            }
                            summary.restrictedItemsByPercentage[restrictionPercentage].sharedRestrictionValue += parseFloat(itemData.restriction_value || 0);
                        }
                    }
                });
            }
        });

        // Second pass: Calculate item quantities
        if (reportData?.items) {
            reportData.items.forEach(item => {
                let itemAvailable = 0;
                let itemPlanned   = 0;
                let hasRestriction = false;
                let restrictionPercentage = 0;

                licenses.forEach(license => {
                    const itemData = license.items?.[item.name];
                    if (itemData) {
                        // Available quantity
                        itemAvailable += parseFloat(itemData.available_quantity || 0);
                        // Planned CIF (sum) — sourced from the e1_plan/e5_plan waterfall.
                        itemPlanned   += parseFloat(itemData.planned_cif || 0);

                        // Check if item has restriction
                        if (itemData.restriction !== null && itemData.restriction !== undefined) {
                            hasRestriction = true;
                            restrictionPercentage = parseFloat(itemData.restriction || 0);
                        }
                    }
                });

                if (itemAvailable > 0) {
                    const itemSummary = {
                        available:   itemAvailable,
                        planned_cif: itemPlanned,
                        unit_price:  itemAvailable > 0 ? itemPlanned / itemAvailable : 0,
                    };

                    if (hasRestriction) {
                        // Add item to its restriction percentage group
                        if (!summary.restrictedItemsByPercentage[restrictionPercentage]) {
                            summary.restrictedItemsByPercentage[restrictionPercentage] = {
                                items: {},
                                sharedRestrictionValue: 0
                            };
                        }
                        summary.restrictedItemsByPercentage[restrictionPercentage].items[item.name] = itemSummary;
                    } else {
                        summary.regularItems[item.name] = itemSummary;
                    }

                    summary.totalAvailable += itemAvailable;
                    summary.totalPlanned = (summary.totalPlanned || 0) + itemPlanned;
                }
            });
        }

        return summary;
    };


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
                        Item Pivot Report
                    </div>
                    <h1>Item Pivot Report</h1>
                    <div style={{ marginTop: 4, fontSize: 12.5, color: 'var(--tb-text-secondary)' }}>
                        {reportData && (
                            <>
                                <CalendarDays className="size-4" aria-hidden="true" />
                                {reportData.report_date}
                                <span style={{ margin: '0 8px', opacity: 0.5 }}>•</span>
                            </>
                        )}
                        <Tag className="size-4" aria-hidden="true" />
                        Active Norm: {activeNormTab || 'None'}
                        {reportData && (
                            <>
                                <span style={{ margin: '0 8px', opacity: 0.5 }}>•</span>
                                <Bell className="size-4" aria-hidden="true" />
                                {getTotalNotificationCount()} Notifications
                                <span style={{ margin: '0 8px', opacity: 0.5 }}>•</span>
                                <FileText className="size-4" aria-hidden="true" />
                                {getTotalLicenseCount()} Licenses
                            </>
                        )}
                    </div>
                </div>
                <div className="page-actions">
                    <Button variant="outline" size="sm" onClick={() => setFiltersCollapsed(!filtersCollapsed)}>
                        <Filter className="size-4" />
                        {filtersCollapsed ? 'Show' : 'Hide'} Filters
                        {hasActiveFilters && <Badge className="ml-1">Active</Badge>}
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleUpdateBalance}
                        title="Update balance_cif, is_active, is_expired, and restrictions. Runs in background."
                    >
                        <RefreshCw className="size-3.5" />
                        Update Balance
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleExport} disabled={downloading}>
                        {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                        {downloading ? 'Generating…' : 'Excel'}
                    </Button>
                </div>
            </div>

            {/* Filters Section */}
            {!filtersCollapsed && (
                <div className="row mb-3">
                    <div className="col-12">
                        <div className="surface-card" style={{maxWidth: '1400px'}}>
                            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--tb-border)' }}
                                 className="flex justify-between items-center">
                                <h5 className="mb-0" style={{ fontWeight: 600, fontSize: 15 }}>
                                    <SlidersHorizontal className="size-4" aria-hidden="true" />
                                    Filters
                                </h5>
                                {hasActiveFilters && (
                                    <button
                                        type="button"
                                        className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted cursor-pointer"
                                        onClick={handleClearFilters}
                                    >
                                        <XCircle className="size-4" aria-hidden="true" />
                                        Clear Filters
                                    </button>
                                )}
                            </div>
                            <div style={{ padding: '14px 16px' }}>
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                                    <div>
                                        <label className="form-label font-bold mb-2">
                                            <DollarSign className="size-4" aria-hidden="true" />
                                            Minimum Balance (CIF)
                                        </label>
                                        <select
                                            flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring
                                            value={minBalance}
                                            onChange={(e) => setMinBalance(parseInt(e.target.value))}
                                        >
                                            <option value="-999999">All (Including Negative)</option>
                                            <option value="0">₹ 0 or Above</option>
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
                                            <CalendarCheck className="size-4" aria-hidden="true" />
                                            License Status
                                        </label>
                                        <select
                                            flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring
                                            value={licenseStatus}
                                            onChange={(e) => setLicenseStatus(e.target.value)}
                                        >
                                            <option value="active">Active ({">"} 1 month)</option>
                                            <option value="expiring_soon">Expiring Soon (≤ 30 days)</option>
                                            <option value="expired">Expired</option>
                                            <option value="all">All</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="form-label font-bold mb-2">
                                            <ShoppingCart className="size-4" aria-hidden="true" />
                                            Purchase Status
                                        </label>
                                        <Select
                                            isMulti
                                            options={purchaseStatusOptions}
                                            value={purchaseStatusOptions.filter(o => purchaseStatus.includes(o.value))}
                                            onChange={(selected) => setPurchaseStatus(selected ? selected.map(s => s.value) : [])}
                                            placeholder="Select purchase status..."
                                            classNamePrefix="select"
                                            menuPortalTarget={document.body}
                                            menuPosition="fixed"
                                            styles={{
                                                menuPortal: (base) => ({...base, zIndex: 9999}),
                                                control: (base) => ({...base, minHeight: '38px'}),
                                            }}
                                        />
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

                                {hasActiveFilters && (
                                    <div className="mt-3">
                                        <div
                                            className="alert alert-info flex justify-between items-center py-2 mb-0">
                                            <div>
                                                <Filter className="size-4" aria-hidden="true" />
                                                <strong>Active Filters:</strong>
                                                {!isDefaultPurchaseStatus && (
                                                    <span className="badge bg-primary ml-2">
                                                        Purchase: {purchaseStatus.length > 0 ? purchaseStatus.join(', ') : 'none'}
                                                    </span>
                                                )}
                                                {minBalance !== 200 && <span className="badge bg-primary ml-2">Min Balance: ₹{minBalance}</span>}
                                                {licenseStatus !== 'active' && <span
                                                    className="badge bg-primary ml-2">Status: {licenseStatus.replace('_', ' ')}</span>}
                                                {expiryDateFrom && <span className="badge bg-primary ml-2">Expiry From: {expiryDateFrom}</span>}
                                                {expiryDateTo && <span className="badge bg-primary ml-2">Expiry To: {expiryDateTo}</span>}
                                                {selectedCompanies.length > 0 && <span
                                                    className="badge bg-primary ml-2">Incl. Companies: {selectedCompanies.length}</span>}
                                                {excludeCompanies.length > 0 && <span className="badge bg-primary ml-2">Excl. Companies: {excludeCompanies.length}</span>}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Norm Tabs */}
            <div className="row mb-3">
                <div className="col-12">
                    <div className="surface-card">
                        <div style={{ padding: '14px 16px' }}>
                            <h6 className="mb-3" style={{ fontWeight: 600, fontSize: 14.5, color: 'var(--primary-color)' }}>
                                <Tag className="size-4" aria-hidden="true" />
                                Available Norms ({availableNorms.length})
                                <small className="text-muted ml-2">(includes E1, E5, E126, E132 conversion norms)</small>
                            </h6>
                            {availableNorms.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                    {availableNorms.map((normObj) => {
                                        const normClass = normObj.norm_class || normObj;
                                        const description = normObj.description || '';
                                        const isConversionNorm = ['E1', 'E5', 'E126', 'E132'].includes(normClass);
                                        return (
                                            <button
                                                key={normClass}
                                                className={`btn btn-sm ${activeNormTab === normClass ? (isConversionNorm ? 'btn-success' : 'btn-primary') : (isConversionNorm ? 'btn-outline-success' : 'btn-outline-primary')}`}
                                                onClick={() => {
                                                    if (activeNormTab !== normClass) {
                                                        setReportData(null);
                                                    }
                                                    setActiveNormTab(normClass);
                                                }}
                                                type="button"
                                                style={{
                                                    minWidth: '120px',
                                                    fontWeight: activeNormTab === normClass ? 'bold' : 'normal',
                                                    transition: 'all 0.3s ease',
                                                    textAlign: 'center',
                                                    display: 'flex',
                                                    flexDirection: 'column',
                                                    alignItems: 'center',
                                                    padding: '8px 12px'
                                                }}
                                            >
                                                <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: description ? '4px' : '0'}}>
                                                    {isConversionNorm ? <RefreshCw className="size-3.5 mr-1" aria-hidden="true" /> : <Tag className="size-3.5 mr-1" aria-hidden="true" />}
                                                    <span style={{fontSize: 16, fontWeight: '600'}}>{normClass}</span>
                                                    {loading && activeNormTab === normClass && (
                                                        <Loader2 className="ml-1.5 size-3.5 animate-spin text-primary" />
                                                    )}
                                                </div>
                                                {description && (
                                                    <small style={{fontSize: 11, opacity: 0.85, lineHeight: '1.2'}}>
                                                        {description}
                                                    </small>
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            ) : (
                                <div className="text-center py-3">
                                    <Inbox className="size-4" aria-hidden="true" />
                                    <p className="text-muted mb-0 mt-2">No norms available.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Report Tables - Only show active norm */}
            <div className="row">
                <div className="col-12">
                    {/* Loading state */}
                    {loading && activeNormTab && (
                        <div className="card">
                            <div className="card-body flex flex-col items-center py-12 text-center">
                                <Loader2 className="mb-3 size-10 animate-spin text-primary" />
                                <h5 className="text-muted">Loading {activeNormTab} Report…</h5>
                                <p className="text-muted small">Please wait while we fetch the data</p>
                            </div>
                        </div>
                    )}

                    {/* No data message after loading */}
                    {!loading && activeNormTab && reportData?.licenses_by_norm_notification && (!reportData?.licenses_by_norm_notification?.[activeNormTab] || Object.keys(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}).length === 0) && (
                        <div className="card">
                            <div className="card-body text-center py-5">
                                <Inbox className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-muted-foreground">No licenses found for {activeNormTab}</h5>
                                <p className="text-muted">Try adjusting your filters to see more results.</p>
                            </div>
                        </div>
                    )}

                    {/* Show report data */}
                    {!loading && activeNormTab && reportData?.licenses_by_norm_notification?.[activeNormTab] && Object.keys(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}).length > 0 && (
                        <div>
                            {/* Notifications within active norm */}
                            {Object.entries(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}).sort().map(([notification, licenses]) => (
                                <div key={`${activeNormTab}-${notification}`} className="mb-4">
                                    <div className="card">
                                        <div
                                            className="card-header bg-gradient text-primary flex justify-between items-center"
                                            style={{background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))'}}>
                                            <div>
                                                <h5 className="mb-0">
                                                    <Bell className="size-4" aria-hidden="true" />
                                                    Notification Number: {notification}
                                                    {notification === 'Unknown' && (
                                                        <span className="badge bg-warning text-dark ml-2"
                                                              title="Notification number is blank or missing">
                                                            <TriangleAlert className="size-4" aria-hidden="true" />
                                                            Missing
                                                        </span>
                                                    )}
                                                </h5>
                                                <small className="opacity-75">
                                                    {licenses.length} License{licenses.length !== 1 ? 's' : ''}
                                                </small>
                                            </div>
                                            <span className="badge bg-white text-dark">{licenses.length}</span>
                                        </div>
                                        <div className="card-body p-0">
                                            <div className="table-responsive" style={{overflowX: 'auto'}}>
                                                <table className="table table-hover table-sm mb-0"
                                                       style={{tableLayout: 'auto', minWidth: '860px'}}>
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
                                                            minWidth: '120px'
                                                        }}>DFIA No
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '180px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>DFIA Dt
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '280px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Expiry Dt
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '380px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '150px'
                                                        }}>Exporter
                                                        </th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '120px'
                                                        }}>Notif No
                                                        </th>
                                                        <th className="text-end" style={{
                                                            position: 'sticky',
                                                            left: '650px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Total CIF
                                                        </th>
                                                        <th className="text-end" style={{
                                                            position: 'sticky',
                                                            left: '750px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Alloted CIF
                                                        </th>
                                                        <th className="text-end" style={{
                                                            position: 'sticky',
                                                            left: '850px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '110px',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}>Balance CIF
                                                        </th>
                                                        {reportData.items.filter(item => item.name).map(item => {
                                                            // Sub-cols per item: HSN, Description, Total, Allotted,
                                                            // Debited, Balance, Unit Price, Planned CIF
                                                            // + 2 optional restriction cols when applicable
                                                            // + 1 optional RUTILE-specific Unit Price.
                                                            const isRutile = item.name === 'RUTILE - A3627';
                                                            const colSpan = 8
                                                                + (item.has_restriction ? 2 : 0)
                                                                + (isRutile ? 1 : 0);
                                                            return (
                                                                <th key={`${item.id}-qty`} colSpan={colSpan}
                                                                    className="text-center bg-info bg-opacity-10"
                                                                    style={{minWidth: '200px'}}>
                                                                    <Package className="size-4" aria-hidden="true" />
                                                                    {item.name}
                                                                </th>
                                                            );
                                                        })}
                                                    </tr>
                                                    <tr className="table-secondary">
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '60px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '180px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '280px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '380px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '650px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '750px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th style={{
                                                            position: 'sticky',
                                                            left: '850px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}></th>
                                                        {reportData.items.filter(item => item.name).map(item => (
                                                            <React.Fragment key={`${item.id}-headers`}>
                                                                <th style={{minWidth: '90px', fontSize: 13.5}}>HSN
                                                                    Code
                                                                </th>
                                                                <th style={{
                                                                    minWidth: '150px',
                                                                    fontSize: 13.5
                                                                }}>Description
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '90px',
                                                                    fontSize: 13.5
                                                                }}>Total QTY
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: 13.5
                                                                }}>Allotted QTY
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: 13.5
                                                                }}>Debited QTY
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '110px',
                                                                    fontSize: 13.5
                                                                }}>Balance QTY
                                                                </th>
                                                                {item.has_restriction && (
                                                                    <>
                                                                        <th className="text-center" style={{
                                                                            minWidth: '90px',
                                                                            fontSize: 13.5
                                                                        }}>Restriction %
                                                                        </th>
                                                                        <th className="text-end" style={{
                                                                            minWidth: '120px',
                                                                            fontSize: 13.5
                                                                        }}>Restriction Val
                                                                        </th>
                                                                    </>
                                                                )}
                                                                {/* Per-item Unit Price + Planned CIF — sourced from
                                                                    the same e1_plan/e5_plan waterfall the bulk
                                                                    Balance Excel uses. */}
                                                                <th className="text-end" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: 13.5
                                                                }}>Unit Price
                                                                </th>
                                                                <th className="text-end" style={{
                                                                    minWidth: '120px',
                                                                    fontSize: 13.5
                                                                }}>Planned CIF
                                                                </th>
                                                                {item.name === 'RUTILE - A3627' && (
                                                                    <th className="text-end" style={{
                                                                        minWidth: '100px',
                                                                        fontSize: 13.5
                                                                    }}>Unit Price (RUTILE)
                                                                    </th>
                                                                )}
                                                            </React.Fragment>
                                                        ))}
                                                    </tr>
                                                    </thead>
                                                    <tbody>
                                                    {licenses.map((license, idx) => (
                                                        <React.Fragment key={license.license_number}>
                                                        <tr className="align-middle">
                                                            <td className="text-center font-bold" style={{
                                                                position: 'sticky',
                                                                left: 0,
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{idx + 1}</td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '60px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>
                                                                <div className="flex items-center gap-2" style={{ flexWrap: 'nowrap' }}>
                                                                    <span>{license.license_number}</span>
                                                                    <PurchaseStatusBadge
                                                                        code={license.purchase_status_code}
                                                                        label={license.purchase_status_label}
                                                                    />
                                                                    {(license.has_tl || license.has_copy) && (
                                                                        <a
                                                                            href="#"
                                                                            title="View merged documents"
                                                                            onClick={async (e) => {
                                                                                e.preventDefault();
                                                                                e.stopPropagation();
                                                                                try {
                                                                                    const response = await api.get(`licenses/${license.id}/merged-documents/`, {
                                                                                        responseType: 'blob',
                                                                                        headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                                                                                    });
                                                                                    openPdfPreview(response.data, `${license.license_number || license.id}-copy.pdf`);
                                                                                } catch {
                                                                                    toast.error('Failed to load merged documents');
                                                                                }
                                                                            }}
                                                                            style={{
                                                                                fontSize: 11,
                                                                                color: 'var(--success-color)',
                                                                                textDecoration: 'none',
                                                                                padding: '1px 4px',
                                                                                backgroundColor: 'var(--success-bg)',
                                                                                borderRadius: '2px',
                                                                                fontWeight: '500',
                                                                                whiteSpace: 'nowrap'
                                                                            }}
                                                                        >
                                                                            Copy
                                                                        </a>
                                                                    )}
                                                                    {license.condition_sheet && (
                                                                        <button
                                                                            type="button"
                                                                            title="View condition sheet"
                                                                            onClick={(e) => {
                                                                                e.preventDefault();
                                                                                e.stopPropagation();
                                                                                setConditionModal({
                                                                                    licenseNumber: license.license_number,
                                                                                    content: license.condition_sheet,
                                                                                });
                                                                            }}
                                                                            style={{
                                                                                fontSize: 11,
                                                                                color: 'var(--tb-warning-text)',
                                                                                border: 'none',
                                                                                padding: '1px 6px',
                                                                                backgroundColor: 'var(--row-yellow-bg)',
                                                                                borderRadius: '2px',
                                                                                fontWeight: 500,
                                                                                whiteSpace: 'nowrap',
                                                                                lineHeight: 1.4,
                                                                            }}
                                                                        >
                                                                            <FileText className="size-4" aria-hidden="true" />
                                                                            Condition
                                                                        </button>
                                                                    )}
                                                                </div>
                                                            </td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '180px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{formatDate(license.license_date)}</td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '280px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{formatDate(license.license_expiry_date)}</td>
                                                            <td className="text-truncate" style={{
                                                                position: 'sticky',
                                                                left: '380px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)',
                                                                maxWidth: '150px'
                                                            }} title={license.exporter}>
                                                                {license.exporter}
                                                            </td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '530px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>
                                                                {license.notification_number}
                                                                {license.notification_number === 'Unknown' && (
                                                                    <TriangleAlert className="size-4" aria-hidden="true" />
                                                                )}
                                                            </td>
                                                            <td className="text-end font-semibold" style={{
                                                                position: 'sticky',
                                                                left: '650px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{license.total_cif.toFixed(2)}</td>
                                                            <td className="text-end font-semibold text-info" style={{
                                                                position: 'sticky',
                                                                left: '750px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{(license.alloted_cif || 0).toFixed(2)}</td>
                                                            <td className="text-end font-semibold text-success" style={{
                                                                position: 'sticky',
                                                                left: '850px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)',
                                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                                borderRight: '2px solid var(--tb-border)'
                                                            }}>{license.balance_cif.toFixed(2)}</td>
                                                            {reportData.items.filter(item => item.name).map(item => {
                                                                const itemData = license.items[item.name] || {};
                                                                const hasData = itemData.quantity > 0;
                                                                return (
                                                                    <React.Fragment
                                                                        key={`${license.license_number}-${item.id}`}>
                                                                        <td className={hasData ? 'bg-light' : ''}>
                                                                            {itemData.hs_code || '-'}
                                                                            {itemData.condition_type && (
                                                                                <ConditionBadge type={itemData.condition_type} size="xs" />
                                                                            )}
                                                                        </td>
                                                                        <td className={`text-truncate ${hasData ? 'bg-light' : ''}`}
                                                                            style={{maxWidth: '180px'}}
                                                                            title={itemData.description || ''}>
                                                                            {itemData.description || '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light' : ''}`}>
                                                                            {itemData.quantity ? itemData.quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light font-semibold text-primary' : ''}`}>
                                                                            {itemData.allotted_quantity ? itemData.allotted_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light' : ''}`} style={hasData ? {color: 'var(--warning-color)'} : {}}>
                                                                            {itemData.debited_quantity ? itemData.debited_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light text-success font-semibold' : ''}`}>
                                                                            {itemData.available_quantity ? itemData.available_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        {item.has_restriction && (
                                                                            <>
                                                                                <td className={`text-center ${hasData ? 'bg-light' : ''}`}>
                                                                                    {itemData.restriction !== null && itemData.restriction !== undefined ? (
                                                                                        <span
                                                                                            className="badge bg-info">{itemData.restriction}%</span>
                                                                                    ) : '-'}
                                                                                </td>
                                                                                <td className={`text-end ${hasData ? 'bg-light font-semibold' : ''}`}>
                                                                                    {itemData.restriction_value ? itemData.restriction_value.toFixed(2) : '-'}
                                                                                </td>
                                                                            </>
                                                                        )}
                                                                        {/* Unit Price + Planned CIF — sourced from
                                                                            the e1_plan/e5_plan waterfall. */}
                                                                        <td className={`text-end ${hasData ? 'bg-light' : ''}`}>
                                                                            {itemData.unit_price ? Number(itemData.unit_price).toFixed(2) : '-'}
                                                                        </td>
                                                                        <td className={`text-end ${hasData ? 'bg-light font-semibold' : ''}`}>
                                                                            {itemData.planned_cif ? Number(itemData.planned_cif).toFixed(2) : '-'}
                                                                        </td>
                                                                        {item.name === 'RUTILE - A3627' && (
                                                                            <td className={`text-end ${hasData ? 'bg-light font-semibold text-warning' : ''}`}>
                                                                                {itemData.unit_price ? itemData.unit_price.toFixed(4) : '-'}
                                                                            </td>
                                                                        )}
                                                                    </React.Fragment>
                                                                );
                                                            })}
                                                        </tr>
                                                        {/* Notes and Latest Transfer Row (Condition Sheet moved to button + modal) */}
                                                        {(license.balance_report_notes || license.latest_transfer) && (
                                                            <tr key={`${license.license_number}-details`} style={{ backgroundColor: 'var(--tb-sunken)' }}>
                                                                <td colSpan={8 + (reportData.items.filter(item => item.name).length * (reportData.items.some(i => i.has_restriction) ? 8 : 6))} style={{
                                                                    padding: '10px 15px',
                                                                    borderTop: 'none'
                                                                }}>
                                                                    <div style={{ fontSize: 13.5, lineHeight: '1.5' }}>
                                                                        {license.balance_report_notes && (
                                                                            <div style={{
                                                                                marginBottom: license.latest_transfer ? '8px' : '0',
                                                                                backgroundColor: 'var(--danger-color)',
                                                                                padding: '6px 10px',
                                                                                borderRadius: 'var(--tb-r-sm)'
                                                                            }}>
                                                                                <strong style={{ color: '#000' }}>
                                                                                    <StickyNote className="size-4" aria-hidden="true" />
                                                                                    Notes:
                                                                                </strong>
                                                                                <span style={{ color: '#000', marginLeft: '8px' }}>
                                                                                    {license.balance_report_notes}
                                                                                </span>
                                                                            </div>
                                                                        )}
                                                                        {license.latest_transfer && (
                                                                            <div style={{
                                                                                backgroundColor: 'var(--info-color)',
                                                                                padding: '6px 10px',
                                                                                borderRadius: 'var(--tb-r-sm)'
                                                                            }}>
                                                                                <strong style={{ color: '#000' }}>
                                                                                    <ArrowLeftRight className="size-4" aria-hidden="true" />
                                                                                    Latest Transfer:
                                                                                </strong>
                                                                                <span style={{ color: '#000', marginLeft: '8px' }}>
                                                                                    {license.latest_transfer}
                                                                                </span>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        )}
                                                        </React.Fragment>
                                                    ))}
                                                    <tr className="table-warning font-bold" style={{
                                                        position: 'sticky',
                                                        bottom: 0,
                                                        backgroundColor: 'var(--warning-bg)'
                                                    }}>
                                                        <td className="text-uppercase" style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }} colSpan="5">
                                                            <Calculator className="size-4" aria-hidden="true" />
                                                            TOTAL
                                                        </td>
                                                        <td style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }}></td>
                                                        <td className="text-end text-primary" style={{
                                                            position: 'sticky',
                                                            left: '650px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + lic.total_cif, 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-end text-info" style={{
                                                            position: 'sticky',
                                                            left: '750px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + (lic.alloted_cif || 0), 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-end text-success" style={{
                                                            position: 'sticky',
                                                            left: '850px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + lic.balance_cif, 0).toFixed(2)}
                                                        </td>
                                                        {reportData.items.filter(item => item.name).map(item => {
                                                            const totalQty = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.quantity || 0);
                                                            }, 0);
                                                            const totalAllotted = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.allotted_quantity || 0);
                                                            }, 0);
                                                            const totalDebited = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.debited_quantity || 0);
                                                            }, 0);
                                                            const totalAvail = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.available_quantity || 0);
                                                            }, 0);
                                                            const totalRestrictionVal = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.restriction_value || 0);
                                                            }, 0);
                                                            const totalPlanned = licenses.reduce((sum, lic) => {
                                                                return sum + (lic.items[item.name]?.planned_cif || 0);
                                                            }, 0);
                                                            // Effective unit price across all licences = total planned / total avail.
                                                            const effectiveUnit = totalAvail > 0 ? totalPlanned / totalAvail : 0;
                                                            return (
                                                                <React.Fragment key={`total-${item.id}`}>
                                                                    <td className="text-muted">-</td>
                                                                    <td className="text-muted">-</td>
                                                                    <td className="text-end">
                                                                        {totalQty > 0 ? totalQty.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-end text-primary">
                                                                        {totalAllotted > 0 ? totalAllotted.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-end" style={{color: 'var(--warning-color)'}}>
                                                                        {totalDebited > 0 ? totalDebited.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-end text-success">
                                                                        {totalAvail > 0 ? totalAvail.toFixed(3) : '-'}
                                                                    </td>
                                                                    {item.has_restriction && (
                                                                        <>
                                                                            <td className="text-muted">-</td>
                                                                            <td className="text-end font-bold">
                                                                                {totalRestrictionVal > 0 ? totalRestrictionVal.toFixed(2) : '-'}
                                                                            </td>
                                                                        </>
                                                                    )}
                                                                    {/* Unit Price (effective rate) + Planned CIF total. */}
                                                                    <td className="text-end">
                                                                        {effectiveUnit > 0 ? effectiveUnit.toFixed(2) : '-'}
                                                                    </td>
                                                                    <td className="text-end font-bold">
                                                                        {totalPlanned > 0 ? totalPlanned.toFixed(2) : '-'}
                                                                    </td>
                                                                    {item.name === 'RUTILE - A3627' && (
                                                                        <td className="text-muted">-</td>
                                                                    )}
                                                                </React.Fragment>
                                                            );
                                                        })}
                                                    </tr>
                                                    </tbody>
                                                </table>
                                            </div>

                                            {/* Summary Table */}
                                            {(() => {
                                                const summary = calculateNotificationSummary(licenses);
                                                return (
                                                    <div className="mt-4 px-3 pb-3">
                                                        <h6 className="mb-3 text-primary">
                                                            <Calculator className="size-4" aria-hidden="true" />
                                                            Summary
                                                        </h6>
                                                        <div style={{maxWidth: '1400px'}}>
                                                            <table className="table table-bordered table-sm" style={{tableLayout: 'fixed', width: '1400px'}}>
                                                                <thead className="table-light">
                                                                <tr>
                                                                    <th style={{width: '80px'}}>Sr No</th>
                                                                    <th style={{width: '620px'}}>Item Name</th>
                                                                    <th className="text-end" style={{width: '230px'}}>Available Balance QTY</th>
                                                                    <th className="text-end" style={{width: '170px'}}>Unit Price</th>
                                                                    <th className="text-end" style={{width: '300px'}}>Total Planned CIF</th>
                                                                </tr>
                                                                </thead>
                                                                <tbody>
                                                                {/* Opening Balance */}
                                                                <tr className="table-info">
                                                                    <td colSpan="2" className="text-center font-bold">OPENING BALANCE</td>
                                                                    <td className="text-end font-bold">
                                                                        {formatIndianNumber(summary.openingBalance, 2)}
                                                                    </td>
                                                                    <td className="text-end font-bold">-</td>
                                                                    <td className="text-end font-bold">-</td>
                                                                </tr>

                                                                {/* Regular Items */}
                                                                {Object.entries(summary.regularItems).map(([itemName, itemData], idx) => (
                                                                    <tr key={itemName}>
                                                                        <td className="text-center">{idx + 1}</td>
                                                                        <td className="fw-bold">{itemName}</td>
                                                                        <td className="text-end">
                                                                            {formatIndianNumber(itemData.available, 2)}
                                                                        </td>
                                                                        <td className="text-end">
                                                                            {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                        </td>
                                                                        <td className="text-end font-semibold">
                                                                            {itemData.planned_cif ? formatIndianNumber(itemData.planned_cif, 2) : '-'}
                                                                        </td>
                                                                    </tr>
                                                                ))}

                                                                {/* Restricted Items Grouped by Percentage */}
                                                                {Object.keys(summary.restrictedItemsByPercentage).length > 0 && (
                                                                    <>
                                                                        {Object.entries(summary.restrictedItemsByPercentage)
                                                                            .sort(([pctA], [pctB]) => parseFloat(pctA) - parseFloat(pctB))
                                                                            .map(([percentage, groupData], groupIdx) => {
                                                                                const startIdx = Object.keys(summary.regularItems).length +
                                                                                    Object.entries(summary.restrictedItemsByPercentage)
                                                                                        .slice(0, groupIdx)
                                                                                        .reduce((acc, [, data]) => acc + Object.keys(data.items).length, 0);

                                                                                return (
                                                                                    <React.Fragment key={percentage}>
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan="5" className="text-center font-bold">
                                                                                                <TriangleAlert className="size-4" aria-hidden="true" />
                                                                                                RESTRICTED ITEMS - {percentage}%
                                                                                            </td>
                                                                                        </tr>
                                                                                        {Object.entries(groupData.items).map(([itemName, itemData], idx) => (
                                                                                            <tr key={itemName} className="table-light">
                                                                                                <td className="text-center">{startIdx + idx + 1}</td>
                                                                                                <td className="fw-bold">{itemName}</td>
                                                                                                <td className="text-end">
                                                                                                    {formatIndianNumber(itemData.available, 2)}
                                                                                                </td>
                                                                                                <td className="text-end">
                                                                                                    {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                                                </td>
                                                                                                <td className="text-end font-semibold">
                                                                                                    {itemData.planned_cif ? formatIndianNumber(itemData.planned_cif, 2) : '-'}
                                                                                                </td>
                                                                                            </tr>
                                                                                        ))}
                                                                                        {/* Balance for this restriction percentage (shared across all items) */}
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan="2" className="text-center font-bold">Balance {percentage}%</td>
                                                                                            <td className="text-end font-bold">
                                                                                                {formatIndianNumber(groupData.sharedRestrictionValue, 2)}
                                                                                            </td>
                                                                                            <td className="text-end font-bold">-</td>
                                                                                            <td className="text-end font-bold">-</td>
                                                                                        </tr>
                                                                                    </React.Fragment>
                                                                                );
                                                                            })}
                                                                    </>
                                                                )}
                                                                {/* Grand-total row for the Summary table. */}
                                                                <tr className="table-success">
                                                                    <td colSpan="2" className="text-center font-bold">TOTAL PLANNED CIF</td>
                                                                    <td className="text-end font-bold">
                                                                        {formatIndianNumber(summary.totalAvailable || 0, 2)}
                                                                    </td>
                                                                    <td className="text-end font-bold">-</td>
                                                                    <td className="text-end font-bold">
                                                                        {formatIndianNumber(summary.totalPlanned || 0, 2)}
                                                                    </td>
                                                                </tr>
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>
                                    </div>
                                </div>
                            ))}

                            {/* Notes and Conditions Section */}
                            {activeNormTab && reportData?.norm_notes_conditions?.[activeNormTab] && (
                                reportData?.norm_notes_conditions?.[activeNormTab]?.notes?.length > 0 || reportData?.norm_notes_conditions?.[activeNormTab]?.conditions?.length > 0
                            ) && (
                                <div className="card mb-4">
                                    <div className="card-header bg-light">
                                        <h5 className="mb-0">
                                            <Info className="size-4" aria-hidden="true" />
                                            SION Norm {activeNormTab} - Notes & Conditions
                                        </h5>
                                    </div>
                                    <div className="card-body">
                                        <div className="row">
                                            {/* Notes Section */}
                                            {reportData?.norm_notes_conditions?.[activeNormTab]?.notes?.length > 0 && (
                                                <div>
                                                    <h6 className="text-primary mb-3">
                                                        <StickyNote className="size-4" aria-hidden="true" />
                                                        Notes
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData?.norm_notes_conditions?.[activeNormTab]?.notes
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((note, index) => (
                                                                <div key={index} className="list-group-item border-start border-primary border-3">
                                                                    <div className="flex w-full justify-between items-start">
                                                                        <span className="badge bg-primary rounded-pill mr-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow-1" style={{whiteSpace: 'pre-wrap'}}>
                                                                            {note.note_text}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Conditions Section */}
                                            {reportData?.norm_notes_conditions?.[activeNormTab]?.conditions?.length > 0 && (
                                                <div>
                                                    <h6 className="text-warning mb-3">
                                                        <TriangleAlert className="size-4" aria-hidden="true" />
                                                        Conditions
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData?.norm_notes_conditions?.[activeNormTab]?.conditions
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((condition, index) => (
                                                                <div key={index} className="list-group-item border-start border-warning border-3">
                                                                    <div className="flex w-full justify-between items-start">
                                                                        <span className="badge bg-warning text-dark rounded-pill mr-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow-1" style={{whiteSpace: 'pre-wrap'}}>
                                                                            {condition.condition_text}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* No norm selected message */}
                    {!loading && !activeNormTab && availableNorms.length > 0 && (
                        <div className="card">
                            <div className="card-body text-center py-5">
                                <Tag className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-primary">Select a Norm to View Report</h5>
                                <p className="text-muted">Click on any norm tab above to load the report data</p>
                            </div>
                        </div>
                    )}

                    {/* No norms available */}
                    {!loading && availableNorms.length === 0 && (
                        <div className="card">
                            <div className="card-body text-center py-5">
                                <Inbox className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-muted-foreground">No Norms Available</h5>
                                <p className="text-muted">No active norm classes found in the system.</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {conditionModal && (
                <Dialog open={!!conditionModal} onOpenChange={(o) => !o && setConditionModal(null)}>
                    <DialogContent className="max-h-[85vh] max-w-4xl overflow-hidden">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <FileText className="size-4" />
                                Condition Sheet — {conditionModal.licenseNumber}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="max-h-[65vh] overflow-y-auto">
                            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit', fontSize: 14.5, margin: 0, color: 'var(--tb-text)' }}>
                                {conditionModal.content}
                            </pre>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConditionModal(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
        </div>
    );
}
