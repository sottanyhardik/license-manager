import React, {useEffect, useState, useCallback, useRef} from "react";
import {useNavigate} from "react-router-dom";
import ConditionBadge from "../../components/ConditionBadge";
import api from "../../api/axios";
import {formatDate} from "../../utils/dateFormatter";
import {formatIndianNumber} from "../../utils/numberFormatter";
import {toast} from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ArrowLeftRight, Bell, Calculator, CalendarDays, FileSpreadsheet, FileText, Filter, Inbox, Info, Loader2, Package, RefreshCw, StickyNote, Tag, Target, TriangleAlert, XCircle, Zap } from "lucide-react";
import LicensePlanningPanel from "../../components/planning/LicensePlanningPanel";
import { PURCHASE_STATUS_PALETTE, PURCHASE_STATUS_UNKNOWN } from "../../theme/tokens";
import { autoPlanAll } from "../../services/api/licenseApi";
import NormCardGrid from "./NormCardGrid";
import ItemPivotFilters from "./ItemPivotFilters";
import { openAuthedFile } from "../../utils/documentDownload";

// Default Purchase Status selection on first load — Global Exim, MITC,
// Conversion (matches the bulk License Balance report's default filter).
const DEFAULT_PURCHASE_STATUS = ['GE', 'MI', 'CO'];

// Distinct, subtle background tints cycled per item so each item's column
// group (and its name header) is easy to tell apart at a glance.
const ITEM_BG_COLORS = [
    'rgba(59,130,246,0.10)',   // blue
    'rgba(16,185,129,0.10)',   // green
    'rgba(249,115,22,0.10)',   // orange
    'rgba(139,92,246,0.10)',   // purple
    'rgba(236,72,153,0.10)',   // pink
    'rgba(234,179,8,0.12)',    // amber
    'rgba(6,182,212,0.10)',    // cyan
    'rgba(107,114,128,0.10)',  // gray
];
const itemBgColor = (idx) => ITEM_BG_COLORS[idx % ITEM_BG_COLORS.length];

type ItemPivotPathOptions = {
    format: "json" | "excel";
    normClass?: unknown;
    selectedCompanies?: unknown[];
    excludeCompanies?: unknown[];
    minBalance?: unknown;
    licenseStatus?: unknown;
    expiryDateFrom?: unknown;
    expiryDateTo?: unknown;
    purchaseStatus?: unknown[];
};

export function toFiniteNumber(value: unknown, fallback = 0): number {
    const parsed = Number.parseFloat(String(value ?? ""));
    return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeFilterValues(values?: unknown[]): string[] {
    if (!Array.isArray(values)) {
        return [];
    }

    return values
        .map((value) => String(value ?? "").trim())
        .filter(Boolean);
}

export function buildItemPivotReportPath({
    format,
    normClass,
    selectedCompanies = [],
    excludeCompanies = [],
    minBalance = 200,
    licenseStatus = "active",
    expiryDateFrom,
    expiryDateTo,
    purchaseStatus = [],
}: ItemPivotPathOptions): string {
    const params = new URLSearchParams({
        format,
        days: "30",
    });
    const normClassValue = String(normClass ?? "").trim();
    const includeCompanyIds = normalizeFilterValues(selectedCompanies);
    const excludeCompanyIds = normalizeFilterValues(excludeCompanies);
    const purchaseStatuses = normalizeFilterValues(purchaseStatus);
    const expiryFrom = String(expiryDateFrom ?? "").trim();
    const expiryTo = String(expiryDateTo ?? "").trim();

    if (normClassValue) params.set("sion_norm", normClassValue);
    if (includeCompanyIds.length > 0) params.set("company_ids", includeCompanyIds.join(","));
    if (excludeCompanyIds.length > 0) params.set("exclude_company_ids", excludeCompanyIds.join(","));
    params.set("min_balance", String(toFiniteNumber(minBalance, 200)));
    params.set("license_status", String(licenseStatus || "active"));
    if (expiryFrom) params.set("expiry_date_from", expiryFrom);
    if (expiryTo) params.set("expiry_date_to", expiryTo);
    if (purchaseStatuses.length > 0) params.set("purchase_status", purchaseStatuses.join(","));

    return `reports/item-pivot/?${params.toString()}`;
}

// Shared style for the compact Condition / Transfer / Note action pills that
// sit next to each DFIA number. Soft tint + coloured text/border, icon inline.
const ACTION_PILL_BASE = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'flex-start',
    gap: 5,
    width: '100%',
    fontSize: 11,
    fontWeight: 600,
    lineHeight: 1.3,
    padding: '3px 8px',
    borderRadius: 6,
    whiteSpace: 'nowrap',
    cursor: 'pointer',
};

// Purchase-status badge palette now lives in theme/tokens.js (single source of truth).
const PURCHASE_STATUS_STYLES = PURCHASE_STATUS_PALETTE;
const UNKNOWN_PS_STYLE = PURCHASE_STATUS_UNKNOWN;

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
    const [reportData, setReportData] = useState<Record<string, any> | null>(null);
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
    const [transferModal, setTransferModal] = useState(null); // { licenseNumber, content }
    const [noteModal, setNoteModal] = useState(null); // { licenseNumber, content }
    // Utilization planning panel (same component the licenses page uses).
    const [showPlanModal, setShowPlanModal] = useState(false);
    const [planLicense, setPlanLicense] = useState(null); // { id, number, balance }
    const [autoPlanning, setAutoPlanning] = useState(false);
    const [autoPlanSummary, setAutoPlanSummary] = useState<{
        total: number; planned: number; already_planned: number;
        skipped_unknown_norm: number; failed: number;
        errors: { license: string; error: string }[];
    } | null>(null);

    // AbortController ref — cancels the previous in-flight loadReport request
    // when a new one starts, preventing stale responses from overwriting fresh data.
    const reportAbortRef = useRef<AbortController | null>(null);

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

        // Cancel any in-flight request for this report — prevents the classic
        // "stale response overwrites fresh data" race condition where a slow
        // first request resolves after a faster second one and resets the table.
        if (reportAbortRef.current) {
            reportAbortRef.current.abort();
        }
        const controller = new AbortController();
        reportAbortRef.current = controller;

        setLoading(true);
        try {
            const response = await api.get(buildItemPivotReportPath({
                format: "json",
                normClass,
                selectedCompanies,
                excludeCompanies,
                minBalance,
                licenseStatus,
                expiryDateFrom,
                expiryDateTo,
                purchaseStatus,
            }), { signal: controller.signal });

            // Only commit state if this request was not superseded
            if (!controller.signal.aborted) {
                setReportData(response.data);
            }
        } catch (error) {
            // Axios names aborted requests 'CanceledError'; ignore them silently
            if (
                error?.name === 'CanceledError' ||
                error?.code === 'ERR_CANCELED' ||
                controller.signal.aborted
            ) {
                return;
            }
            toast.error(error?.response?.data?.error || 'Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            if (!controller.signal.aborted) {
                setLoading(false);
            }
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
            if (!taskId) {
                toast.error('Balance update did not return a task id.');
                return;
            }

            // Show immediate toast notification
            toast.info(`Balance update started for ${statusText} licenses. You'll be notified when complete.`, {
                duration: 5000
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
                const updatedCount = toFiniteNumber(result?.updated, 0);
                const elapsedSeconds = toFiniteNumber(result?.elapsed_seconds, 0);
                toast.success(
                    `Balance update completed! Updated ${updatedCount} licenses in ${elapsedSeconds.toFixed(1)}s`,
                    { duration: 6000 }
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
            await openAuthedFile(buildItemPivotReportPath({
                format: "excel",
                normClass: activeNormTab,
                selectedCompanies,
                excludeCompanies,
                minBalance,
                licenseStatus,
                expiryDateFrom,
                expiryDateTo,
                purchaseStatus,
            }), "item_pivot_report.xlsx");
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

    const handleAutoPlanAll = async () => {
        if (!window.confirm(
            'Auto Plan All DFIA will run the plan algorithm on every eligible E1/E5/E132 license ' +
            '(skipping those already ≥ 99 % planned).\n\nThis may take a while. Continue?'
        )) return;
        setAutoPlanning(true);
        setAutoPlanSummary(null);
        try {
            const result = await autoPlanAll();
            setAutoPlanSummary(result);
        } catch (err: unknown) {
            const msg = (err as { response?: { data?: { error?: string } } })?.response?.data?.error
                || 'Auto Plan All failed. Please try again.';
            toast.error(msg);
        } finally {
            setAutoPlanning(false);
        }
    };

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
        const summary: Record<string, any> = {
            openingBalance: 0,
            regularItems: {},
            restrictedItemsByPercentage: {},
            totalAvailable: 0
        };

        // Calculate opening balance (sum of all license balances)
        licenses.forEach(license => {
            const balance = toFiniteNumber(license.balance_cif);
            summary.openingBalance += balance;
        });

        // First pass: Calculate restriction values per license (not per item, as it's shared)
        const processedRestrictions = new Set(); // Track processed license+percentage combinations
        licenses.forEach(license => {
            if (reportData?.items) {
                reportData.items.forEach(item => {
                    const itemData = license.items?.[item.name];
                    if (itemData && itemData.restriction !== null && itemData.restriction !== undefined) {
                        const restrictionPercentage = toFiniteNumber(itemData.restriction);
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
                            summary.restrictedItemsByPercentage[restrictionPercentage].sharedRestrictionValue += toFiniteNumber(itemData.restriction_value);
                        }
                    }
                });
            }
        });

        // Second pass: Calculate item quantities
        if (reportData?.items) {
            reportData.items.forEach(item => {
                let itemAvailable  = 0;
                let itemPlanned    = 0;   // planned CIF (manual plan if present, else norm)
                let itemPlannedQty = 0;   // planned quantity backing that CIF
                let hasRestriction = false;
                let restrictionPercentage = 0;

                licenses.forEach(license => {
                    const itemData = license.items?.[item.name];
                    if (itemData) {
                        // Available quantity
                        itemAvailable += toFiniteNumber(itemData.available_quantity);
                        // Planned CIF + quantity evaluated per-product: use manual
                        // plan values when this product was manually planned;
                        // otherwise fall back to norm-derived planned_cif / qty.
                        const itemHasManual =
                            toFiniteNumber(itemData.plan_cif) > 0 ||
                            toFiniteNumber(itemData.plan_quantity) > 0;
                        itemPlanned    += itemHasManual
                            ? toFiniteNumber(itemData.plan_cif)
                            : toFiniteNumber(itemData.planned_cif);
                        itemPlannedQty += itemHasManual
                            ? toFiniteNumber(itemData.plan_quantity)
                            : toFiniteNumber(itemData.available_quantity);

                        // Check if item has restriction
                        if (itemData.restriction !== null && itemData.restriction !== undefined) {
                            hasRestriction = true;
                            restrictionPercentage = toFiniteNumber(itemData.restriction);
                        }
                    }
                });

                // Include an item in the summary when it has import balance *or*
                // has planned CIF — the latter handles manually-planned split items
                // (e.g. "DWP - E1") whose planned item name has no corresponding
                // import item and therefore available_quantity = 0.
                if (itemAvailable > 0 || itemPlanned > 0) {
                    const itemSummary = {
                        // For split-planned items (DWP, WPC …) that have no direct
                        // import counterpart, available_quantity is 0 from the backend.
                        // Fall back to the planned qty so the column shows the correct
                        // balance quantity instead of 0.
                        available:    itemAvailable > 0 ? itemAvailable : itemPlannedQty,
                        planned_cif:  itemPlanned,
                        planned_qty:  itemPlannedQty,
                        // Unit price = Total Planned CIF / Total Planned QTY.
                        unit_price:   itemPlannedQty > 0 ? itemPlanned / itemPlannedQty : 0,
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
                    summary.totalPlannedQty = (summary.totalPlannedQty || 0) + itemPlannedQty;
                }
            });
        }

        return summary;
    };


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
                        Item Pivot Report
                    </div>
                    <h1>Item Pivot Report</h1>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        {reportData && (
                            <span className="inline-flex items-center gap-1">
                                <CalendarDays className="size-3.5" aria-hidden="true" />
                                {reportData.report_date}
                            </span>
                        )}
                        <span className="inline-flex items-center gap-1">
                            <Tag className="size-3.5" aria-hidden="true" />
                            Active Norm:
                            <span className="font-semibold text-foreground">{activeNormTab || 'None'}</span>
                        </span>
                        {reportData && (
                            <>
                                <span className="inline-flex items-center gap-1">
                                    <Bell className="size-3.5" aria-hidden="true" />
                                    {getTotalNotificationCount()} Notifications
                                </span>
                                <span className="inline-flex items-center gap-1">
                                    <FileText className="size-3.5" aria-hidden="true" />
                                    {getTotalLicenseCount()} Licenses
                                </span>
                            </>
                        )}
                    </div>
                </div>
                <div className="page-actions">
                    <Button variant="ghost" size="sm" onClick={() => setFiltersCollapsed(!filtersCollapsed)}>
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
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleAutoPlanAll}
                        disabled={autoPlanning}
                        className="gap-1.5 border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 hover:text-amber-800 font-semibold"
                        title="Run Auto Plan on every eligible DFIA license (E1 / E5 / E132)"
                    >
                        {autoPlanning ? <Loader2 className="size-3.5 animate-spin" /> : <Zap className="size-3.5" />}
                        {autoPlanning ? 'Planning…' : 'Auto Plan All DFIA'}
                    </Button>
                </div>
            </div>

            {/* Filters Section */}
            {!filtersCollapsed && (
                <ItemPivotFilters
                    minBalance={minBalance} setMinBalance={setMinBalance}
                    licenseStatus={licenseStatus} setLicenseStatus={setLicenseStatus}
                    purchaseStatus={purchaseStatus} setPurchaseStatus={setPurchaseStatus}
                    purchaseStatusOptions={purchaseStatusOptions}
                    expiryDateFrom={expiryDateFrom} setExpiryDateFrom={setExpiryDateFrom}
                    expiryDateTo={expiryDateTo} setExpiryDateTo={setExpiryDateTo}
                    selectedCompanies={selectedCompanies} handleCompanyChange={handleCompanyChange}
                    excludeCompanies={excludeCompanies} handleExcludeCompanyChange={handleExcludeCompanyChange}
                    hasActiveFilters={hasActiveFilters} handleClearFilters={handleClearFilters}
                    isDefaultPurchaseStatus={isDefaultPurchaseStatus}
                />
            )}

            {/* Norm Tabs — redesigned */}
            <NormCardGrid
                availableNorms={availableNorms}
                activeNormTab={activeNormTab}
                setActiveNormTab={setActiveNormTab}
                setReportData={setReportData}
                loading={loading}
            />

            {/* Report Tables - Only show active norm */}
            <div>
                    {/* Empty state: norms exist but none selected */}
                    {!activeNormTab && !loading && availableNorms.length > 0 && (
                        <div className="flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed border-border py-16 text-center">
                            <div className="flex size-16 items-center justify-center rounded-2xl bg-primary/10">
                                <Tag className="size-8 text-primary" />
                            </div>
                            <div>
                                <p className="text-base font-bold text-foreground">Select a Norm to View Report</p>
                                <p className="mt-1 text-[12.5px] text-muted-foreground">Click any norm card above to load license data for that SION norm class</p>
                            </div>
                            {availableNorms.length > 0 && (
                                <div className="flex flex-wrap justify-center gap-1.5 mt-1">
                                    {availableNorms.slice(0, 5).map((n) => (
                                        <button key={n.norm_class || n} type="button"
                                            onClick={() => { setReportData(null); setActiveNormTab(n.norm_class || n); }}
                                            className="rounded-lg px-3 py-1 text-xs font-bold transition-colors hover:opacity-90"
                                            style={{ background: ['E1','E5','E126','E132'].includes(n.norm_class || n) ? 'var(--tb-success-soft)' : 'var(--tb-brand-50)', color: ['E1','E5','E126','E132'].includes(n.norm_class || n) ? 'var(--tb-success-text)' : 'var(--tb-brand)', border: '1px solid' }}>
                                            {n.norm_class || n}
                                        </button>
                                    ))}
                                    {availableNorms.length > 5 && <span className="self-center text-[11px] text-muted-foreground">+{availableNorms.length - 5} more</span>}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Loading state */}
                    {loading && activeNormTab && (
                        <div className="mb-4 flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-card py-14 text-center shadow-sm">
                            <div className="flex size-14 items-center justify-center rounded-full bg-primary/10">
                                <Loader2 className="size-7 animate-spin text-primary" />
                            </div>
                            <div>
                                <p className="font-semibold text-foreground">Loading {activeNormTab} Report…</p>
                                <p className="mt-0.5 text-[12.5px] text-muted-foreground">Fetching license data for this norm</p>
                            </div>
                        </div>
                    )}

                    {/* No data message after loading */}
                    {!loading && activeNormTab && reportData?.licenses_by_norm_notification && (!reportData?.licenses_by_norm_notification?.[activeNormTab] || Object.keys(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}).length === 0) && (
                        <div className="mb-4 flex flex-col items-center justify-center gap-3 rounded-xl border border-border bg-card py-12 text-center shadow-sm">
                            <Inbox className="size-10 opacity-20" aria-hidden="true" />
                            <div>
                                <p className="font-semibold text-foreground">No licenses found for <span className="text-primary">{activeNormTab}</span></p>
                                <p className="mt-0.5 text-[12.5px] text-muted-foreground">Try adjusting your filters — e.g. increase minimum balance or change purchase status.</p>
                            </div>
                            {hasActiveFilters && (
                                <Button variant="outline" size="sm" onClick={handleClearFilters}>
                                    <XCircle className="size-4" />
                                    Clear Filters
                                </Button>
                            )}
                        </div>
                    )}

                    {/* Show report data */}
                    {!loading && activeNormTab && reportData?.licenses_by_norm_notification?.[activeNormTab] && Object.keys(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}).length > 0 && (
                        <div>
                            {/* Notifications within active norm */}
                            {(Object.entries(reportData?.licenses_by_norm_notification?.[activeNormTab] || {}) as [string, any][]).sort().map(([groupKey, licenses]: [string, any]) => {
                                // Group key is "<Purchase Status> — <notification>" (see backend).
                                // Split it so the table header shows purchase status as a chip
                                // and the notification on its own.
                                const emIdx = groupKey.indexOf(' — ');
                                const psLabel = emIdx >= 0 ? groupKey.slice(0, emIdx) : (licenses[0]?.purchase_status_label || '');
                                const notification = emIdx >= 0 ? groupKey.slice(emIdx + 3) : groupKey;
                                // Per-group item filter: only render columns for items that have
                                // actual data (import qty, balance, or plan) in THIS notification
                                // group. Using the global reportData.items list would cause every
                                // possible E1/E5 item to appear as an empty column even when no
                                // license in this group planned or imported it.
                                const groupItems = (reportData.items as any[]).filter((item: any) => {
                                    if (!item.name) return false;
                                    return (licenses as any[]).some((license: any) => {
                                        const d = license.items?.[item.name] || {};
                                        return (
                                            (d.quantity ?? 0) > 0 ||
                                            (d.available_quantity ?? 0) > 0 ||
                                            (d.plan_quantity ?? 0) > 0 ||
                                            (d.plan_cif ?? 0) > 0
                                        );
                                    });
                                });
                                return (
                                <div key={`${activeNormTab}-${groupKey}`} className="mb-4">
                                    <Card>
                                        <CardHeader
                                            className="flex-row items-center justify-between gap-4 text-primary-foreground"
                                            style={{background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))'}}>
                                            <div>
                                                <h5 className="mb-0 flex items-center gap-2 font-semibold">
                                                    <Bell className="size-4" aria-hidden="true" />
                                                    Notification Number: {notification}
                                                    {notification === 'Unknown' && (
                                                        <span className="chip chip-warning ml-2"
                                                              title="Notification number is blank or missing">
                                                            <TriangleAlert className="size-4" aria-hidden="true" />
                                                            Missing
                                                        </span>
                                                    )}
                                                    {psLabel && (
                                                        <span className="chip chip-info ml-2" title="Purchase status">
                                                            {psLabel}
                                                        </span>
                                                    )}
                                                </h5>
                                                <small className="opacity-75">
                                                    {licenses.length} License{licenses.length !== 1 ? 's' : ''}
                                                </small>
                                            </div>
                                            <span className="chip chip-neutral">{licenses.length}</span>
                                        </CardHeader>
                                        <CardContent className="p-0">
                                            <div className="overflow-x-auto">
                                                <table className="table table-hover table-sm table-bordered mb-0"
                                                       style={{tableLayout: 'auto', minWidth: '860px'}}>
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
                                                            minWidth: '120px'
                                                        }}>DFIA No
                                                        </th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '180px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Expiry Dt
                                                        </th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '280px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '150px'
                                                        }}>Exporter
                                                        </th>
                                                        <th scope="col" className="text-right" style={{
                                                            position: 'sticky',
                                                            left: '430px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Total CIF
                                                        </th>
                                                        <th scope="col" className="text-right" style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Debited CIF
                                                        </th>
                                                        <th scope="col" className="text-right" style={{
                                                            position: 'sticky',
                                                            left: '630px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '100px'
                                                        }}>Alloted CIF
                                                        </th>
                                                        <th scope="col" className="text-right" style={{
                                                            position: 'sticky',
                                                            left: '730px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-sunken)',
                                                            minWidth: '110px',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}>Balance CIF
                                                        </th>
                                                        {/* DFIA Dt / Notif No temporarily hidden
                                                        <th style={{ minWidth: '100px' }}>DFIA Dt</th>
                                                        <th style={{ minWidth: '120px' }}>Notif No</th>
                                                        */}
                                                        {groupItems.map((item, itemIdx) => {
                                                            // Sub-cols per item: HSN, Description, Total, Allotted,
                                                            // Debited, Balance, Plan Qty, Plan CIF
                                                            // + 2 optional restriction cols when applicable
                                                            // + 1 optional RUTILE-specific Unit Price.
                                                            const isRutile = item.name === 'RUTILE - A3627';
                                                            const colSpan = 8
                                                                + (item.has_restriction ? 2 : 0)
                                                                + (isRutile ? 1 : 0)
                                                                + 2;
                                                            return (
                                                                <th scope="col" key={`${item.id}-qty`} colSpan={colSpan}
                                                                    className="text-center"
                                                                    style={{minWidth: '200px', backgroundColor: itemBgColor(itemIdx)}}>
                                                                    <Package className="size-4" aria-hidden="true" />
                                                                    {item.name}
                                                                </th>
                                                            );
                                                        })}
                                                    </tr>
                                                    <tr className="table-secondary">
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: 0,
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '60px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '180px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '280px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '430px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '630px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)'
                                                        }}></th>
                                                        <th scope="col" style={{
                                                            position: 'sticky',
                                                            left: '730px',
                                                            zIndex: 11,
                                                            backgroundColor: 'var(--tb-border)',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}></th>
                                                        {/* DFIA Dt / Notif No spacers temporarily hidden */}
                                                        {groupItems.map(item => (
                                                            <React.Fragment key={`${item.id}-headers`}>
                                                                <th scope="col" style={{minWidth: '90px', fontSize: 13.5}}>HSN
                                                                    Code
                                                                </th>
                                                                <th scope="col" style={{
                                                                    minWidth: '150px',
                                                                    fontSize: 13.5
                                                                }}>Description
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '90px',
                                                                    fontSize: 13.5
                                                                }}>Total QTY
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: 13.5
                                                                }}>Allotted QTY
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '100px',
                                                                    fontSize: 13.5
                                                                }}>Debited QTY
                                                                </th>
                                                                <th scope="col" className="text-right" style={{
                                                                    minWidth: '110px',
                                                                    fontSize: 13.5
                                                                }}>Balance QTY
                                                                </th>
                                                                {item.has_restriction && (
                                                                    <>
                                                                        <th scope="col" className="text-center" style={{
                                                                            minWidth: '90px',
                                                                            fontSize: 13.5
                                                                        }}>Restriction %
                                                                        </th>
                                                                        <th scope="col" className="text-right" style={{
                                                                            minWidth: '120px',
                                                                            fontSize: 13.5
                                                                        }}>Restriction Val
                                                                        </th>
                                                                    </>
                                                                )}
                                                                {/* Manual plan when present, else norm unit price / planned CIF */}
                                                                <th scope="col" className="text-right" style={{ minWidth: '110px', fontSize: 13.5 }}>Plan Qty / Unit Price</th>
                                                                <th scope="col" className="text-right" style={{ minWidth: '110px', fontSize: 13.5 }}>Planned CIF</th>
                                                                {item.name === 'RUTILE - A3627' && (
                                                                    <th scope="col" className="text-right" style={{
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
                                                                    <div>
                                                                        {(license.has_tl || license.has_copy) ? (
                                                                            <a
                                                                                href="#"
                                                                                title="Open DFIA documents in a new tab"
                                                                                onClick={async (e) => {
                                                                                    e.preventDefault();
                                                                                    e.stopPropagation();
                                                                                    try {
                                                                                        await openAuthedFile(`licenses/${license.id}/merged-documents/`);
                                                                                    } catch {
                                                                                        toast.error('Failed to open DFIA documents');
                                                                                    }
                                                                                }}
                                                                                className="cursor-pointer whitespace-nowrap font-semibold text-primary underline"
                                                                            >
                                                                                {license.license_number}
                                                                            </a>
                                                                        ) : (
                                                                            <span className="font-semibold">{license.license_number}</span>
                                                                        )}
                                                                        <div className="mt-1">
                                                                            <PurchaseStatusBadge
                                                                                code={license.purchase_status_code}
                                                                                label={license.purchase_status_label}
                                                                            />
                                                                        </div>
                                                                    </div>
                                                                    {/* Condition / Transfer / Note — one vertical, centered column of
                                                                        buttons that open their content in a modal (saves row width). */}
                                                                    {(
                                                                        <div className="flex flex-col items-stretch justify-center gap-1" style={{ minWidth: 96 }}>
                                                                            {license.condition_sheet && (
                                                                                <button
                                                                                    type="button"
                                                                                    title="View condition sheet"
                                                                                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setConditionModal({ licenseNumber: license.license_number, content: license.condition_sheet }); }}
                                                                                    style={{ ...ACTION_PILL_BASE, color: '#92610a', backgroundColor: 'rgba(234,179,8,0.13)', border: '1px solid rgba(234,179,8,0.45)' }}
                                                                                >
                                                                                    <FileText className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                    Condition
                                                                                </button>
                                                                            )}
                                                                            {license.latest_transfer && (
                                                                                <button
                                                                                    type="button"
                                                                                    title="View transfer status"
                                                                                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setTransferModal({ licenseNumber: license.license_number, content: license.latest_transfer }); }}
                                                                                    style={{ ...ACTION_PILL_BASE, color: '#1d4ed8', backgroundColor: 'rgba(59,130,246,0.13)', border: '1px solid rgba(59,130,246,0.45)' }}
                                                                                >
                                                                                    <ArrowLeftRight className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                    Transfer
                                                                                </button>
                                                                            )}
                                                                            {license.balance_report_notes && (
                                                                                <button
                                                                                    type="button"
                                                                                    title="View notes"
                                                                                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setNoteModal({ licenseNumber: license.license_number, content: license.balance_report_notes }); }}
                                                                                    style={{ ...ACTION_PILL_BASE, color: '#b91c1c', backgroundColor: 'rgba(239,68,68,0.13)', border: '1px solid rgba(239,68,68,0.45)' }}
                                                                                >
                                                                                    <StickyNote className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                    Note
                                                                                </button>
                                                                            )}
                                                                            <button
                                                                                type="button"
                                                                                title={license.plan_source === 'manual' ? 'Re-plan utilization (already planned)' : 'Plan utilization'}
                                                                                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setPlanLicense({ id: license.id, number: license.license_number, balance: Number(license.balance_cif || 0) }); setShowPlanModal(true); }}
                                                                                style={{ ...ACTION_PILL_BASE, color: 'var(--tb-brand-active)', backgroundColor: 'var(--tb-brand-50)', border: '1px solid #a5b4fc' }}
                                                                            >
                                                                                <Target className="size-3.5 shrink-0" aria-hidden="true" />
                                                                                {license.plan_source === 'manual' ? 'Re Plan me' : 'Plan me'}
                                                                            </button>
                                                                        </div>)}
                                                                </div>
                                                            </td>
                                                            <td className="text-nowrap" style={{
                                                                position: 'sticky',
                                                                left: '180px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{formatDate(license.license_expiry_date)}</td>
                                                            <td className="text-truncate" style={{
                                                                position: 'sticky',
                                                                left: '280px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)',
                                                                maxWidth: '150px'
                                                            }} title={license.exporter}>
                                                                {license.exporter}
                                                            </td>
                                                            <td className="text-right font-semibold" style={{
                                                                position: 'sticky',
                                                                left: '430px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{license.total_cif.toFixed(2)}</td>
                                                            <td className="text-right font-semibold text-warning" style={{
                                                                position: 'sticky',
                                                                left: '530px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{(license.debited_cif || 0).toFixed(2)}</td>
                                                            <td className="text-right font-semibold text-info" style={{
                                                                position: 'sticky',
                                                                left: '630px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)'
                                                            }}>{(license.alloted_cif || 0).toFixed(2)}</td>
                                                            <td className="text-right font-semibold text-success" style={{
                                                                position: 'sticky',
                                                                left: '730px',
                                                                zIndex: 1,
                                                                backgroundColor: 'var(--tb-card-bg)',
                                                                boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                                borderRight: '2px solid var(--tb-border)'
                                                            }}>{license.balance_cif.toFixed(2)}</td>
                                                            {/* DFIA Dt / Notif No temporarily hidden
                                                            <td className="text-nowrap">{formatDate(license.license_date)}</td>
                                                            <td className="text-nowrap">{license.notification_number}</td>
                                                            */}
                                                            {groupItems.map((item, itemIdx) => {
                                                                const itemData = license.items[item.name] || {};
                                                                const hasData = itemData.quantity > 0;
                                                                // Per-product: whether THIS product was manually planned
                                                                // (independent of every other product on this license).
                                                                // A product was manually planned when its plan_quantity or
                                                                // plan_cif is non-zero; otherwise show norm-derived values.
                                                                // Each item's cells share one background tint so the item's
                                                                // column group is visually distinct from its neighbours.
                                                                const itemBg = itemBgColor(itemIdx);
                                                                return (
                                                                    <React.Fragment
                                                                        key={`${license.license_number}-${item.id}`}>
                                                                        <td style={{backgroundColor: itemBg}}>
                                                                            {itemData.hs_code || '-'}
                                                                            {itemData.condition_type && (
                                                                                <ConditionBadge type={itemData.condition_type} size="xs" />
                                                                            )}
                                                                        </td>
                                                                        <td className="text-truncate"
                                                                            style={{maxWidth: '180px', backgroundColor: itemBg}}
                                                                            title={itemData.description || ''}>
                                                                            {itemData.description || '-'}
                                                                        </td>
                                                                        <td className="text-right" style={{backgroundColor: itemBg}}>
                                                                            {itemData.quantity ? itemData.quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={cn('text-right', hasData && 'font-semibold text-primary')} style={{backgroundColor: itemBg}}>
                                                                            {itemData.allotted_quantity ? itemData.allotted_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className="text-right" style={{backgroundColor: itemBg, ...(hasData ? {color: 'var(--warning-color)'} : {})}}>
                                                                            {itemData.debited_quantity ? itemData.debited_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        <td className={cn('text-right', hasData && 'text-success font-semibold')} style={{backgroundColor: itemBg}}>
                                                                            {itemData.available_quantity ? itemData.available_quantity.toFixed(3) : '-'}
                                                                        </td>
                                                                        {item.has_restriction && (
                                                                            <>
                                                                                <td className="text-center" style={{backgroundColor: itemBg}}>
                                                                                    {itemData.restriction !== null && itemData.restriction !== undefined ? (
                                                                                        <span
                                                                                            className="chip chip-info">{itemData.restriction}%</span>
                                                                                    ) : '-'}
                                                                                </td>
                                                                                <td className={cn('text-right', hasData && 'font-semibold')} style={{backgroundColor: itemBg}}>
                                                                                    {itemData.restriction_value ? itemData.restriction_value.toFixed(2) : '-'}
                                                                                </td>
                                                                            </>
                                                                        )}
                                                                        {/* Per-product plan: manual plan takes priority when
                                                                            this product was manually planned; fall back to
                                                                            norm-derived values otherwise. */}
                                                                        <td className="text-right" style={{backgroundColor: itemBg}}>
                                                                            {(Number(itemData.plan_quantity || 0) > 0 || Number(itemData.plan_cif || 0) > 0)
                                                                                ? Number(itemData.plan_quantity || 0).toFixed(3)
                                                                                : (itemData.unit_price != null ? Number(itemData.unit_price).toFixed(2) : '-')}
                                                                        </td>
                                                                        <td className={cn('text-right', hasData && 'font-semibold')} style={{backgroundColor: itemBg}}>
                                                                            {(Number(itemData.plan_quantity || 0) > 0 || Number(itemData.plan_cif || 0) > 0)
                                                                                ? Number(itemData.plan_cif || 0).toFixed(2)
                                                                                : (itemData.planned_cif ? Number(itemData.planned_cif).toFixed(2) : '-')}
                                                                        </td>
                                                                        {item.name === 'RUTILE - A3627' && (
                                                                            <td className={cn('text-right', hasData && 'font-semibold text-warning')} style={{backgroundColor: itemBg}}>
                                                                                {itemData.unit_price ? itemData.unit_price.toFixed(4) : '-'}
                                                                            </td>
                                                                        )}
                                                                    </React.Fragment>
                                                                );
                                                            })}
                                                        </tr>
                                                        {/* Notes & Latest Transfer now open from the Note / Transfer buttons
                                                            in the DFIA cell (see above) — bottom detail row removed. */}
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
                                                        }} colSpan={4}>
                                                            <Calculator className="size-4" aria-hidden="true" />
                                                            TOTAL
                                                        </td>
                                                        <td className="text-right text-primary" style={{
                                                            position: 'sticky',
                                                            left: '430px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + lic.total_cif, 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-right text-warning" style={{
                                                            position: 'sticky',
                                                            left: '530px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + (lic.debited_cif || 0), 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-right text-info" style={{
                                                            position: 'sticky',
                                                            left: '630px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + (lic.alloted_cif || 0), 0).toFixed(2)}
                                                        </td>
                                                        <td className="text-right text-success" style={{
                                                            position: 'sticky',
                                                            left: '730px',
                                                            zIndex: 1,
                                                            backgroundColor: 'var(--warning-bg)',
                                                            boxShadow: '3px 0 8px rgba(0,0,0,0.15)',
                                                            borderRight: '2px solid var(--tb-border)'
                                                        }}>
                                                            {licenses.reduce((sum, lic) => sum + lic.balance_cif, 0).toFixed(2)}
                                                        </td>
                                                        {/* DFIA Dt / Notif No totals temporarily hidden */}
                                                        {groupItems.map(item => {
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
                                                            // Planned CIF + quantity per-product (matches per-row logic):
                                                            // use manual plan values when THIS product was manually
                                                            // planned; otherwise use norm-derived values.
                                                            const totalPlanned = licenses.reduce((sum, lic) => {
                                                                const it = lic.items[item.name] || {};
                                                                const itHasManual = (it.plan_quantity || 0) > 0 || (it.plan_cif || 0) > 0;
                                                                return sum + (itHasManual ? (it.plan_cif || 0) : (it.planned_cif || 0));
                                                            }, 0);
                                                            const totalPlannedQty = licenses.reduce((sum, lic) => {
                                                                const it = lic.items[item.name] || {};
                                                                const itHasManual = (it.plan_quantity || 0) > 0 || (it.plan_cif || 0) > 0;
                                                                return sum + (itHasManual ? (it.plan_quantity || 0) : (it.available_quantity || 0));
                                                            }, 0);
                                                            // Effective unit price = total planned CIF / total planned qty.
                                                            const effectiveUnit = totalPlannedQty > 0 ? totalPlanned / totalPlannedQty : 0;
                                                            return (
                                                                <React.Fragment key={`total-${item.id}`}>
                                                                    <td className="text-muted-foreground">-</td>
                                                                    <td className="text-muted-foreground">-</td>
                                                                    <td className="text-right">
                                                                        {totalQty > 0 ? totalQty.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-right text-primary">
                                                                        {totalAllotted > 0 ? totalAllotted.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-right text-warning">
                                                                        {totalDebited > 0 ? totalDebited.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className="text-right text-success">
                                                                        {totalAvail > 0 ? totalAvail.toFixed(3) : '-'}
                                                                    </td>
                                                                    {item.has_restriction && (
                                                                        <>
                                                                            <td className="text-muted-foreground">-</td>
                                                                            <td className="text-right font-bold">
                                                                                {totalRestrictionVal > 0 ? totalRestrictionVal.toFixed(2) : '-'}
                                                                            </td>
                                                                        </>
                                                                    )}
                                                                    {/* Unit Price (effective rate) + Planned CIF total. */}
                                                                    <td className="text-muted-foreground">-</td>
                                                                    <td className="text-right text-muted-foreground">-</td>
                                                                    <td className="text-right">
                                                                        {effectiveUnit > 0 ? effectiveUnit.toFixed(2) : '-'}
                                                                    </td>
                                                                    <td className="text-right font-bold">
                                                                        {totalPlanned > 0 ? totalPlanned.toFixed(2) : '-'}
                                                                    </td>
                                                                    {item.name === 'RUTILE - A3627' && (
                                                                        <td className="text-muted-foreground">-</td>
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
                                                                    <th scope="col" style={{width: '80px'}}>Sr No</th>
                                                                    <th scope="col" style={{width: '620px'}}>Item Name</th>
                                                                    <th scope="col" className="text-right" style={{width: '230px'}}>Available Balance QTY</th>
                                                                    <th scope="col" className="text-right" style={{width: '170px'}}>Unit Price</th>
                                                                    <th scope="col" className="text-right" style={{width: '300px'}}>Total Planned CIF ($)</th>
                                                                </tr>
                                                                </thead>
                                                                <tbody>
                                                                {/* Opening Balance */}
                                                                <tr className="table-info">
                                                                    <td colSpan={2} className="text-center font-bold">OPENING BALANCE</td>
                                                                    <td className="text-right font-bold">
                                                                        {formatIndianNumber(summary.openingBalance, 2)}
                                                                    </td>
                                                                    <td className="text-right font-bold">-</td>
                                                                    <td className="text-right font-bold">-</td>
                                                                </tr>

                                                                {/* Regular Items */}
                                                                {(Object.entries(summary.regularItems) as [string, any][]).map(([itemName, itemData]: [string, any], idx) => (
                                                                    <tr key={itemName}>
                                                                        <td className="text-center">{idx + 1}</td>
                                                                        <td className="font-bold">{itemName}</td>
                                                                        <td className="text-right">
                                                                            {formatIndianNumber(itemData.available, 2)}
                                                                        </td>
                                                                        <td className="text-right">
                                                                            {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                        </td>
                                                                        <td className="text-right font-semibold">
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
                                                                                        .reduce((acc: number, [, data]: [string, any]) => acc + Object.keys((data as any).items || {}).length, 0);

                                                                                return (
                                                                                    <React.Fragment key={percentage}>
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan={5} className="text-center font-bold">
                                                                                                <TriangleAlert className="size-4" aria-hidden="true" />
                                                                                                RESTRICTED ITEMS - {percentage}%
                                                                                            </td>
                                                                                        </tr>
                                                                                        {(Object.entries((groupData as any).items || {}) as [string, any][]).map(([itemName, itemData]: [string, any], idx) => (
                                                                                            <tr key={itemName} className="table-light">
                                                                                                <td className="text-center">{startIdx + idx + 1}</td>
                                                                                                <td className="font-bold">{itemName}</td>
                                                                                                <td className="text-right">
                                                                                                    {formatIndianNumber(itemData.available, 2)}
                                                                                                </td>
                                                                                                <td className="text-right">
                                                                                                    {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                                                </td>
                                                                                                <td className="text-right font-semibold">
                                                                                                    {itemData.planned_cif ? formatIndianNumber(itemData.planned_cif, 2) : '-'}
                                                                                                </td>
                                                                                            </tr>
                                                                                        ))}
                                                                                        {/* Balance for this restriction percentage (shared across all items) */}
                                                                                        <tr className="table-warning">
                                                                                            <td colSpan={2} className="text-center font-bold">Balance {percentage}%</td>
                                                                                            <td className="text-right font-bold">
                                                                                                {formatIndianNumber((groupData as any).sharedRestrictionValue, 2)}
                                                                                            </td>
                                                                                            <td className="text-right font-bold">-</td>
                                                                                            <td className="text-right font-bold">-</td>
                                                                                        </tr>
                                                                                    </React.Fragment>
                                                                                );
                                                                            })}
                                                                    </>
                                                                )}
                                                                {/* Grand-total row for the Summary table. */}
                                                                <tr className="table-success">
                                                                    <td colSpan={2} className="text-center font-bold">TOTAL PLANNED CIF ($)</td>
                                                                    <td className="text-right font-bold">
                                                                        {formatIndianNumber(summary.totalAvailable || 0, 2)}
                                                                    </td>
                                                                    <td className="text-right font-bold">
                                                                        {summary.totalPlannedQty > 0
                                                                            ? (summary.totalPlanned / summary.totalPlannedQty).toFixed(2)
                                                                            : '-'}
                                                                    </td>
                                                                    <td className="text-right font-bold">
                                                                        {formatIndianNumber(summary.totalPlanned || 0, 2)}
                                                                    </td>
                                                                </tr>
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </CardContent>
                                    </Card>
                                </div>
                                );
                            })}

                            {/* ── Norms Total Summary ────────────────────────── */}
                            {(() => {
                                // Flatten all licenses across every notification group
                                // for the active norm, then reuse the existing summary engine.
                                const allNormLicenses: any[] = Object.values(
                                    reportData?.licenses_by_norm_notification?.[activeNormTab] || {}
                                ).flat();
                                if (allNormLicenses.length === 0) return null;
                                const totalLicenses = allNormLicenses.length;
                                const totalBalanceCif = allNormLicenses.reduce(
                                    (s, l) => s + (l.balance_cif || 0), 0
                                );
                                const ns = calculateNotificationSummary(allNormLicenses);
                                const itemRows = [
                                    ...Object.entries(ns.regularItems as Record<string, any>),
                                    ...Object.values(ns.restrictedItemsByPercentage as Record<string, any>)
                                        .flatMap((g: any) => Object.entries(g.items || {})),
                                ] as [string, any][];

                                return (
                                    <Card className="mb-4 border-primary/30">
                                        <CardHeader
                                            className="flex-row items-center gap-3 text-primary-foreground"
                                            style={{ background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))' }}>
                                            <Calculator className="size-4" aria-hidden="true" />
                                            <h5 className="mb-0 font-semibold">
                                                {activeNormTab} — Norms Total Summary
                                            </h5>
                                            <span className="chip chip-neutral ml-auto">{totalLicenses} Licenses</span>
                                        </CardHeader>
                                        <CardContent className="p-0">
                                            <div style={{ maxWidth: '1400px', overflowX: 'auto' }}>
                                                <table className="table table-bordered table-sm mb-0" style={{ tableLayout: 'fixed', width: '1400px' }}>
                                                    <thead className="table-light">
                                                        <tr>
                                                            <th scope="col" style={{ width: '60px' }}>Sr No</th>
                                                            <th scope="col" style={{ width: '540px' }}>Item Name</th>
                                                            <th scope="col" className="text-right" style={{ width: '230px' }}>Available Balance QTY</th>
                                                            <th scope="col" className="text-right" style={{ width: '170px' }}>Unit Price</th>
                                                            <th scope="col" className="text-right" style={{ width: '300px' }}>Total Planned CIF ($)</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {/* Opening Balance */}
                                                        <tr className="table-info">
                                                            <td colSpan={2} className="text-center font-bold">OPENING BALANCE</td>
                                                            <td className="text-right font-bold">{formatIndianNumber(totalBalanceCif, 2)}</td>
                                                            <td className="text-right font-bold">-</td>
                                                            <td className="text-right font-bold">-</td>
                                                        </tr>

                                                        {/* Item rows */}
                                                        {itemRows.map(([itemName, itemData], idx) => (
                                                            <tr key={itemName}>
                                                                <td className="text-center">{idx + 1}</td>
                                                                <td className="font-bold">{itemName}</td>
                                                                <td className="text-right">
                                                                    {formatIndianNumber(itemData.available, 2)}
                                                                </td>
                                                                <td className="text-right">
                                                                    {itemData.unit_price ? itemData.unit_price.toFixed(2) : '-'}
                                                                </td>
                                                                <td className="text-right font-semibold">
                                                                    {itemData.planned_cif ? formatIndianNumber(itemData.planned_cif, 2) : '-'}
                                                                </td>
                                                            </tr>
                                                        ))}

                                                        {/* Grand total */}
                                                        <tr className="table-primary font-bold">
                                                            <td colSpan={2} className="text-center font-bold">TOTAL PLANNED CIF ($)</td>
                                                            <td className="text-right font-bold">
                                                                {formatIndianNumber(ns.totalPlannedQty || 0, 2)}
                                                            </td>
                                                            <td className="text-right font-bold">
                                                                {(ns.totalPlannedQty || 0) > 0
                                                                    ? ((ns.totalPlanned || 0) / (ns.totalPlannedQty || 1)).toFixed(2)
                                                                    : '-'}
                                                            </td>
                                                            <td className="text-right font-bold">
                                                                {formatIndianNumber(ns.totalPlanned || 0, 2)}
                                                            </td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </CardContent>
                                    </Card>
                                );
                            })()}

                            {/* Notes and Conditions Section */}
                            {activeNormTab && reportData?.norm_notes_conditions?.[activeNormTab] && (
                                reportData?.norm_notes_conditions?.[activeNormTab]?.notes?.length > 0 || reportData?.norm_notes_conditions?.[activeNormTab]?.conditions?.length > 0
                            ) && (
                                <Card className="mb-4">
                                    <CardHeader>
                                        <h5 className="flex items-center gap-2 font-semibold">
                                            <Info className="size-4" aria-hidden="true" />
                                            SION Norm {activeNormTab} - Notes & Conditions
                                        </h5>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="space-y-4">
                                            {/* Notes Section */}
                                            {reportData?.norm_notes_conditions?.[activeNormTab]?.notes?.length > 0 && (
                                                <div>
                                                    <h6 className="mb-3 flex items-center gap-2 text-primary">
                                                        <StickyNote className="size-4" aria-hidden="true" />
                                                        Notes
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData?.norm_notes_conditions?.[activeNormTab]?.notes
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((note, index) => (
                                                                <div key={index} className="list-group-item border-start border-primary border-3">
                                                                    <div className="flex w-full justify-between items-start">
                                                                        <span className="chip chip-primary mr-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow whitespace-pre-wrap">
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
                                                    <h6 className="mb-3 flex items-center gap-2 text-warning">
                                                        <TriangleAlert className="size-4" aria-hidden="true" />
                                                        Conditions
                                                    </h6>
                                                    <div className="list-group">
                                                        {reportData?.norm_notes_conditions?.[activeNormTab]?.conditions
                                                            .sort((a, b) => a.display_order - b.display_order)
                                                            .map((condition, index) => (
                                                                <div key={index} className="list-group-item border-start border-warning border-3">
                                                                    <div className="flex w-full justify-between items-start">
                                                                        <span className="chip chip-warning mr-2">{index + 1}</span>
                                                                        <p className="mb-0 flex-grow whitespace-pre-wrap">
                                                                            {condition.condition_text}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </div>
                    )}

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
                            <pre className="m-0 whitespace-pre-wrap break-words font-[inherit] text-[14.5px] text-foreground">
                                {conditionModal.content}
                            </pre>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConditionModal(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {transferModal && (
                <Dialog open={!!transferModal} onOpenChange={(o) => !o && setTransferModal(null)}>
                    <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <ArrowLeftRight className="size-4" />
                                Transfer Status — {transferModal.licenseNumber}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="max-h-[65vh] overflow-y-auto">
                            <pre className="m-0 whitespace-pre-wrap break-words font-[inherit] text-[14.5px] text-foreground">
                                {transferModal.content}
                            </pre>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setTransferModal(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {noteModal && (
                <Dialog open={!!noteModal} onOpenChange={(o) => !o && setNoteModal(null)}>
                    <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <StickyNote className="size-4" />
                                Notes — {noteModal.licenseNumber}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="max-h-[65vh] overflow-y-auto">
                            <pre className="m-0 whitespace-pre-wrap break-words font-[inherit] text-[14.5px] text-foreground">
                                {noteModal.content}
                            </pre>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setNoteModal(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {/* Utilization planning — same panel the licenses page uses. */}
            <LicensePlanningPanel
                show={showPlanModal}
                onHide={() => { setShowPlanModal(false); setPlanLicense(null); }}
                licenseId={planLicense?.id}
                licenseNumber={planLicense?.number}
                balanceCif={planLicense?.balance || 0}
                onSaved={() => { if (activeNormTab) loadReport(activeNormTab); }}
            />

            {/* Auto Plan All — summary dialog */}
            {autoPlanSummary && (
                <Dialog open={!!autoPlanSummary} onOpenChange={(o) => { if (!o) setAutoPlanSummary(null); }}>
                    <DialogContent className="max-w-md">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <Zap className="size-4 text-amber-600" aria-hidden="true" />
                                Auto Plan Completed
                            </DialogTitle>
                        </DialogHeader>
                        <div className="space-y-2 py-2 text-sm">
                            {[
                                ['Total Licenses Processed', autoPlanSummary.total],
                                ['Successfully Planned',     autoPlanSummary.planned],
                                ['Already Planned',          autoPlanSummary.already_planned],
                                ['Skipped (unknown norm)',   autoPlanSummary.skipped_unknown_norm],
                                ['Failed',                  autoPlanSummary.failed],
                            ].map(([label, value]) => (
                                <div key={String(label)} className="flex items-center justify-between rounded-lg border border-border/50 px-3 py-2">
                                    <span className="text-muted-foreground">{label}</span>
                                    <span className="font-bold tabular-nums">{value}</span>
                                </div>
                            ))}
                        </div>
                        {autoPlanSummary.errors.length > 0 && (
                            <details className="mt-1">
                                <summary className="cursor-pointer text-[11px] text-destructive font-medium">
                                    {autoPlanSummary.errors.length} error(s) — click to expand
                                </summary>
                                <div className="mt-2 max-h-40 overflow-y-auto space-y-1">
                                    {autoPlanSummary.errors.map((e, i) => (
                                        <div key={i} className="rounded bg-destructive/5 px-2 py-1 text-[11px]">
                                            <span className="font-semibold">{e.license}:</span> {e.error}
                                        </div>
                                    ))}
                                </div>
                            </details>
                        )}
                        <DialogFooter>
                            <Button size="sm" onClick={() => setAutoPlanSummary(null)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
        </div>
    );
}
