import { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import api from "../../api/axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { CalendarDays, FileSpreadsheet, Inbox, Loader2, Package, Tag } from "lucide-react";
import { usePagination } from "@/hooks/usePagination";
import DataPagination from "@/components/DataPagination";
import PageHeader from "@/components/PageHeader";
import ActiveFilters, { type ActiveFilterItem } from "@/components/ActiveFilters";
import { useItemReportFilters } from "./itemReport/useItemReportFilters";
import { useItemReportData } from "./itemReport/useItemReportData";
import ItemReportFilters from "./itemReport/ItemReportFilters";
import ItemReportTotalsBar from "./itemReport/ItemReportTotalsBar";
import ItemReportTable from "./itemReport/ItemReportTable";
import ItemReportProductTable, { ReconciliationBadge } from "./itemReport/ItemReportProductTable";
import { useItemReportProducts } from "./itemReport/useItemReportProducts";
import { buildItemReportPath } from "./reportPaths";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { PlanningStatus } from "./itemReport/useItemReportFilters";

const PLANNING_STATUS_OPTIONS: { value: PlanningStatus; label: string }[] = [
    { value: "all", label: "All Items" },
    { value: "planned", label: "Planned" },
    { value: "unplanned", label: "Unplanned" },
];

type ReportView = "product" | "import";

const VIEW_OPTIONS: { value: ReportView; label: string }[] = [
    { value: "product", label: "By product (Item Name × SION)" },
    { value: "import", label: "By import item" },
];

const EMPTY_MESSAGE: Record<PlanningStatus, string> = {
    all: "No items found",
    planned: "No planned items match the current filters",
    unplanned: "No unplanned items match the current filters",
};



export default function ItemReport() {
    const {
        selectedItemNames, minBalance, minAvailQty, licenseStatus, selectedCompanies, excludeCompanies,
        isRestricted, purchaseStatus, productDescSearch, hsnCodeSearch, selectedNorms, selectedNotifications,
        notificationOptions, purchaseStatusOptions, normOptions, expiryDateFrom, expiryDateTo, planningStatus, setPlanningStatus, licenseNumbers, setLicenseNumbers,
        setMinBalance, setMinAvailQty, setLicenseStatus, setIsRestricted,
        setProductDescSearch, setHsnCodeSearch, setExpiryDateFrom, setExpiryDateTo,
        handleItemNameChange, handleCompanyChange, handleExcludeCompanyChange, handlePurchaseStatusChange,
        handleNormsChange, handleNotificationsChange, handleClearFilters,
        hasActiveFilters, filters, debouncedFilters, isPending,
    } = useItemReportFilters();

    const [view, setView] = useState<ReportView>("product");

    const products = useItemReportProducts(debouncedFilters, view === "product");

    const {
        reportData, setReportData, loading, downloading, itemNameOptions,
        editingCell, editValue, setEditValue, startEdit, cancelEdit, saveEdit, handleExport,
    } = useItemReportData({
        buildPath: buildItemReportPath,
        availableItemsPath: "item-report/available-items/",
        debouncedFilters,
        exportFilename: "item_report.xlsx",
        requireQuery: false,
        enabled: view === "import",
    });
    const planningCounts = (view === "product" ? products.data?.planning_counts : reportData?.planning_counts) as Record<PlanningStatus, number> | undefined;

    // Paginate by LICENSE GROUP (not raw item row) — a license's item rows
    // must never be split across a page boundary, since the first row of
    // each group carries the license-level columns the rest rowSpan into.
    // The report's own data is already sorted by expiry date server-side
    // (see item_report.py's generate_report), so grouping here preserves
    // that order. Totals bar / Excel export always use the FULL,
    // unpaginated `reportData.items` — only the on-screen table paginates.
    const licenseGroups = useMemo(() => {
        if (!reportData?.items) return [];
        const map = new Map<string, any[]>();
        reportData.items.forEach((item: any) => {
            if (!map.has(item.license_id)) map.set(item.license_id, []);
            map.get(item.license_id)!.push(item);
        });
        return Array.from(map.values());
    }, [reportData]);

    const pagination = usePagination({ initialPageSize: 25 });
    useEffect(() => {
        pagination.setTotalItems(licenseGroups.length);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [licenseGroups.length]);
    useEffect(() => {
        // Reset to page 1 whenever the filtered dataset changes, so the
        // user never gets stranded on a page beyond the new result set.
        pagination.goToPage(1);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [reportData]);

    const groupStart = (pagination.currentPage - 1) * pagination.pageSize;
    const priorPageGroups = useMemo(
        () => licenseGroups.slice(0, groupStart),
        [licenseGroups, groupStart]
    );
    // Sr No increments once per raw item row (see ItemReportTable), so the
    // continuation offset for page N+1 must be the raw-row count of every
    // license group on prior pages — not the group count itself.
    const startSrNo = useMemo(
        () => priorPageGroups.reduce((sum, group) => sum + group.length, 0),
        [priorPageGroups]
    );
    const pageItems = useMemo(
        () => licenseGroups.slice(groupStart, groupStart + pagination.pageSize).flat(),
        [licenseGroups, groupStart, pagination.pageSize]
    );

    const handleItemNamesEdit = async (item: any, selectedOptions: { value: unknown; label: string }[] | null) => {
        try {
            const itemNameIds = selectedOptions ? selectedOptions.map(v => v.value) : [];
            await api.patch(`license-items/${item.id}/`, {
                items: itemNameIds
            });
            toast.success('Item names updated successfully');

            // Fetch updated item data to check if it still matches filters
            const response = await api.get(buildItemReportPath({format: "json", ...filters}));
            const updatedReportData = response.data;

            // Find the updated item in the new data
            const updatedItem = updatedReportData.items.find((i: any) => i.id === item.id);

            if (updatedItem) {
                // Item still matches filters - update the row
                setReportData((prev) => {
                    if (!prev) return prev;
                    const updatedItems = prev.items.map((i: any) => i.id === item.id ? updatedItem : i);
                    return {...prev, items: updatedItems};
                });
            } else {
                // Item no longer matches filters - remove it from the list
                setReportData((prev) => {
                    if (!prev) return prev;
                    const filteredItems = prev.items.filter((i: any) => i.id !== item.id);
                    return {...prev, items: filteredItems, total_items: filteredItems.length};
                });
                toast.info('Item removed from list as it no longer matches the filters');
            }
        } catch {
            toast.error('Failed to update item names. Please try again.');
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <PageHeader
                pretitle="Reports"
                title="Item Report"
                description={
                    view === "product" && products.data ? (
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                            <CalendarDays className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span>{products.data.report_date}</span>
                            <span className="text-muted-foreground">•</span>
                            <Package className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span>{products.data.products.length} products</span>
                        </div>
                    ) : view === "import" && reportData ? (
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                            <CalendarDays className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span>{reportData.report_date}</span>
                            <span className="text-muted-foreground">•</span>
                            <Package className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span>{reportData.total_items} items</span>
                        </div>
                    ) : undefined
                }
                actions={
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => (view === "product" ? products.exportExcel(filters) : handleExport(filters))}
                        disabled={view === "product" ? products.downloading : downloading}
                    >
                        {(view === "product" ? products.downloading : downloading) ? <Loader2 className="size-3.5 animate-spin shrink-0" /> : <FileSpreadsheet className="size-3.5 shrink-0" />}
                        <span className="hidden sm:inline">{(view === "product" ? products.downloading : downloading) ? 'Generating…' : 'Export Excel'}</span>
                        <span className="sm:hidden">{(view === "product" ? products.downloading : downloading) ? '…' : 'Export'}</span>
                    </Button>
                }
            />

            <ItemReportFilters
                isPending={isPending}
                hasActiveFilters={hasActiveFilters}
                onClearFilters={handleClearFilters}
                minBalance={minBalance}
                onMinBalanceChange={setMinBalance}
                minAvailQty={minAvailQty}
                onMinAvailQtyChange={setMinAvailQty}
                licenseStatus={licenseStatus}
                onLicenseStatusChange={setLicenseStatus}
                expiryDateFrom={expiryDateFrom}
                onExpiryDateFromChange={setExpiryDateFrom}
                expiryDateTo={expiryDateTo}
                onExpiryDateToChange={setExpiryDateTo}
                selectedCompanies={selectedCompanies}
                onCompanyChange={handleCompanyChange}
                excludeCompanies={excludeCompanies}
                onExcludeCompanyChange={handleExcludeCompanyChange}
                isRestricted={isRestricted}
                onIsRestrictedChange={setIsRestricted}
                purchaseStatusOptions={purchaseStatusOptions}
                purchaseStatus={purchaseStatus}
                onPurchaseStatusChange={handlePurchaseStatusChange}
                normOptions={normOptions}
                selectedNorms={selectedNorms}
                onNormsChange={handleNormsChange}
                notificationOptions={notificationOptions}
                selectedNotifications={selectedNotifications}
                onNotificationsChange={handleNotificationsChange}
                productDescSearch={productDescSearch}
                onProductDescSearchChange={setProductDescSearch}
                hsnCodeSearch={hsnCodeSearch}
                onHsnCodeSearchChange={setHsnCodeSearch}
                itemNameOptions={itemNameOptions}
                selectedItemNames={selectedItemNames}
                onItemNameChange={handleItemNameChange}
                licenseNumbers={licenseNumbers}
                onLicenseNumbersChange={setLicenseNumbers}
            />

            {/* Active Filters Display */}
            <ItemReportActiveFiltersDisplay
                filters={{
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
                    licenseNumbers,
                }}
                onRemoveFilter={(key) => {
                    switch (key) {
                        case 'selectedItemNames': handleItemNameChange(null); break;
                        case 'minBalance': setMinBalance(200); break;
                        case 'minAvailQty': setMinAvailQty(0); break;
                        case 'licenseStatus': setLicenseStatus('active'); break;
                        case 'selectedCompanies': handleCompanyChange(null); break;
                        case 'excludeCompanies': handleExcludeCompanyChange(null); break;
                        case 'isRestricted': setIsRestricted('all'); break;
                        case 'purchaseStatus': handlePurchaseStatusChange(purchaseStatusOptions.map(o => o.value)); break;
                        case 'productDescSearch': setProductDescSearch(''); break;
                        case 'hsnCodeSearch': setHsnCodeSearch(''); break;
                        case 'selectedNorms': handleNormsChange(null); break;
                        case 'selectedNotifications': handleNotificationsChange(null); break;
                        case 'expiryDateFrom': setExpiryDateFrom(''); break;
                        case 'expiryDateTo': setExpiryDateTo(''); break;
                        case 'licenseNumbers': setLicenseNumbers(''); break;
                    }
                }}
                onClearAll={handleClearFilters}
                purchaseStatusOptions={purchaseStatusOptions}
            />

            {/* View switch — both views share the filters and Planning Status */}
            <div role="group" aria-label="Report view" className="mt-3 inline-flex rounded-lg border border-border p-0.5">
                {VIEW_OPTIONS.map((option) => (
                    <Button
                        key={option.value}
                        type="button"
                        size="sm"
                        variant={view === option.value ? "default" : "ghost"}
                        aria-pressed={view === option.value}
                        onClick={() => setView(option.value)}
                    >
                        {option.label}
                    </Button>
                ))}
            </div>

            {/* Planning Status (server-side filter; counts are within the other active filters) */}
            <div className="mt-3 flex flex-wrap items-center gap-2">
                <label id="planning-status-label" htmlFor="planning-status" className="text-sm font-medium">Planning Status</label>
                <Select value={planningStatus} onValueChange={(value) => setPlanningStatus(value as PlanningStatus)}>
                    <SelectTrigger id="planning-status" aria-labelledby="planning-status-label" className="h-8 w-[220px]">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {PLANNING_STATUS_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                                {option.label}{planningCounts ? ` (${planningCounts[option.value].toLocaleString("en-IN")})` : ""}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {view === "product" && products.data && !products.loading && (
                <div className="mt-3"><ReconciliationBadge reconciliation={products.data.reconciliation} /></div>
            )}

            {/* Sticky Totals Bar */}
            {view === "import" && !loading && (reportData?.items?.length ?? 0) > 0 && (
                <ItemReportTotalsBar items={reportData.items} />
            )}

            {/* Report Table */}
            <div className="row mt-3">
                <div className="col-span-full">
                    {view === "product" && products.loading && (
                        <Card>
                            <CardContent className="flex flex-col items-center py-8 text-center">
                                <Loader2 className="mb-2 size-8 animate-spin text-primary" />
                                <h5 className="text-muted-foreground">Loading product report…</h5>
                            </CardContent>
                        </Card>
                    )}

                    {view === "product" && !products.loading && products.data && products.data.products.length === 0 && (
                        <Card>
                            <CardContent className="py-5 text-center">
                                <Inbox className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-muted-foreground">{EMPTY_MESSAGE[planningStatus]}</h5>
                                <p className="text-muted-foreground">Try adjusting your filters to see more results.</p>
                            </CardContent>
                        </Card>
                    )}

                    {view === "product" && !products.loading && products.data && products.data.products.length > 0 && (
                        <ItemReportProductTable
                            products={products.data.products}
                            totals={products.data.totals}
                            filters={debouncedFilters}
                        />
                    )}

                    {view === "import" && loading && (
                        <Card>
                            <CardContent className="flex flex-col items-center py-8 text-center">
                                <Loader2 className="mb-2 size-8 animate-spin text-primary" />
                                <h5 className="text-muted-foreground">Loading Item Report…</h5>
                                <p className="text-muted-foreground text-sm">Please wait while we fetch the data</p>
                            </CardContent>
                        </Card>
                    )}


                    {view === "import" && !loading && reportData && (reportData.items?.length ?? 0) === 0 && (
                        <Card>
                            <CardContent className="py-5 text-center">
                                <Inbox className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-muted-foreground">{EMPTY_MESSAGE[planningStatus]}</h5>
                                <p className="text-muted-foreground">Try adjusting your filters to see more results.</p>
                                <div className="mx-auto mt-3 max-w-[600px] text-left">
                                    <p className="mb-2 text-sm text-muted-foreground"><strong>Tip:</strong> When searching by Product Description or HSN Code, consider:</p>
                                    <ul className="text-sm text-muted-foreground">
                                        <li>Setting License Status to "All"</li>
                                        <li>Lowering the Min Balance (CIF) to 100</li>
                                        <li>Checking if your search term matches exactly (case-insensitive partial match)</li>
                                    </ul>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {view === "import" && !loading && (reportData?.items?.length ?? 0) > 0 && (
                        <>
                            <ItemReportTable
                                items={pageItems}
                                totalsItems={reportData.items}
                                startSrNo={startSrNo}
                                itemNameMode="editable"
                                itemNameOptions={itemNameOptions}
                                onItemNamesChange={handleItemNamesEdit}
                                editingCell={editingCell}
                                editValue={editValue}
                                onEditValueChange={setEditValue}
                                onStartEdit={startEdit}
                                onCancelEdit={cancelEdit}
                                onSaveEdit={saveEdit}
                            />
                            <DataPagination
                                currentPage={pagination.currentPage}
                                totalPages={pagination.totalPages}
                                pageSize={pagination.pageSize}
                                hasNext={!pagination.isLastPage}
                                hasPrevious={!pagination.isFirstPage}
                                totalItems={licenseGroups.length}
                                onPageChange={pagination.goToPage}
                                onPageSizeChange={pagination.setPageSize}
                            />
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

/**
 * ItemReportActiveFiltersDisplay — shows all active filters with individual remove buttons
 */
function ItemReportActiveFiltersDisplay({
    filters,
    onRemoveFilter,
    onClearAll,
    purchaseStatusOptions,
}: {
    filters: {
        selectedItemNames: unknown[];
        minBalance: number;
        minAvailQty: number;
        licenseStatus: string;
        selectedCompanies: unknown[];
        excludeCompanies: unknown[];
        isRestricted: string;
        purchaseStatus: string[];
        productDescSearch: string;
        hsnCodeSearch: string;
        selectedNorms: string[];
        selectedNotifications: string[];
        expiryDateFrom: string;
        expiryDateTo: string;
        licenseNumbers: string;
    };
    onRemoveFilter: (key: string) => void;
    onClearAll: () => void;
    purchaseStatusOptions: { value: string; label: string }[];
}) {
    const activeFilters: ActiveFilterItem[] = useMemo(() => {
        const items: ActiveFilterItem[] = [];

        // Item Names
        if (filters.selectedItemNames.length > 0) {
            items.push({
                key: 'selectedItemNames',
                label: 'Item Names',
                value: `${filters.selectedItemNames.length} selected`,
            });
        }

        // Min Balance
        if (filters.minBalance !== 200) {
            items.push({
                key: 'minBalance',
                label: 'Min Balance (CIF)',
                value: `₹${filters.minBalance}`,
            });
        }

        // Min Avail Qty
        if (filters.minAvailQty !== 0) {
            items.push({
                key: 'minAvailQty',
                label: 'Min Available Qty',
                value: filters.minAvailQty.toString(),
            });
        }

        // License Status
        if (filters.licenseStatus !== 'active') {
            items.push({
                key: 'licenseStatus',
                label: 'License Status',
                value: filters.licenseStatus,
            });
        }

        // Companies
        if (filters.selectedCompanies.length > 0) {
            items.push({
                key: 'selectedCompanies',
                label: 'Companies',
                value: `${filters.selectedCompanies.length} selected`,
            });
        }

        // Exclude Companies
        if (filters.excludeCompanies.length > 0) {
            items.push({
                key: 'excludeCompanies',
                label: 'Exclude Companies',
                value: `${filters.excludeCompanies.length} excluded`,
            });
        }

        // Restricted
        if (filters.isRestricted !== 'all') {
            items.push({
                key: 'isRestricted',
                label: 'Restricted Items',
                value: filters.isRestricted === 'true' ? 'Yes' : 'No',
            });
        }

        // Purchase Status
        const defaultPurchaseStatus = purchaseStatusOptions.map(o => o.value);
        const isDefaultPurchaseStatus = filters.purchaseStatus.length === defaultPurchaseStatus.length &&
            filters.purchaseStatus.every(ps => defaultPurchaseStatus.includes(ps));
        if (!isDefaultPurchaseStatus && filters.purchaseStatus.length > 0) {
            items.push({
                key: 'purchaseStatus',
                label: 'Purchase Status',
                value: `${filters.purchaseStatus.length} selected`,
            });
        }

        // Product Description Search
        if (filters.productDescSearch) {
            items.push({
                key: 'productDescSearch',
                label: 'Product Description',
                value: `"${filters.productDescSearch}"`,
            });
        }

        // HSN Code Search
        if (filters.hsnCodeSearch) {
            items.push({
                key: 'hsnCodeSearch',
                label: 'HSN Code',
                value: `"${filters.hsnCodeSearch}"`,
            });
        }

        // Norms
        if (filters.selectedNorms.length > 0) {
            items.push({
                key: 'selectedNorms',
                label: 'SION Norms',
                value: `${filters.selectedNorms.length} selected`,
            });
        }

        if (filters.licenseNumbers.trim()) {
            items.push({
                key: 'licenseNumbers',
                label: 'Licence numbers',
                value: filters.licenseNumbers.trim(),
            });
        }

        // Notifications
        if (filters.selectedNotifications.length > 0) {
            items.push({
                key: 'selectedNotifications',
                label: 'Notifications',
                value: `${filters.selectedNotifications.length} selected`,
            });
        }

        // Expiry Date Range
        if (filters.expiryDateFrom || filters.expiryDateTo) {
            const dateRange = [
                filters.expiryDateFrom || '—',
                filters.expiryDateTo || '—',
            ].join(' to ');
            items.push({
                key: 'expiryDateRange',
                label: 'Expiry Date Range',
                value: dateRange,
            });
        }

        return items;
    }, [filters, purchaseStatusOptions]);

    if (activeFilters.length === 0) {
        return null;
    }

    return (
        <div className="mb-4">
            <ActiveFilters
                filters={activeFilters}
                onRemove={onRemoveFilter}
                onClearAll={onClearAll}
                showCount={true}
            />
        </div>
    );
}
